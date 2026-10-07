"""Post-processing pipeline for completed downloads."""

from __future__ import annotations

import inspect
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.download import Download, DownloadStatus
from app.services.ai.analysis_pipeline import AnalysisPipeline
from app.services.ai.categorizer import ContentCategorizer
from app.services.moderator import ContentModerator, ModerationResult
from app.services.processor.ffmpeg_engine import FFmpegEngine

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """Run post-processing steps on a completed download."""

    def __init__(self, ffmpeg: Optional[FFmpegEngine] = None, db_session: Optional[AsyncSession] = None) -> None:
        self.ffmpeg = ffmpeg or FFmpegEngine()
        self._categorizer = ContentCategorizer()
        self._analysis = AnalysisPipeline()
        self._db_session = db_session

    @staticmethod
    async def _await_maybe(value):
        if inspect.isawaitable(value):
            return await value
        return value

    async def process_download(self, download_id: str) -> None:
        """Run merge, metadata embed, thumbnail generation, and auto-move for ``download_id``.

        Failures are swallowed so the download remains usable; ``processing_error``
        records the cause.
        """
        if self._db_session is not None:
            db = self._db_session
            result = await db.execute(select(Download).where(Download.id == download_id))
            download = result.scalars().first()
        else:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Download).where(Download.id == download_id))
                download = result.scalars().first()

        if download is None:
            logger.warning("Processing skipped: download %s not found", download_id)
            return

        download.status = DownloadStatus.PROCESSING
        if self._db_session is not None:
            await self._db_session.commit()
        else:
            await db.commit()

        temp_files: list[str] = []
        file_path = download.file_path

        try:
            if not file_path or not Path(file_path).exists():
                raise ValueError(f"Download file not found: {file_path}")

            if self._db_session is not None:
                session = self._db_session
            else:
                session = db

            # 1) Auto-merge separate video+audio streams.
            if settings.AUTO_MERGE:
                video_path, audio_path = self._find_separate_streams(file_path)
                if video_path and audio_path:
                    merged_path = str(Path(file_path).with_suffix(".mp4"))
                    merged = await self._await_maybe(self.ffmpeg.merge_streams(video_path, audio_path, merged_path))
                    if isinstance(merged, str) and merged:
                        file_path = merged
                        download.file_path = file_path
                    temp_files.extend([video_path, audio_path])

            # 2) Normalize non-MP4 containers to MP4 for broad compatibility.
            if file_path and Path(file_path).suffix.lower() in {".webm", ".mkv"}:
                normalized_path = str(Path(file_path).with_suffix(".mp4"))
                normalized = await self._await_maybe(self.ffmpeg.normalize_to_mp4(file_path, normalized_path))
                if isinstance(normalized, str) and normalized:
                    file_path = normalized
                    download.file_path = file_path

            # 3) Embed metadata.
            if settings.EMBED_METADATA and file_path:
                meta = self._build_metadata(download)
                embedded = await self._await_maybe(self.ffmpeg.embed_metadata(file_path, meta))
                if isinstance(embedded, str) and embedded:
                    file_path = embedded
                    download.file_path = file_path

            # 4) Generate thumbnail.
            if settings.GENERATE_THUMBNAILS and file_path:
                thumb_dir = Path(settings.DOWNLOAD_DIR) / "thumbnails"
                thumb_dir.mkdir(parents=True, exist_ok=True)
                thumb_path = str(thumb_dir / f"{download.id}.jpg")
                thumb = await self._await_maybe(self.ffmpeg.generate_thumbnail(file_path, thumb_path))
                if isinstance(thumb, str) and thumb:
                    download.thumbnail_local = thumb

            # 5) Auto-categorize and move.
            move_error = None
            if settings.AUTO_CATEGORIZE and file_path:
                move_error = await self._categorize_and_move(session, download, file_path)

            # 5a) Safe-mode moderation / quarantine.
            moderation_error = None
            current_path = download.file_path or file_path
            if getattr(settings, "SAFE_MODE", False) and current_path:
                moderation_error = await self._maybe_quarantine(session, download, current_path)
            if moderation_error:
                move_error = moderation_error

            download.processed = True
            download.processing_error = move_error or None
            download.status = DownloadStatus.COMPLETED
            download.completed_at = datetime.utcnow()
            await session.commit()
            logger.info("Processing complete for download %s", download_id)

            try:
                from app.services.notifications.push_service import PushService
                if not getattr(download, "pushed", False):
                    owner_id = getattr(download, "owner_id", None)
                    if owner_id:
                        await PushService().send_to_user(
                            db if self._db_session is None else self._db_session,
                            owner_id,
                            "Processing complete",
                            download.title or "",
                            "processing",
                            f"/downloads/{download_id}",
                        )
                    download.pushed = True
                    await session.commit()
            except Exception as exc:
                logger.warning("Push notification failed for processing %s: %s", download_id, exc)

            # 6) Chain AI analysis if enabled.
            if getattr(settings, "AI_ANALYSIS_ENABLED", False):
                try:
                    from app.workers.ai_tasks import analysis_task
                    analysis_task.delay(download_id)
                except Exception as exc:
                    logger.warning("Failed to enqueue analysis task: %s", exc)

            # 7) Fingerprint for dedup if enabled (exception-isolated).
            if getattr(settings, "DEDUP_ENABLED", False):
                try:
                    from app.services.ai.dedup import DedupEngine
                    engine = DedupEngine(session)
                    await engine.fingerprint_download(download_id)
                except Exception as exc:
                    logger.warning("Failed to fingerprint download %s: %s", download_id, exc)

        except Exception as exc:
            logger.warning("Processing failed for download %s: %s", download_id, exc)
            download.processed = False
            download.processing_error = str(exc)[:2000]
            download.status = DownloadStatus.COMPLETED
            download.completed_at = datetime.utcnow()
            if self._db_session is not None:
                await self._db_session.commit()
            elif 'session' in locals():
                try:
                    from app.services.notifications.push_service import PushService
                    if not getattr(download, "pushed", False):
                        owner_id = getattr(download, "owner_id", None)
                        if owner_id:
                            await PushService().send_to_user(
                                session, owner_id, "Processing failed", download.title or "", "processing", f"/downloads/{download_id}"
                            )
                        download.pushed = True
                        await session.commit()
                except Exception as push_exc:
                    logger.warning("Push notification failed for processing %s: %s", download_id, push_exc)
                    try:
                        await session.commit()
                    except Exception:
                        pass
        finally:
            for temp in temp_files:
                Path(temp).unlink(missing_ok=True)

    async def _categorize_and_move(self, db, download: Download, file_path: str) -> Optional[str]:
        """Categorize the download and move it into a category subfolder.

        Returns:
            An error message if the move failed, or None on success.
        """
        metadata = download.metadata_json or {}
        title = download.title or metadata.get("title") or ""
        description = metadata.get("description") or ""
        tags = metadata.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]

        result = self._categorizer.categorize(title=title, description=description, tags=tags)
        download.category = result.category

        if result.category == "Other" or not file_path:
            return None

        src = Path(file_path)
        if not src.exists():
            return None

        platform = download.platform or "unknown"
        uploader = metadata.get("uploader_name") or metadata.get("uploader") or metadata.get("username") or "unknown"
        username = str(uploader).replace("/", "_").replace("\\", "_")
        dest_dir = Path(settings.DOWNLOAD_DIR) / platform / f"@{username}" / result.category
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name

        try:
            shutil.move(str(src), str(dest))
            download.file_path = str(dest)
            return None
        except Exception as exc:
            logger.warning("Failed to move categorized file %s -> %s: %s", src, dest, exc)
            return f"Auto-move failed: {exc}"

    async def _maybe_quarantine(self, db, download: Download, file_path: str) -> Optional[str]:
        """Run safe-mode moderation and quarantine the file when flagged."""
        metadata = download.metadata_json or {}
        title = download.title or metadata.get("title") or ""
        description = metadata.get("description") or ""
        tags = metadata.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        transcript = metadata.get("transcript") or metadata.get("transcription")

        moderator = ContentModerator(
            blacklist=getattr(settings, "KEYWORD_BLACKLIST", []),
            sensitivity=getattr(settings, "MODERATION_SENSITIVITY", 0.5),
        )
        result = moderator.check_content(title=title, description=description, tags=tags, transcript=transcript)
        if not result.flagged:
            return None

        src = Path(file_path)
        if not src.exists():
            return None

        platform = download.platform or "unknown"
        quarantine_root = Path(settings.DOWNLOAD_DIR) / "_quarantine" / platform
        quarantine_root.mkdir(parents=True, exist_ok=True)
        dest = quarantine_root / src.name

        try:
            shutil.move(str(src), str(dest))
            download.file_path = str(dest)
            download.quarantined = True
            download.quarantine_reason = "; ".join(result.reasons) if result.reasons else "flagged_by_moderation"
            await db.commit()
            logger.info("Quarantined download %s: %s", download.id, download.quarantine_reason)
            return None
        except Exception as exc:
            logger.warning("Failed to quarantine file %s: %s", src, exc)
            return f"Quarantine failed: {exc}"

    def _find_separate_streams(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Return ``(video_path, audio_path)`` if the download left separate files."""
        path = Path(file_path)
        stem = path.stem
        parent = path.parent

        video_file: Optional[str] = None
        audio_file: Optional[str] = None

        if path.suffix.lower() in settings.VIDEO_EXTENSIONS:
            video_file = str(path)
        elif path.suffix.lower() in settings.AUDIO_EXTENSIONS:
            audio_file = str(path)

        try:
            entries = list(parent.iterdir())
        except OSError:
            if video_file and audio_file:
                return video_file, audio_file
            return None, None

        for candidate in entries:
            if candidate.stem != stem:
                continue
            if candidate == path:
                continue
            ext = candidate.suffix.lower()
            if ext in settings.VIDEO_EXTENSIONS and not video_file:
                video_file = str(candidate)
            elif ext in settings.AUDIO_EXTENSIONS and not audio_file:
                audio_file = str(candidate)

        if video_file and audio_file:
            return video_file, audio_file
        return None, None

    def _build_metadata(self, download: Download) -> dict:
        """Build ffmpeg -metadata flags from the download record."""
        meta: dict = {}
        if download.title:
            meta["title"] = download.title
        metadata = download.metadata_json or {}
        uploader = metadata.get("uploader_name") or metadata.get("uploader") or metadata.get("username")
        if uploader:
            meta["artist"] = str(uploader)
        upload_date = metadata.get("upload_date")
        if upload_date:
            meta["date"] = str(upload_date)
        description = metadata.get("description")
        if description:
            meta["comment"] = str(description)[:500]
        return meta
