"""Download queue management endpoints.

Covers the queue screen: what is running, what is waiting, reordering, and the
bulk pause/resume actions. All of it is delegated to
:class:`~app.services.downloader.download_orchestrator.DownloadOrchestrator`, which
owns the ordering rules and the Redis pause signalling.

Per-download controls live in ``downloads.py`` and are mounted at
``/api/v1/downloads/{id}/pause``: they act on a ``downloads`` primary key rather
than on a queue row, so they belong with that resource.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.deps import get_orchestrator
from app.schemas.queue import QueueActionResult, QueueEntry, QueueSnapshot
from app.services.downloader.download_orchestrator import (
    DownloadNotFound,
    InvalidTransition,
    QueueError,
)

router = APIRouter(prefix="/queue", tags=["Queue"])


@router.get("", response_model=QueueSnapshot)
async def get_queue(
    orchestrator=Depends(get_orchestrator),
) -> QueueSnapshot:
    """Return active, queued and paused downloads with live progress.

    Speed, ETA and downloaded-byte figures come from the Redis progress snapshots
    written by the workers; the database supplies the durable progress so the
    response is still useful when Redis is unreachable.
    """
    return await orchestrator.get_queue()


@router.post("/pause-all", response_model=QueueActionResult)
async def pause_all_downloads(
    orchestrator=Depends(get_orchestrator),
) -> QueueActionResult:
    """Pause every active and queued download and report how many were affected."""
    try:
        return await orchestrator.pause_all()
    except QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/resume-all", response_model=QueueActionResult)
async def resume_all_downloads(
    orchestrator=Depends(get_orchestrator),
) -> QueueActionResult:
    """Resume every paused download, re-dispatching each to a worker."""
    try:
        return await orchestrator.resume_all()
    except QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/{id}/prioritize", response_model=QueueEntry)
async def prioritize_download(
    id: str,
    orchestrator=Depends(get_orchestrator),
) -> QueueEntry:
    """Move a queued download to the front of the queue.

    Raises:
        404: No download with that ID.
        409: The download is already active or finished, so it cannot be requeued.
    """
    try:
        return await orchestrator.prioritize(id)
    except DownloadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))