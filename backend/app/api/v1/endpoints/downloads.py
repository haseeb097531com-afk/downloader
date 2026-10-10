"""Per-download control endpoints.

Pause and resume a single download. Both go through
:class:`~app.services.downloader.download_orchestrator.DownloadOrchestrator`, the
same path the queue bulk actions use, so a single download and the whole queue
share one implementation of the ordering and Redis-flag logic.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.deps import get_orchestrator
from app.schemas.queue import DownloadActionResult
from app.services.downloader.download_orchestrator import (
    DownloadNotFound,
    InvalidTransition,
    QueueError,
)

router = APIRouter(prefix="/downloads", tags=["Downloads"])

from pydantic import BaseModel
from typing import Optional

class CreateDownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    force: bool = False

@router.post("", response_model=dict)
async def create_download(
    payload: CreateDownloadRequest,
    orchestrator=Depends(get_orchestrator),
):
    try:
        download = await orchestrator.create_download(
            url=payload.url,
            force=payload.force
        )
        if payload.quality:
            download.quality = payload.quality
        if payload.start_time:
            download.trim_start = payload.start_time
        if payload.end_time:
            download.trim_end = payload.end_time
        await orchestrator.db.commit()
        return {"id": str(download.id), "status": "queued"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{id}/pause", response_model=DownloadActionResult)
async def pause_download(
    id: str,
    orchestrator=Depends(get_orchestrator),
) -> DownloadActionResult:
    """Pause one download.

    Writes the ``pause:{id}`` Redis flag for the worker to observe and moves the row
    to ``paused``. For an active download the transfer stops at the next chunk, so
    the response can arrive slightly before the worker actually suspends.

    Raises:
        404: No download with that ID.
        409: The download is finished or already paused.
        503: Redis was unreachable, so the pause could not be signalled.
    """
    try:
        return await orchestrator.pause_download(id)
    except DownloadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/{id}/resume", response_model=DownloadActionResult)
async def resume_download(
    id: str,
    orchestrator=Depends(get_orchestrator),
) -> DownloadActionResult:
    """Resume one paused download.

    Clears the pause flag and re-dispatches the Celery task with continuation
    enabled, so yt-dlp resumes the partial ``.part`` file instead of restarting.

    Raises:
        404: No download with that ID.
        409: The download is not in a resumable state.
        503: The broker was unreachable, so the download was left paused.
    """
    try:
        return await orchestrator.resume_download(id)
    except DownloadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))