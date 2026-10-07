"""Maintenance Celery tasks for Phase 11A smart deduplication."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

import imagehash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core import redis_client
from app.db.database import AsyncSessionLocal
from app.models.download import Download, DownloadStatus
from app.models.media_fingerprint import MediaFingerprint
from app.services.ai.dedup import DedupEngine
from app.services.processor.ffmpeg_engine import FFmpegEngine

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.maintenance_tasks.fingerprint_download_task")
def fingerprint_download_task(download_id: str) -> None:
    """Compute and persist a perceptual hash for a completed download."""
    asyncio.run(_run_fingerprint(download_id))


async def _run_fingerprint(download_id: str) -> None:
    async with AsyncSessionLocal() as db:
        engine = DedupEngine(db)
        try:
            await engine.fingerprint_download(download_id)
        except Exception as exc:
            logger.warning("Fingerprint task failed for %s: %s", download_id, exc)


@celery_app.task(name="app.workers.maintenance_tasks.dedup_scan_task")
def dedup_scan_task() -> None:
    """Fingerprint every completed download that lacks a MediaFingerprint.

    Groups duplicates (hamming distance <= threshold) and stores the latest
    report in Redis key ``dedup_report`` as JSON.
    """
    asyncio.run(_run_scan())


async def _run_scan() -> None:
    async with AsyncSessionLocal() as db:
        # Find completed downloads that have not been fingerprinted yet.
        result = await db.execute(
            select(Download)
            .outerjoin(MediaFingerprint, MediaFingerprint.download_id == Download.id)
            .where(Download.status == DownloadStatus.COMPLETED)
            .where(MediaFingerprint.id.is_(None))
        )
        downloads = result.scalars().all()

        if not downloads:
            logger.info("Dedup scan: no unfingerprinted completed downloads found")
            _write_report(db, [])
            return

        engine = DedupEngine(db)
        threshold = getattr(settings, "dedup_threshold", 6)
        fingerprinted = 0

        for download in downloads:
            try:
                fp = await engine.fingerprint_download(download.id)
                if fp is not None:
                    fingerprinted += 1
            except Exception as exc:
                logger.warning("Dedup scan: failed to fingerprint %s: %s", download.id, exc)

        await db.commit()
        logger.info("Dedup scan: fingerprinted %d new downloads", fingerprinted)

        # Build duplicate groups from all fingerprints.
        report = await _build_groups(db, threshold)
        _write_report(db, report)


async def _build_groups(db: AsyncSession, threshold: int) -> list[dict[str, Any]]:
    """Return duplicate groups from all stored fingerprints."""
    result = await db.execute(
        select(MediaFingerprint).options(selectinload(MediaFingerprint.download))
    )
    fingerprints = result.scalars().all()

    if not fingerprints:
        return []

    # Build a lookup: phash -> [fingerprint]
    # Group by phash first (exact matches).
    by_hash: dict[str, list[MediaFingerprint]] = defaultdict(list)
    for fp in fingerprints:
        by_hash[fp.phash].append(fp)

    groups: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # First pass: exact phash matches.
    for phash_val, fps in by_hash.items():
        if len(fps) < 2:
            continue
        group: dict[str, Any] = {"keep": None, "duplicates": []}
        for fp in fps:
            dl = fp.download
            if dl is None:
                continue
            entry = {
                "id": dl.id,
                "title": dl.title,
                "similarity": 1.0,
                "platform": dl.platform,
            }
            if group["keep"] is None:
                group["keep"] = entry
            else:
                group["duplicates"].append(entry)
            seen_ids.add(dl.id)
        if group["keep"] and group["duplicates"]:
            groups.append(group)

    # Second pass: near-duplicate matches within threshold.
    fps_list = list(fingerprints)
    for i, fp_a in enumerate(fps_list):
        dl_a = fp_a.download
        if dl_a is None or dl_a.id in seen_ids:
            continue
        group = {"keep": None, "duplicates": []}
        group["keep"] = {
            "id": dl_a.id,
            "title": dl_a.title,
            "similarity": 1.0,
            "platform": dl_a.platform,
        }
        seen_ids.add(dl_a.id)
        for j in range(i + 1, len(fps_list)):
            fp_b = fps_list[j]
            dl_b = fp_b.download
            if dl_b is None or dl_b.id in seen_ids:
                continue
            try:
                dist = imagehash.hex_to_hash(fp_a.phash) - imagehash.hex_to_hash(fp_b.phash)
            except Exception:
                continue
            if dist <= threshold:
                similarity = max(0.0, 1.0 - (dist / 64.0))
                group["duplicates"].append({
                    "id": dl_b.id,
                    "title": dl_b.title,
                    "similarity": round(similarity, 4),
                    "platform": dl_b.platform,
                })
                seen_ids.add(dl_b.id)
        if group["duplicates"]:
            groups.append(group)

    return groups


def _write_report(db: AsyncSession, report: list[dict[str, Any]]) -> None:
    """Persist the dedup report to Redis."""
    try:
        client = redis_client.get_redis()
        client.set("dedup_report", json.dumps(report, default=str))
    except Exception as exc:
        logger.warning("Failed to write dedup report to Redis: %s", exc)


def read_dedup_report() -> list[dict[str, Any]]:
    """Read the latest dedup report from Redis."""
    try:
        client = redis_client.get_redis()
        raw = client.get("dedup_report")
        if not raw:
            return []
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Failed to read dedup report from Redis: %s", exc)
        return []


__all__ = [
    "fingerprint_download_task",
    "dedup_scan_task",
    "read_dedup_report",
]
