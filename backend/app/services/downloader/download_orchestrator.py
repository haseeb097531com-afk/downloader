"""Download queue orchestration.

Owns everything that happens *around* a download: placing it in the queue,
reordering it, pausing it, and resuming it. The actual byte transfer lives in
:mod:`app.workers.download_tasks`; this module is the control plane.

Queue ordering is stored on the ``download_queue`` table (``priority`` +
``position``) rather than in Redis, so the order survives a broker restart and can
be queried and tested without a live Redis. Redis carries only the ephemeral pause
flags and live progress snapshots.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis_client
from app.core.config import settings
from app.models.download import Download, DownloadStatus
from app.models.download_queue import QueueItem
from app.models.user import User
from app.api.deps_auth import OwnerFilter
from app.schemas.queue import (
    DownloadActionResult,
    QueueActionResult,
    QueueEntry,
    QueueSnapshot,
)

logger = logging.getLogger(__name__)

__all__ = [
    "DownloadOrchestrator",
    "QueueError",
    "DuplicateFoundError",
    "DownloadNotFound",
    "InvalidTransition",
    "DispatchUnavailable",
]

# Statuses that mean "this item is done with the queue"; their rows are removed so
# a completed or failed download stops occupying a queue slot.
_TERMINAL_STATUSES = (
    DownloadStatus.COMPLETED,
    DownloadStatus.FAILED,
    DownloadStatus.CANCELLED,
)

# Statuses whose downloads are actively transferring.
_ACTIVE_STATUSES = (DownloadStatus.DOWNLOADING, DownloadStatus.PROCESSING)


class QueueError(Exception):
    """Base class for queue operation failures."""


class DuplicateFoundError(QueueError):
    """Raised when a duplicate of an existing download is detected.

    Attributes:
        matches: List of dicts describing the duplicate downloads found.
    """

    def __init__(self, matches: list, detail: str = "") -> None:
        super().__init__(detail)
        self.matches = matches


class DownloadNotFound(QueueError):
    """Raised when no download record exists for the supplied ID."""


class InvalidTransition(QueueError):
    """Raised when an action does not apply to the download's current status."""


class DispatchUnavailable(QueueError):
    """Raised when the Celery broker cannot be reached to dispatch a task."""


class DownloadOrchestrator:
    """Queue control plane for downloads.

    Args:
        db: Active database session for the request.
        task_dispatcher: Callable taking ``(download_id, resume)`` and returning the
            Celery task ID. Defaults to dispatching
            ``app.workers.download_tasks.download_media_task``. Tests inject a fake
            so no broker is required.
    """

    def __init__(self, db: AsyncSession, task_dispatcher=None, current_user: Optional[User] = None) -> None:
        self.db = db
        self._dispatcher = task_dispatcher or self._default_dispatcher
        self.current_user = current_user

    async def _owner_query(self, query):
        """Apply owner scoping to ``query`` when auth is enabled."""
        if self.current_user is not None:
            from app.api.deps_auth import OwnerFilter, visible_users
            visible = await visible_users(self.current_user, self.db)
            return OwnerFilter.apply(self.current_user, query, Download, visible_user_ids=visible)
        return query

    # ------------------------------------------------------------------ #
    # Enqueueing
    # ------------------------------------------------------------------ #
    async def enqueue_download(
        self,
        download: Download,
        dispatch: bool = True,
    ) -> Optional[str]:
        """Register a download in the queue and optionally dispatch it to a worker.

        Args:
            download: A :class:`Download` already added to the session. The caller
                owns the commit; this method only flushes so ``download.id`` exists.
            dispatch: Set ``False`` to leave the item queued for a later kick - used
                by bulk enqueues that fill the queue and dispatch separately.

        Returns:
            The Celery task ID when dispatched, otherwise ``None``.
        """
        await self.db.flush()

        queue_item = await self._get_or_create_queue_item(download.id)
        if queue_item.position is None:
            queue_item.position = await self._next_position()
            queue_item.priority = 0
            queue_item.status = "queued"
            await self.db.flush()

        if not dispatch:
            return None

        return await self.dispatch(download.id)

    async def dispatch(self, download_id: str, resume: bool = False) -> Optional[str]:
        """Send a download to a Celery worker and record the task ID.

        The pause flag is cleared first when resuming, so the worker's very first
        progress callback does not immediately re-pause the download.

        Args:
            download_id: Download to run.
            resume: Pass ``True`` to have yt-dlp continue a partial ``.part`` file.

        Returns:
            The Celery task ID, or ``None`` when the dispatcher is a no-op.

        Raises:
            DispatchUnavailable: If the broker rejects the dispatch. The download row
                stays ``PENDING`` so the user can retry rather than losing it.
        """
        if resume:
            redis_client.clear_pause(download_id)

        task_id = self._dispatcher(download_id, resume)
        if task_id:
            download = await self._get_download(download_id)
            download.celery_task_id = task_id
            if download.status in (DownloadStatus.PAUSED, DownloadStatus.FAILED):
                download.status = DownloadStatus.PENDING
            await self.db.commit()
        return task_id

    def _default_dispatcher(self, download_id: str, resume: bool) -> Optional[str]:
        """Default dispatcher: hand the download to the Celery worker.

        The import is local so that importing this module does not pull in yt-dlp
        and Celery at API import time.
        """
        import redis
        import threading
        import subprocess
        import os
        from app.models.download import Download, DownloadStatus
        from app.core.config import settings

        try:
            r = redis.Redis(host='localhost', port=6379, socket_timeout=1)
            r.ping()
            redis_alive = True
        except Exception:
            redis_alive = False

        if not redis_alive:
            logger.warning("Redis is unreachable, falling back to local background thread for download %s", download_id)
            
            def _fallback_download(d_id: str):
                logger.info("Fallback thread STARTED for download %s", d_id)
                try:
                    import asyncio
                    from app.db.database import AsyncSessionLocal
                    from sqlalchemy import select
                    async def _run():
                        logger.info("Fallback _run STARTED for download %s", d_id)
                        try:
                            async with AsyncSessionLocal() as session:
                                result = await session.execute(select(Download).where(Download.id == d_id))
                                d = result.scalars().first()
                                if not d:
                                    logger.warning("Fallback: download %s not found in DB", d_id)
                                    return
                                logger.info("Fallback: Found download %s, setting to DOWNLOADING", d_id)
                                d.status = DownloadStatus.DOWNLOADING
                                await session.commit()
                                
                                out_dir = settings.DOWNLOAD_DIR
                                os.makedirs(out_dir, exist_ok=True)
                                quality = d.quality if getattr(d, 'quality', None) else "best"
                                format_str = f"-f {quality}" if quality != "best" else ""
                                out_template = os.path.join(out_dir, f"{d_id}.%(ext)s")
                                
                                yt_dlp_path = r"D:\new downloader\backend\.venv\Scripts\yt-dlp.exe"
                                if not os.path.exists(yt_dlp_path):
                                    yt_dlp_path = "yt-dlp"
    
                                # Use list args instead of shell string for Windows compatibility
                                cmd = [yt_dlp_path, d.url, "-o", out_template]
                                if format_str:
                                    cmd.extend(format_str.split())
                                
                                logger.info("Fallback: Running yt-dlp command: %s", cmd)
                                process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                                
                                if process.returncode == 0:
                                    d.status = DownloadStatus.COMPLETED
                                    # Try to find the downloaded file
                                    for f in os.listdir(out_dir):
                                        if f.startswith(d_id):
                                            d.file_path = os.path.join(out_dir, f)
                                            break
                                    logger.info("Fallback: Download completed for %s, file: %s", d_id, d.file_path)
                                else:
                                    d.status = DownloadStatus.FAILED
                                    d.error_message = process.stderr[-1000:] if process.stderr else "yt-dlp error"
                                    logger.error("Fallback: yt-dlp failed for %s: %s", d_id, d.error_message)
                                await session.commit()
                                logger.info("Fallback: Committed final status for %s: %s", d_id, d.status)
                        except Exception as e:
                            logger.error("Fallback download error for %s: %s", d_id, e)
                    asyncio.run(_run())
                except Exception as e:
                    logger.error("Fallback download thread error for %s: %s", d_id, e)
            
            t = threading.Thread(target=_fallback_download, args=(download_id,))
            t.start()
            return f"local-thread-{download_id}"

        from app.workers.download_tasks import download_media_task

        try:
            async_result = download_media_task.delay(download_id, resume)
        except Exception as exc:  # broker unreachable, serialisation failure, ...
            logger.error("Failed to dispatch download %s: %s", download_id, exc)
            raise DispatchUnavailable(f"Could not reach the download worker: {exc}") from exc
        return getattr(async_result, "id", None)

    # ------------------------------------------------------------------ #
    # Queue inspection
    # ------------------------------------------------------------------ #
    async def get_queue(self) -> QueueSnapshot:
        """Return the current queue split into active, queued and paused items.

        Live ``speed``/``eta``/``downloaded_bytes`` figures are read from the Redis
        progress snapshots written by the workers and layered over the database
        rows. When Redis is unavailable the snapshot is still returned, with
        ``progress_source="database"``, so the queue screen degrades to stale-but-
        correct progress instead of failing.

        Returns:
            A :class:`QueueSnapshot`. Active items are ordered by descending
            progress, queued items by descending priority then ascending position.
        """
        result = await self.db.execute(
            await self._owner_query(
                select(Download, QueueItem)
                .outerjoin(QueueItem, QueueItem.download_id == Download.id)
                .where(Download.status.notin_(_TERMINAL_STATUSES))
            )
        )
        rows: List[Tuple[Download, Optional[QueueItem]]] = result.all()

        active: List[QueueEntry] = []
        queued: List[QueueEntry] = []
        paused: List[QueueEntry] = []
        progress_source = "database"
        live_cache: Dict[str, Optional[dict]] = {}

        for download, queue_item in rows:
            snapshot = live_cache.get(download.id, ...)
            if snapshot is ...:
                snapshot = redis_client.read_progress(download.id)
                live_cache[download.id] = snapshot
                if snapshot:
                    progress_source = "redis"

            entry = self._to_queue_entry(download, queue_item, snapshot)

            if download.status in _ACTIVE_STATUSES:
                active.append(entry)
            elif download.status == DownloadStatus.PAUSED:
                paused.append(entry)
            else:
                queued.append(entry)

        active.sort(key=lambda item: (-(item.progress or 0.0), item.id))
        # Highest priority first; position is the tiebreaker so an explicit
        # reordering is honoured among equally prioritised items.
        queued.sort(key=lambda item: (-(item.priority or 0), item.position, item.id))

        return QueueSnapshot(
            active=active,
            queued=queued,
            paused=paused,
            active_count=len(active),
            queued_count=len(queued),
            paused_count=len(paused),
            max_concurrent=settings.MAX_CONCURRENT_DOWNLOADS,
            progress_source=progress_source,
        )

    def _to_queue_entry(
        self,
        download: Download,
        queue_item: Optional[QueueItem],
        snapshot: Optional[dict],
    ) -> QueueEntry:
        """Project a download (plus optional live metrics) into a queue entry.

        The database holds the durable progress; the Redis snapshot is layered on
        top when present, since it updates far more often than the row is written.
        """
        progress = float(download.progress or 0.0)
        speed: Optional[float] = None
        eta: Optional[int] = None
        downloaded_bytes = 0
        total_bytes: Optional[int] = None

        if snapshot:
            progress = float(snapshot.get("progress", progress) or 0.0)
            raw_speed = snapshot.get("speed")
            speed = float(raw_speed) if isinstance(raw_speed, (int, float)) else None
            raw_eta = snapshot.get("eta")
            eta = int(raw_eta) if isinstance(raw_eta, (int, float)) else None
            downloaded_bytes = int(snapshot.get("downloaded_bytes") or 0)
            raw_total = snapshot.get("total_bytes")
            total_bytes = int(raw_total) if isinstance(raw_total, (int, float)) else None

        status_value = download.status.value if isinstance(download.status, DownloadStatus) else str(download.status)

        return QueueEntry(
            id=download.id,
            title=download.title,
            url=download.url,
            platform=download.platform,
            content_type=download.content_type,
            thumbnail_url=download.thumbnail_url,
            thumbnail_local=download.thumbnail_local,
            status=status_value,
            progress=progress,
            position=int(queue_item.position) if queue_item and queue_item.position is not None else 0,
            priority=int(queue_item.priority) if queue_item and queue_item.priority is not None else 0,
            speed=speed,
            eta=eta,
            downloaded_bytes=downloaded_bytes,
            total_bytes=total_bytes,
            error_message=download.error_message,
            processing_error=download.processing_error,
            processed=bool(download.processed),
            is_active=download.status in _ACTIVE_STATUSES,
            celery_task_id=download.celery_task_id,
        )

    # ------------------------------------------------------------------ #
    # Reordering
    # ------------------------------------------------------------------ #
    async def prioritize(self, download_id: str) -> QueueEntry:
        """Move a download to the front of the queue.

        The item is given the highest priority in the queue and position 0, and
        every other queued item is renumbered so positions stay dense and
        consecutive. Renumbering is what makes "move to front" actually work: the
        worker dispatches in position order, so without it a single row set to 0
        would tie with the previous front item.

        Args:
            download_id: Download to move.

        Returns:
            The updated :class:`QueueEntry`.

        Raises:
            DownloadNotFound: If the record does not exist.
            InvalidTransition: If the download is not in the queue because it is
                active or already finished.
        """
        download = await self._get_download(download_id)

        if download.status in _ACTIVE_STATUSES or download.status in _TERMINAL_STATUSES:
            raise InvalidTransition(
                f"Download {download_id} is {download.status.value if isinstance(download.status, DownloadStatus) else download.status} and cannot be requeued"
            )

        queue_item = await self._get_or_create_queue_item(download_id)
        queue_item.priority = await self._max_priority() + 1
        queue_item.position = 0
        queue_item.status = "queued"

        # Renumber the rest, skipping the promoted item so it keeps position 0.
        others_result = await self.db.execute(
            select(QueueItem)
            .join(Download, Download.id == QueueItem.download_id)
            .where(
                QueueItem.id != queue_item.id,
                Download.status.in_([DownloadStatus.PENDING, DownloadStatus.PAUSED]),
            )
            .order_by(QueueItem.priority.desc(), QueueItem.position.asc())
        )
        position = 1
        for other in others_result.scalars().all():
            other.position = position
            position += 1

        if download.status == DownloadStatus.PAUSED:
            redis_client.clear_pause(download_id)
            download.status = DownloadStatus.PENDING

        await self.db.commit()

        return QueueEntry(
            id=download.id,
            title=download.title,
            url=download.url,
            platform=download.platform,
            content_type=download.content_type,
            thumbnail_url=download.thumbnail_url,
            thumbnail_local=download.thumbnail_local,
            status=download.status.value if isinstance(download.status, DownloadStatus) else str(download.status),
            progress=float(download.progress or 0.0),
            position=0,
            priority=queue_item.priority,
            error_message=download.error_message,
            processing_error=download.processing_error,
            processed=bool(download.processed),
            is_active=False,
            celery_task_id=download.celery_task_id,
        )

    # ------------------------------------------------------------------ #
    # Pause / resume
    # ------------------------------------------------------------------ #
    async def pause_download(self, download_id: str) -> DownloadActionResult:
        """Pause a single in-flight or queued download.

        For an active download this writes the ``pause:{id}`` Redis flag, which the
        worker's progress callback checks between chunks; the worker then suspends
        itself and marks the row ``paused``, so the endpoint returns before the
        worker has actually stopped. For a queued download, setting the row to
        ``paused`` is enough because no worker holds it.

        Args:
            download_id: Download to pause.

        Returns:
            A :class:`DownloadActionResult` describing the new status.

        Raises:
            DownloadNotFound: If the record does not exist.
            InvalidTransition: If the download is finished or already paused.
            QueueError: If Redis is unavailable, because a pause the user can see
                acknowledged but that never reaches the worker is worse than a
                visible failure.
        """
        download = await self._get_download(download_id)
        status = self._status_value(download)

        if status in ("completed", "failed", "cancelled"):
            raise InvalidTransition(f"Cannot pause a download with status '{status}'")
        if status == "paused":
            return DownloadActionResult(
                id=download.id, status="paused", message="Download is already paused"
            )

        flag_set = redis_client.request_pause(download_id)
        if not flag_set:
            raise QueueError(
                "Cannot pause the download: the pause signal store is unreachable"
            )

        download.status = DownloadStatus.PAUSED
        await self.db.commit()

        message = (
            "Pause requested; the download will stop at the next chunk"
            if status == "downloading"
            else "Download paused"
        )
        return DownloadActionResult(id=download.id, status="paused", message=message)

    async def resume_download(self, download_id: str) -> DownloadActionResult:
        """Resume a paused download by re-dispatching it with continuation enabled.

        The pause flag is cleared by :meth:`dispatch` before the task starts, and the
        task runs yt-dlp with ``continuedl`` so it picks up the partial ``.part``
        file instead of starting over.

        Args:
            download_id: Download to resume.

        Returns:
            A :class:`DownloadActionResult` including the new Celery task ID.

        Raises:
            DownloadNotFound: If the record does not exist.
            InvalidTransition: If the download is not paused or failed.
            DispatchUnavailable: If the broker could not be reached.
        """
        download = await self._get_download(download_id)
        status = self._status_value(download)

        if status not in ("paused", "failed"):
            raise InvalidTransition(
                f"Cannot resume a download with status '{status}'"
            )

        # Nothing is mutated before dispatching: dispatch() flips the row to PENDING
        # and commits only once the broker has accepted the task. That ordering is
        # what guarantees a broker outage cannot leave a row marked as running when
        # no worker holds it, and it means no rollback is needed on failure.
        task_id = await self.dispatch(download_id, resume=True)

        # Clear the stale failure reason now that the retry is under way.
        download = await self._get_download(download_id)
        download.error_message = None
        await self.db.commit()

        return DownloadActionResult(
            id=download_id,
            status=self._status_value(download),
            message="Download resumed",
            celery_task_id=task_id,
        )

    async def pause_all(self) -> QueueActionResult:
        """Pause every active and queued download.

        Each active download needs a ``pause:{id}`` Redis flag for its worker to
        notice; queued downloads are simply moved out of the running state. A
        download whose flag could not be written is left untouched, so a Redis
        outage pauses the queued items and reports the active ones it could not
        signal rather than falsely claiming the whole queue stopped.

        Returns:
            A :class:`QueueActionResult` whose ``affected`` count is the number of
            downloads whose status changed.
        """
        result = await self.db.execute(
            await self._owner_query(
                select(Download).where(
                    Download.status.in_(_ACTIVE_STATUSES + (DownloadStatus.PENDING,))
                )
            )
        )
        downloads: List[Download] = list(result.scalars().all())

        paused_ids: List[str] = []
        for download in downloads:
            if download.status in _ACTIVE_STATUSES and not redis_client.request_pause(download.id):
                logger.warning("Could not signal pause for active download %s", download.id)
                continue
            download.status = DownloadStatus.PAUSED
            paused_ids.append(download.id)

        if paused_ids:
            await self.db.commit()

        return QueueActionResult(
            affected=len(paused_ids),
            message=f"Paused {len(paused_ids)} of {len(downloads)} active/queued downloads",
        )

    async def resume_all(self) -> QueueActionResult:
        """Resume every paused download.

        Returns:
            A :class:`QueueActionResult` reporting how many downloads were
            re-dispatched. Items the broker refused are counted and reported; their
            status is rolled back to ``paused`` so the UI does not show a download
            as pending that nothing is running.
        """
        result = await self.db.execute(
            await self._owner_query(
                select(Download).where(Download.status == DownloadStatus.PAUSED)
            )
        )
        paused: List[Download] = list(result.scalars().all())
        if not paused:
            return QueueActionResult(affected=0, message="No paused downloads to resume")

        resumed = 0
        failed: List[str] = []
        for download in paused:
            redis_client.clear_pause(download.id)
            download.status = DownloadStatus.PENDING
            await self.db.commit()
            try:
                await self.dispatch(download.id, resume=True)
            except DispatchUnavailable as exc:
                logger.warning("Could not resume download %s: %s", download.id, exc)
                download.status = DownloadStatus.PAUSED
                await self.db.commit()
                failed.append(download.id)
                continue
            resumed += 1

        message = f"Resumed {resumed} paused downloads"
        if failed:
            message += f"; {len(failed)} could not be dispatched"
        return QueueActionResult(affected=resumed, message=message)

    # ------------------------------------------------------------------ #
    # Download creation with dedup check
    # ------------------------------------------------------------------ #
    async def create_download(
        self,
        url: str,
        *,
        force: bool = False,
        platform: Optional[str] = None,
    ) -> Download:
        """Create a new download record, checking for duplicates first.

        Args:
            url: Source URL to download.
            force: When ``True`` skip duplicate detection.
            platform: Optional platform override.

        Returns:
            The persisted :class:`Download` row.

        Raises:
            DuplicateFoundError: If dedup is enabled, ``force`` is ``False``, and
                one or more near-duplicate downloads already exist.
        """
        if getattr(settings, "DEDUP_ENABLED", False) and not force:
            from app.services.ai.dedup import DedupEngine

            dedup = DedupEngine(self.db)
            matches = await dedup.check_url(url)
            if matches:
                raise DuplicateFoundError(
                    matches=[m.to_dict() for m in matches],
                    detail=f"Duplicate detected: {len(matches)} similar download(s) found",
                )

        tenant_id = getattr(self.current_user, "tenant_id", None) if self.current_user else None
        if tenant_id:
            from app.services.billing.quota_service import QuotaService
            quota = QuotaService(self.db)
            check = await quota.can_create_download(tenant_id)
            if not check.allowed:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=check.reason,
                )

        download = Download(
            url=url,
            platform=platform or self._detect_platform(url),
            content_type="video",
            title=url,
            status=DownloadStatus.PENDING,
            owner_id=self.current_user.id if self.current_user else None,
            tenant_id=tenant_id,
        )
        self.db.add(download)
        await self.db.flush()

        await self.enqueue_download(download, dispatch=False)
        await self.db.commit()
        await self.db.refresh(download)
        
        # Now dispatch after commit so the fallback thread can see the download
        await self.dispatch(download.id)
        
        return download

    @staticmethod
    def _detect_platform(url: str) -> str:
        """Best-effort platform detection from URL."""
        lower = url.lower()
        for platform in settings.ALLOWED_PLATFORMS:
            if platform in lower:
                return platform
        return "unknown"

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _get_download(self, download_id: str) -> Download:
        """Fetch a download row or raise :class:`DownloadNotFound`."""
        result = await self.db.execute(
            await self._owner_query(select(Download).where(Download.id == download_id))
        )
        download = result.scalars().first()
        if download is None:
            raise DownloadNotFound(f"Download not found: {download_id}")
        return download

    async def _get_or_create_queue_item(self, download_id: str) -> QueueItem:
        """Return the queue row for a download, creating it if absent."""
        result = await self.db.execute(
            select(QueueItem).where(QueueItem.download_id == download_id)
        )
        queue_item = result.scalars().first()
        if queue_item is None:
            queue_item = QueueItem(download_id=download_id, position=0, priority=0, status="queued")
            self.db.add(queue_item)
            await self.db.flush()
        return queue_item

    async def _next_position(self) -> int:
        """Return the next free queue position."""
        current = await self.db.scalar(select(func.max(QueueItem.position)))
        return 0 if current is None else int(current) + 1

    async def _max_priority(self) -> int:
        """Return the highest priority currently in use."""
        current = await self.db.scalar(select(func.max(QueueItem.priority)))
        return 0 if current is None else int(current)

    @staticmethod
    def _status_value(download: Download) -> str:
        """Return a download's status as a plain string."""
        status = download.status
        return status.value if isinstance(status, DownloadStatus) else str(status)