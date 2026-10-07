from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user, OwnerFilter
from app.db.database import get_db
from app.models.download import Download, DownloadStatus
from app.models.user import User
from app.schemas.library import ImportResult, LibraryItem, LibraryPage, LibraryStats, UntrackedFile
from app.services.storage.library_service import (
    DownloadNotFound,
    LibraryPathError,
    LibraryService,
)
from app.services.storage.storage_guard import get_disk_status

router = APIRouter(prefix="/library", tags=["Library"])


class CategorySummary(BaseModel):
    category: str = Field(..., description="Category name")
    count: int = Field(0, description="Number of completed downloads")
    total_size: int = Field(0, description="Combined size in bytes")


class RenameRequest(BaseModel):
    """Body of ``POST /library/{id}/rename``."""

    new_name: str = Field(..., min_length=1, max_length=255, description="New filename for the media file")


class ImportRequest(BaseModel):
    """Body of ``POST /library/import``."""

    file_paths: list[str] = Field(..., description="Absolute paths of untracked files to adopt")


def get_library_service(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LibraryService:
    """Build a :class:`LibraryService` for the request."""
    return LibraryService(db, current_user=current_user)


@router.get("", response_model=LibraryPage)
async def scan_library(
    page: int = Query(1, ge=1, description="1-based page number"),
    limit: int = Query(24, ge=1, le=200, description="Items per page"),
    platform: str | None = Query(None, description="Filter by platform, e.g. youtube"),
    search: str | None = Query(None, max_length=200, description="Case-insensitive title search"),
    category: str | None = Query(None, description="Filter by category"),
    service: LibraryService = Depends(get_library_service),
) -> LibraryPage:
    """Return a page of completed downloads, verified against disk."""
    return await service.scan_library(page=page, limit=limit, platform=platform, search=search, category=category)


@router.get("/stats", response_model=LibraryStats)
async def get_library_stats(
    service: LibraryService = Depends(get_library_service),
) -> LibraryStats:
    """Return library totals, per-platform breakdown, a 7-day chart and top creators."""
    return await service.get_library_stats()


@router.get("/categories", response_model=list[CategorySummary])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CategorySummary]:
    """Return category counts and total sizes for completed downloads."""
    query = (
        select(Download.category, func.count(Download.id), func.sum(Download.file_size))
        .where(Download.status == DownloadStatus.COMPLETED)
        .where(Download.category.is_not(None))
        .group_by(Download.category)
        .order_by(func.count(Download.id).desc())
    )
    visible = await visible_users(current_user, db)
    query = OwnerFilter.apply(current_user, query, Download, visible_user_ids=visible)
    result = await db.execute(query)
    rows = result.all()
    return [
        CategorySummary(category=row[0] or "Other", count=int(row[1] or 0), total_size=int(row[2] or 0))
        for row in rows
    ]


@router.get("/untracked", response_model=list[UntrackedFile])
async def list_untracked_files(
    service: LibraryService = Depends(get_library_service),
) -> list[UntrackedFile]:
    """List media files on disk that have no matching download record."""
    try:
        return await service.detect_untracked_files()
    except LibraryPathError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/import", response_model=ImportResult)
async def import_untracked_files(
    req: ImportRequest,
    service: LibraryService = Depends(get_library_service),
) -> ImportResult:
    """Adopt untracked files into the library by creating download records."""
    try:
        return await service.import_untracked_detailed(req.file_paths)
    except LibraryPathError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{id}/rename", response_model=LibraryItem)
async def rename_library_file(
    id: str,
    req: RenameRequest,
    service: LibraryService = Depends(get_library_service),
) -> LibraryItem:
    """Rename a media file on disk and update its title."""
    try:
        return await service.rename_file(id, req.new_name)
    except DownloadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LibraryPathError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{id}", status_code=204)
async def delete_library_file(
    id: str,
    service: LibraryService = Depends(get_library_service),
) -> None:
    """Delete a media file from disk and remove its database record."""
    try:
        await service.delete_media(id)
    except DownloadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LibraryPathError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{id}/open-folder")
async def open_library_folder(
    id: str,
    service: LibraryService = Depends(get_library_service),
) -> dict:
    """Reveal a media file in the operating system file manager."""
    try:
        await service.open_folder(id)
    except DownloadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LibraryPathError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"message": "Opened the containing folder"}
