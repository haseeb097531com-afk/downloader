"""Response schemas for download queue management.

Returned by :mod:`app.services.downloader.download_orchestrator` and the
``/api/v1/queue`` and ``/api/v1/downloads`` endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

__all__ = [
    "QueueEntry",
    "QueueSnapshot",
    "QueueActionResult",
    "DownloadActionResult",
]


class QueueEntry(BaseModel):
    """One item in the download queue, active or waiting."""

    id: str = Field(..., description="Download record ID")
    title: str = Field(..., description="Media title")
    url: str = Field(..., description="Source URL")
    platform: str = Field(..., description="Source platform")
    content_type: str = Field(..., description="Either 'video' or 'audio'")
    thumbnail_url: Optional[str] = Field(None, description="Poster/thumbnail URL")
    thumbnail_local: Optional[str] = Field(None, description="Local thumbnail path")
    status: str = Field(..., description="Current download status")
    progress: float = Field(0.0, description="Progress percentage from 0 to 100")
    position: int = Field(0, description="Queue position; 0 is the next item to run")
    priority: int = Field(0, description="Higher values are dispatched first")
    speed: Optional[float] = Field(None, description="Current throughput in bytes per second")
    eta: Optional[int] = Field(None, description="Estimated seconds remaining")
    downloaded_bytes: int = Field(0, description="Bytes transferred so far")
    total_bytes: Optional[int] = Field(None, description="Expected total size in bytes, when known")
    error_message: Optional[str] = Field(None, description="Failure reason, when status is 'failed'")
    processing_error: Optional[str] = Field(None, description="Post-processing warning, when applicable")
    processed: bool = Field(False, description="True when post-processing completed successfully")
    is_active: bool = Field(False, description="True when a worker is currently transferring this item")
    celery_task_id: Optional[str] = Field(None, description="Celery task ID running this download")


class QueueSnapshot(BaseModel):
    """Current state of the download queue."""

    active: List[QueueEntry] = Field(default_factory=list, description="Downloads currently transferring")
    queued: List[QueueEntry] = Field(default_factory=list, description="Downloads waiting to start, in dispatch order")
    paused: List[QueueEntry] = Field(default_factory=list, description="Downloads suspended by the user")
    active_count: int = Field(0, description="Number of active downloads")
    queued_count: int = Field(0, description="Number of queued downloads")
    paused_count: int = Field(0, description="Number of paused downloads")
    max_concurrent: int = Field(0, description="Configured concurrency limit")
    progress_source: str = Field("database", description="'redis' when live metrics were available, else 'database'")


class QueueActionResult(BaseModel):
    """Result of a bulk queue action such as pause-all or resume-all."""

    affected: int = Field(0, description="Number of items the action was applied to")
    message: str = Field("", description="Human-readable summary")


class DownloadActionResult(BaseModel):
    """Result of a single-download action such as pause, resume or cancel."""

    id: str = Field(..., description="Download record ID")
    status: str = Field(..., description="Status after the action")
    message: str = Field("", description="Human-readable summary")
    celery_task_id: Optional[str] = Field(None, description="Task ID of the re-dispatched download, when resumed")