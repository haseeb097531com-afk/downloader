"""Response schemas for the media library.

These are the service-layer result models returned by
:mod:`app.services.storage.library_service` and by the ``/api/v1/library``
endpoints. Request bodies stay local to their endpoint module, matching the
existing convention in ``app/api/v1/endpoints/profiles.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.download import DownloadStatus

__all__ = [
    "LibraryItem",
    "LibraryPage",
    "PlatformStat",
    "DailyDownloadCount",
    "CreatorStat",
    "LibraryStats",
    "UntrackedFile",
    "ImportResult",
]


class LibraryItem(BaseModel):
    """A single completed download as presented in the library grid."""

    id: str = Field(..., description="Download record ID")
    title: str = Field(..., description="Media title, shown in the library")
    platform: str = Field(..., description="Source platform, e.g. youtube")
    content_type: str = Field(..., description="Either 'video' or 'audio'")
    file_path: Optional[str] = Field(None, description="Absolute path of the media file")
    file_size: int = Field(0, description="Size of the file in bytes")
    thumbnail_url: Optional[str] = Field(None, description="Poster/thumbnail URL")
    thumbnail_local: Optional[str] = Field(None, description="Path to locally generated thumbnail")
    is_watermark_free: bool = Field(False, description="Whether the media has no watermark")
    completed_at: Optional[datetime] = Field(None, description="When the download finished")
    exists_on_disk: bool = Field(True, description="False when the file was deleted outside the app")
    processed: bool = Field(False, description="True when post-processing completed successfully")
    status: str = Field(..., description="Current download status")
    progress: float = Field(0.0, description="Progress percentage")
    category: Optional[str] = Field(None, description="Auto-detected content category")

    @classmethod
    def from_download(cls, download, *, exists_on_disk: bool = True, file_size: int = 0) -> "LibraryItem":
        """Build an item from a :class:`~app.models.download.Download` row.

        Args:
            download: The ORM row to project.
            exists_on_disk: Result of the FileManager existence check. A record whose
                file has vanished is still returned (flagged) rather than hidden, so
                the user can see and clean it up.
            file_size: Size read from disk, falling back to the value recorded at
                download time when the file is gone.

        Returns:
            The populated :class:`LibraryItem`.
        """
        return cls(
            id=download.id,
            title=download.title,
            platform=download.platform,
            content_type=download.content_type,
            file_path=download.file_path,
            file_size=file_size if exists_on_disk else int(download.file_size or 0),
            thumbnail_url=download.thumbnail_url,
            thumbnail_local=download.thumbnail_local,
            is_watermark_free=bool(download.is_watermark_free),
            completed_at=download.completed_at,
            exists_on_disk=exists_on_disk,
            processed=bool(download.processed),
            status=download.status.value if isinstance(download.status, DownloadStatus) else str(download.status),
            progress=float(download.progress or 0.0),
            category=download.category,
        )


class LibraryPage(BaseModel):
    """One page of library items plus the pagination state for the frontend."""

    items: List[LibraryItem] = Field(default_factory=list, description="Items on this page")
    page: int = Field(1, description="1-based page number")
    limit: int = Field(24, description="Items per page")
    total: int = Field(0, description="Total items matching the filters")
    total_pages: int = Field(0, description="Total number of pages available")
    has_next: bool = Field(False, description="Whether a next page exists")


class PlatformStat(BaseModel):
    """Per-platform aggregate used by the library stats cards."""

    platform: str = Field(..., description="Platform name")
    count: int = Field(0, description="Number of completed downloads")
    total_size: int = Field(0, description="Combined size of those downloads in bytes")


class DailyDownloadCount(BaseModel):
    """One bucket of the "downloads last 7 days" mini chart."""

    date: str = Field(..., description="ISO date (YYYY-MM-DD) for the day")
    count: int = Field(0, description="Downloads completed that day")


class CreatorStat(BaseModel):
    """A uploader ranked by how much of the library they account for."""

    username: str = Field(..., description="Uploader / creator username")
    count: int = Field(0, description="Number of completed downloads by this creator")


class LibraryStats(BaseModel):
    """Aggregate library metrics for the dashboard header."""

    total_files: int = Field(0, description="Number of completed downloads")
    total_size_bytes: int = Field(0, description="Combined size in bytes")
    missing_files: int = Field(0, description="Records whose file no longer exists on disk")
    platform_breakdown: List[PlatformStat] = Field(default_factory=list, description="Per-platform totals")
    downloads_last_7_days: List[DailyDownloadCount] = Field(default_factory=list, description="Daily counts, oldest first")
    top_creators: List[CreatorStat] = Field(default_factory=list, description="Up to 5 most-downloaded creators")


class UntrackedFile(BaseModel):
    """A media file on disk that has no matching download record."""

    path: str = Field(..., description="Absolute path of the untracked file")
    filename: str = Field(..., description="File name including extension")
    extension: str = Field(..., description="Lower-case extension, e.g. '.mp4'")
    file_size: int = Field(0, description="Size in bytes")
    modified_at: Optional[datetime] = Field(None, description="Last modification time")
    platform: str = Field("unknown", description="Platform inferred from the parent directory")
    content_type: str = Field("video", description="Either 'video' or 'audio'")
    modified_since_sync: bool = Field(False, description="True when the file changed after it was detected")


class ImportResult(BaseModel):
    """Summary returned by ``POST /library/import``."""

    imported: int = Field(0, description="Number of download records created")
    skipped: int = Field(0, description="Paths rejected as unsafe, unknown or already tracked")
    total_size_bytes: int = Field(0, description="Combined size of the imported files in bytes")
    errors: List[str] = Field(default_factory=list, description="Human-readable reason per rejected path")