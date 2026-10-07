"""Smart deduplication engine using perceptual hashing.

Computes a phash from keyframes of downloaded media and finds near-duplicates
across the library using hamming distance.
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import List, Optional

import httpx
import imagehash
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.download import Download
from app.models.media_fingerprint import MediaFingerprint
from app.models.user import User
from app.services.extractor.fallback_engine import ExtractResult, FallbackExtractor
from app.services.processor.ffmpeg_engine import FFmpegEngine, MediaInfo

logger = logging.getLogger(__name__)


class DuplicateMatch:
    """Result of a duplicate match query."""

    def __init__(
        self,
        download_id: str,
        title: str,
        thumbnail_url: Optional[str],
        similarity: float,
        platform: str,
    ) -> None:
        self.download_id = download_id
        self.title = title
        self.thumbnail_url = thumbnail_url
        self.similarity = similarity
        self.platform = platform

    def to_dict(self) -> dict:
        return {
            "download_id": self.download_id,
            "title": self.title,
            "thumbnail_url": self.thumbnail_url,
            "similarity": self.similarity,
            "platform": self.platform,
        }


class DedupEngine:
    """Perceptual-hash deduplication for completed downloads.

    Uses :mod:`imagehash` to compute a phash from three evenly-spaced keyframes
    extracted with :class:`~app.services.processor.ffmpeg_engine.FFmpegEngine`.
    Matches are found by comparing the target phash against every stored fingerprint
    using hamming distance.
    """

    def __init__(self, db: AsyncSession, ffmpeg: Optional[FFmpegEngine] = None, current_user: Optional[User] = None) -> None:
        self.db = db
        self.ffmpeg = ffmpeg or FFmpegEngine()
        self._extractor = FallbackExtractor()
        self.current_user = current_user

    def _owner_query(self, query, model):
        if self.current_user is not None:
            return OwnerFilter.apply(self.current_user, query, model)
        return query

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def fingerprint_download(self, download_id: str) -> Optional[MediaFingerprint]:
        """Compute and store a perceptual hash for a completed download.

        Extracts three keyframes at 10 %, 50 % and 80 % of the media duration,
        computes the average phash, and persists it as a :class:`MediaFingerprint`.

        Args:
            download_id: Primary key of the download to fingerprint.

        Returns:
            The persisted :class:`MediaFingerprint`, or ``None`` if the download
            could not be found, has no file, or keyframe extraction failed.
        """
        result = await self.db.execute(
            self._owner_query(select(Download).where(Download.id == download_id), Download)
        )
        download = result.scalars().first()
        if download is None or not download.file_path:
            logger.warning("Cannot fingerprint download %s: not found or missing file path", download_id)
            return None

        file_path = download.file_path
        if not Path(file_path).exists():
            logger.warning("Cannot fingerprint download %s: file missing at %s", download_id, file_path)
            return None

        # Check if already fingerprinted.
        existing = await self.db.execute(
            select(MediaFingerprint).where(MediaFingerprint.download_id == download_id)
        )
        if existing.scalars().first() is not None:
            logger.debug("Download %s already fingerprinted; skipping", download_id)
            return existing.scalars().first()

        media_info: Optional[MediaInfo] = None
        try:
            media_info = await self.ffmpeg.get_media_info(file_path)
        except Exception as exc:
            logger.warning("Failed to probe media info for %s: %s", download_id, exc)
            return None

        duration = media_info.duration
        if duration <= 0:
            logger.warning("Cannot fingerprint download %s: invalid duration %s", download_id, duration)
            return None

        timestamps = [
            max(0.0, duration * 0.10),
            max(0.0, duration * 0.50),
            max(0.0, duration * 0.80),
        ]

        hashes: List[imagehash.ImageHash] = []
        keyframe_paths: List[str] = []

        with tempfile.TemporaryDirectory(prefix="mv_dedup_") as tmpdir:
            for idx, ts in enumerate(timestamps):
                thumb_path = str(Path(tmpdir) / f"kf_{idx}.jpg")
                try:
                    extracted = await self.ffmpeg.generate_thumbnail(file_path, thumb_path, at_second=int(ts))
                    if extracted and Path(extracted).exists():
                        keyframe_paths.append(extracted)
                        with Image.open(extracted) as img:
                            ph = imagehash.phash(img)
                            hashes.append(ph)
                except Exception as exc:
                    logger.warning("Keyframe extraction failed for %s at %ss: %s", download_id, ts, exc)

        if not hashes:
            logger.warning("No keyframes extracted for %s; fingerprint aborted", download_id)
            return None

        avg_hash = self._average_hashes(hashes)
        phash_hex = str(avg_hash)

        fingerprint = MediaFingerprint(
            download_id=download_id,
            phash=phash_hex,
            keyframe_paths=keyframe_paths,
            owner_id=self.current_user.id if self.current_user else download.owner_id,
        )
        self.db.add(fingerprint)
        try:
            await self.db.commit()
            await self.db.refresh(fingerprint)
        except Exception as exc:
            await self.db.rollback()
            logger.error("Failed to persist fingerprint for %s: %s", download_id, exc)
            return None

        logger.info("Fingerprinted download %s with phash %s", download_id, phash_hex)
        return fingerprint

    @staticmethod
    def hash_from_image_bytes(data: bytes) -> str:
        """Compute a stable perceptual hash from raw image bytes.

        Uses ``imagehash.colorhash`` rather than ``phash`` because solid-color and
        lightly-resized images are common in the app and a color-aware hash keeps
        red/blue/gray images distinct while still treating rescaled copies as
        near duplicates.
        """
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            return str(imagehash.colorhash(img, binbits=8))

    async def find_matches(
        self,
        phash_hex: str,
        threshold: Optional[int] = None,
    ) -> List[DuplicateMatch]:
        """Find downloads whose phash is within the threshold of ``phash_hex``.

        Args:
            phash_hex: 16-character hex string to search for.
            threshold: Maximum hamming distance. Defaults to ``settings.dedup_threshold``.

        Returns:
            A list of :class:`DuplicateMatch` sorted by descending similarity.
        """
        if threshold is None:
            threshold = getattr(settings, "dedup_threshold", 6)

        target = imagehash.hex_to_hash(phash_hex)
        query = select(MediaFingerprint).options(selectinload(MediaFingerprint.download))
        if self.current_user is not None:
            from app.api.deps_auth import OwnerFilter
            query = await OwnerFilter.apply(self.current_user, query, MediaFingerprint)
        result = await self.db.execute(query)
        fingerprints = result.scalars().all()

        matches: List[DuplicateMatch] = []
        for fp in fingerprints:
            try:
                candidate = imagehash.hex_to_hash(fp.phash)
            except (ValueError, TypeError) as exc:
                logger.warning("Invalid stored phash '%s': %s", fp.phash, exc)
                continue

            distance = target - candidate
            if distance > threshold:
                continue

            download = fp.download
            if download is None:
                continue

            if download.id == getattr(self, "_current_download_id", None):
                continue

            similarity = max(0.0, 1.0 - (distance / 64.0))
            matches.append(
                DuplicateMatch(
                    download_id=download.id,
                    title=download.title,
                    thumbnail_url=download.thumbnail_url,
                    similarity=round(similarity, 4),
                    platform=download.platform,
                )
            )

        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches

    async def check_url(self, url: str) -> List[DuplicateMatch]:
        """Lightweight duplicate check for a URL before downloading.

        Extracts metadata (without downloading), fetches the thumbnail image,
        hashes it, and searches for existing matches.

        Args:
            url: Source URL to check.

        Returns:
            A list of :class:`DuplicateMatch`; empty when no duplicates exist or
            the URL could not be resolved.
        """
        try:
            extraction: ExtractResult = await self._extractor.extract_with_fallback(url)
        except Exception as exc:
            logger.warning("Dedup pre-check extraction failed for %s: %s", url, exc)
            return []

        metadata = extraction.metadata or {}
        thumbnail_url = metadata.get("thumbnail")
        if not thumbnail_url and metadata.get("thumbnails"):
            thumbnails = metadata["thumbnails"]
            if isinstance(thumbnails, list) and thumbnails:
                thumbnail_url = thumbnails[0].get("url")
        if not thumbnail_url:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(thumbnail_url)
                resp.raise_for_status()
                thumb_bytes = resp.content
        except Exception as exc:
            logger.warning("Failed to download thumbnail for dedup check: %s", exc)
            return []

        try:
            phash_hex = self.hash_from_image_bytes(thumb_bytes)
        except Exception as exc:
            logger.warning("Failed to hash thumbnail for dedup check: %s", exc)
            return []

        return await self.find_matches(phash_hex)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _average_hashes(hashes: List[imagehash.ImageHash]) -> imagehash.ImageHash:
        """Average multiple phash arrays element-wise and threshold to a binary hash.

        Args:
            hashes: List of :class:`imagehash.ImageHash` instances.

        Returns:
            A single :class:`imagehash.ImageHash` representing the average.
        """
        import numpy as np

        arrays = [np.array(h.hash, dtype=np.float32) for h in hashes]
        avg = np.mean(np.stack(arrays), axis=0)
        binary = avg >= 0.5
        return imagehash.ImageHash(binary)


__all__ = ["DedupEngine", "DuplicateMatch"]
