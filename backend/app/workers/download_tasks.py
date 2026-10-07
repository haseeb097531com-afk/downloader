"""Celery task that performs the actual media download.

The task is deliberately pause-aware. Pausing a transfer cannot be done by killing
the worker (that would orphan the ``.part`` file), so instead the progress callback
polls the ``mediavault:pause:{download_id}`` Redis flag on every chunk and raises
:class:`DownloadPausedSignal` when it is set. yt-dlp leaves the partial file in
place, and resuming re-dispatches this same task with ``resume=True``, which turns
on yt-dlp's ``continuedl`` so it picks the transfer back up where it stopped.

Progress is reported through two channels:

* a Redis pub/sub snapshot - live speed and ETA for the queue and WebSocket screens;
* the ``downloads.progress`` column - flushed by a coroutine on the event loop, so
  the queue stays correct even if Redis is unavailable.

The callback itself only mutates a plain dict. It runs on a worker thread (yt-dlp
is blocking), and touching the AsyncSession from that thread would mean using a
session across two event loops, so persistence is handled separately.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.future import select

from app.core.celery_app import celery_app
from app.core import redis_client
from app.core.config import settings
from app.core.redis_client import clear_pause, is_paused, write_progress
from app.db.database import AsyncSessionLocal
from app.models.download import Download, DownloadStatus
from app.services.extractor.fallback_engine import ExtractResult, FallbackExtractor
from app.services.extractor.ytdlp_engine import (
    YTDLPControlSignal,
    YTDLPEngine,
    YTDLPEngineError,
)
from app.services.storage.file_manager import FileManager, FileManagerError
from app.workers.processor_tasks import process_media_task

logger = logging.getLogger(__name__)

__all__ = ["download_media_task", "DownloadPausedSignal", "SystemThrottled"]

# How often the reporter coroutine flushes progress to the database.
_PROGRESS_FLUSH_SECONDS = 1.0

# Progress keys forwarded from the yt-dlp hook into the Redis snapshot.
_PROGRESS_KEYS = ("progress", "speed", "eta", "downloaded_bytes", "total_bytes")


class DownloadPausedSignal(YTDLPControlSignal):
    """Raised inside the progress hook to suspend a download at a chunk boundary.

    Inherits from :class:`YTDLPControlSignal` so
    :meth:`YTDLPEngine.download_media` re-raises it instead of translating it into a
    ``YTDLPEngineError``.
    """


class SystemThrottled(Exception):
    """Raised when the system is overloaded and the download should be retried later."""


@celery_app.task(name="app.workers.download_tasks.download_media_task", bind=True, max_retries=100, default_retry_delay=30)
def download_media_task(self, download_id: str, resume: bool = False) -> Dict[str, Any]:
    """Download one media item to disk, honouring pause requests.

    Args:
        download_id: Primary key of the :class:`Download` row to process.
        resume: Continue a previously interrupted transfer instead of restarting it.

    Returns:
        A dict describing the outcome, with a ``status`` key of ``completed``,
        ``paused``, ``failed`` or ``skipped``. The task never raises for an expected
        outcome: the row's status is the record of truth, and a raised exception would
        make Celery mark a cleanly paused download as errored.
    """
    return asyncio.run(_run_download(self, download_id, resume=resume))


async def _run_download(self, download_id: str, resume: bool) -> Dict[str, Any]:
    """Async body of :func:`download_media_task`."""
    if redis_client.is_throttled():
        raise self.retry(args=[download_id], kwargs={"resume": True}, countdown=30, exc=SystemThrottled("System is overloaded"))

    if redis_client.get_redis().exists("storage_guard"):
        raise self.retry(args=[download_id], kwargs={"resume": True}, countdown=60, exc=SystemThrottled("Storage guard active"))

    # Off-peak delay: if outside off-peak hours and enabled, retry until start.
    if _is_off_peak_delayed():
        countdown = _off_peak_countdown_seconds()
        raise self.retry(args=[download_id], kwargs={"resume": True}, countdown=countdown, exc=SystemThrottled("Off-peak delay active"))

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Download).where(Download.id == download_id))
        download = result.scalars().first()

        if download is None:
            logger.warning("Download %s no longer exists, skipping task", download_id)
            return {"status": "skipped", "reason": "download_not_found", "id": download_id}

        if download.status == DownloadStatus.COMPLETED:
            return {"status": "skipped", "reason": "already_completed", "id": download_id}

        file_manager = FileManager()

        # A pause flag may be left over from a previous attempt; a task that started
        # while its own flag was set would suspend itself on the first chunk.
        clear_pause(download_id)

        download.status = DownloadStatus.DOWNLOADING
        download.error_message = None
        await db.commit()

        try:
            result = await _transfer(self, db, download, file_manager, resume=resume)
        except DownloadPausedSignal:
            download.status = DownloadStatus.PAUSED
            await db.commit()
            progress = float(download.progress or 0.0)
            write_progress(download_id, {"status": "paused", "progress": progress})
            logger.info("Download %s paused at %.1f%%", download_id, progress)
            return {"status": "paused", "id": download_id, "progress": progress}
        except (YTDLPEngineError, FileManagerError) as exc:
            download.status = DownloadStatus.FAILED
            download.error_message = str(exc)[:2000]
            await db.commit()
            logger.error("Download %s failed: %s", download_id, exc)
            return {"status": "failed", "id": download_id, "error": str(exc)}
        except Exception as exc:  # pragma: no cover - must not kill the worker
            download.status = DownloadStatus.FAILED
            download.error_message = f"Unexpected error: {exc}"[:2000]
            await db.commit()
            logger.exception("Download %s crashed", download_id)
            return {"status": "failed", "id": download_id, "error": str(exc)}

        status_value = result.get("status") if isinstance(result, dict) else None
        if status_value in ("completed", "failed") and not getattr(download, "pushed", False):
            try:
                from app.services.notifications.push_service import PushService
                owner_id = getattr(download, "owner_id", None)
                if owner_id:
                    await PushService().send_to_user(
                        db, owner_id, f"Download {status_value}", download.title or "", "download", f"/downloads/{download.id}"
                    )
                    download.pushed = True
                    await db.commit()
            except Exception as exc:
                logger.warning("Push notification failed for download %s: %s", download_id, exc)

        return result


async def _transfer(
    self,
    db,
    download: Download,
    file_manager: FileManager,
    resume: bool,
) -> Dict[str, Any]:
    """Run the yt-dlp transfer on a worker thread and persist the outcome.

    Args:
        db: Active session; used only from this event loop.
        download: The download row being processed.
        file_manager: Filesystem gateway rooted at the download directory.
        resume: Whether to continue a partial transfer.

    Returns:
        A result dict describing the completed or failed transfer.

    Raises:
        DownloadPausedSignal: If a pause was requested mid-transfer.
    """
    download_id = download.id
    file_manager.ensure_dir()
    output_template = file_manager.build_output_template(download.platform or "unknown")

    archive_path = None
    if getattr(settings, "ARCHIVE_DEDUP_ENABLED", False):
        archive_path = getattr(settings, "ARCHIVE_DEDUP_PATH", "") or str(Path(settings.DATA_DIR) / "download_archive.txt")

    # Attempt fallback extraction before downloading.
    fallback = FallbackExtractor()
    try:
        result: ExtractResult = await fallback.extract_with_fallback(download.url)
        if result.metadata:
            download.metadata_json = result.metadata
            if result.degraded:
                existing = download.error_message or ""
                note = "Direct extraction blocked - used fallback API"
                download.error_message = f"{existing}; {note}" if existing else note
            await db.commit()
    except Exception as exc:
        logger.warning("Fallback extraction failed for %s: %s", download_id, exc)

    # Shared with the blocking progress callback, which runs on a worker thread.
    state: Dict[str, Any] = {"progress": float(download.progress or 0.0)}

    def progress_callback(payload: Dict[str, Any]) -> None:
        """Handle one yt-dlp progress event.

        Checks the pause flag first: a pause request must win over reporting
        progress, and the flag has to be honoured promptly since the user is
        watching. Raises :class:`DownloadPausedSignal` to abort the transfer while
        leaving the ``.part`` file intact for a later resume.
        """
        if is_paused(download_id):
            raise DownloadPausedSignal(f"Download {download_id} was paused")

        forwarded = {key: payload[key] for key in _PROGRESS_KEYS if payload.get(key) is not None}
        if payload.get("status") == "finished":
            state["progress"] = 100.0
            forwarded["progress"] = 100.0
            write_progress(download_id, forwarded)
            return

        if "progress" in forwarded:
            state["progress"] = float(forwarded["progress"])
        # Always broadcast, even without a known total: the queue UI still wants
        # speed and ETA in that case.
        write_progress(download_id, forwarded)

    engine = YTDLPEngine()
    format_id = _extract_format_id(download)

    limit_mbps = _bandwidth_limit_mbps()
    auto_quality = _auto_adjust_quality()

    if format_id is None and download.quality and download.quality not in ("best", "audio_only"):
        try:
            best = engine.get_best_format(download.url, download.quality)
            if best and best.get("format_id"):
                format_id = best["format_id"]
        except Exception as exc:
            logger.warning("Quality resolution failed for %s: %s", download_id, exc)

    extra_opts: Dict[str, Any] = {"continuedl": bool(resume)}
    if archive_path:
        extra_opts["download_archive"] = archive_path

    transfer = asyncio.create_task(
        asyncio.to_thread(
            engine.download_media,
            download.url,
            output_template,
            format_id,
            progress_callback,
            extra_opts,
            start_time=download.trim_start,
            end_time=download.trim_end,
            limit_rate_mbps=limit_mbps,
            auto_adjust_quality=auto_quality,
        )
    )
    reporter = asyncio.create_task(_report_progress(db, download_id, state, transfer))

    try:
        filename = await transfer
    finally:
        reporter.cancel()
        try:
            await reporter
        except asyncio.CancelledError:
            pass

    if not filename:
        download.status = DownloadStatus.FAILED
        download.error_message = "Download produced no output file"
        await db.commit()
        return {"status": "failed", "id": download_id, "error": "no_output_file"}

    final_path = await asyncio.to_thread(_resolve_output, file_manager, filename)
    file_size = file_manager.get_size(final_path) if final_path else 0

    download.status = DownloadStatus.COMPLETED
    download.progress = 100.0
    download.file_path = str(final_path) if final_path else None
    download.file_size = file_size
    download.completed_at = datetime.utcnow()
    await db.commit()

    write_progress(download_id, {"status": "completed", "progress": 100.0, "total_bytes": file_size})
    clear_pause(download_id)

    logger.info("Download %s completed: %s (%d bytes)", download_id, final_path, file_size)

    try:
        process_media_task.delay(download_id)
    except Exception as exc:  # pragma: no cover - best effort chaining
        logger.warning("Failed to chain post-processing for %s: %s", download_id, exc)

    return {
        "status": "completed",
        "id": download_id,
        "file_path": str(final_path) if final_path else None,
        "file_size": file_size,
    }


async def _report_progress(db, download_id: str, state: Dict[str, Any], transfer: asyncio.Task) -> None:
    """Flush transfer progress into the database while ``transfer`` is running.

    The blocking yt-dlp call owns a worker thread, so the progress callback cannot
    write through the AsyncSession itself. This coroutine runs on the event loop and
    periodically mirrors the shared ``state`` dict into the row, keeping the value
    fresh without one UPDATE per downloaded chunk.
    """
    last_flushed = float(state.get("progress") or 0.0)

    while not transfer.done():
        await asyncio.sleep(_PROGRESS_FLUSH_SECONDS)
        current = float(state.get("progress") or 0.0)
        if abs(current - last_flushed) < 0.5:
            continue

        try:
            result = await db.execute(select(Download).where(Download.id == download_id))
            row = result.scalars().first()
            if row is not None:
                row.progress = current
                await db.commit()
                last_flushed = current
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Deferred progress flush for %s failed: %s", download_id, exc)


def _extract_format_id(download: Download) -> Optional[str]:
    """Return a concrete yt-dlp format ID recorded at extraction time, if any.

    ``download.quality`` holds a preference such as ``"best"`` or ``"1080p"``, not a
    format selector yt-dlp accepts, so it is deliberately not passed as ``format``.
    """
    metadata = download.metadata_json
    if isinstance(metadata, dict):
        value = metadata.get("format_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_output(file_manager: FileManager, filename: str) -> Optional[Path]:
    """Turn yt-dlp's returned filename into a validated path inside the library.

    yt-dlp returns the *prepared* name, which may not exist when the container
    differed from the template, and may point outside the download directory for
    exotic extractors. Anything failing containment is rejected rather than trusted.

    Args:
        file_manager: Gateway used for the containment check.
        filename: Path returned by :meth:`YTDLPEngine.download_media`.

    Returns:
        The validated media path, or ``None`` when nothing usable was found.
    """
    if not filename:
        return None

    try:
        candidate = file_manager.resolve(filename)
    except FileManagerError:
        logger.warning("yt-dlp returned a path outside the library: %s", filename)
        return None

    if candidate.is_file():
        return candidate

    # The template ends in .%(ext)s; after a merge the real container can differ,
    # so look for the same stem with any media extension before giving up.
    if candidate.parent.is_dir():
        for sibling in sorted(candidate.parent.glob(f"{candidate.stem}.*")):
            if file_manager.is_media_file(sibling):
                return sibling

    logger.warning("Downloaded file not found on disk: %s", filename)
    return None


def _is_off_peak_delayed() -> bool:
    """Return True when off-peak mode is active and the current time is outside the allowed window."""
    if not settings.OFF_PEAK_ENABLED:
        return False
    now = datetime.now().time()
    try:
        start = datetime.strptime(settings.OFF_PEAK_START, "%H:%M").time()
        end = datetime.strptime(settings.OFF_PEAK_END, "%H:%M").time()
    except ValueError:
        return False
    if start <= end:
        return now < start or now >= end
    return now < start and now >= end


def _off_peak_countdown_seconds() -> int:
    """Return seconds until the next off-peak window opens."""
    now = datetime.now()
    try:
        start = datetime.strptime(settings.OFF_PEAK_START, "%H:%M").time()
    except ValueError:
        return 300
    next_start = now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    if now >= next_start:
        from datetime import timedelta
        next_start += timedelta(days=1)
    delta = (next_start - now).total_seconds()
    return max(int(delta), 60)


def _bandwidth_limit_mbps() -> Optional[int]:
    if settings.BANDWIDTH_LIMIT_MBPS and settings.BANDWIDTH_LIMIT_MBPS > 0:
        return settings.BANDWIDTH_LIMIT_MBPS
    return None


def _auto_adjust_quality() -> bool:
    return bool(settings.AUTO_ADJUST_QUALITY)