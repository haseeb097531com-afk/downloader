"""Smart deduplication endpoints.

Exposes:
- ``GET /api/v1/dedup/check`` — pre-download duplicate check
- ``POST /api/v1/library/dedup-scan`` — enqueue background scan
- ``GET /api/v1/library/dedup-report`` — latest scan report
- ``POST /api/v1/library/dedup-cleanup`` — delete duplicate records
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user, visible_users
from app.api.v1.deps import get_orchestrator
from app.core import redis_client
from app.db.database import get_db
from app.models.download import Download, DownloadStatus
from app.models.media_fingerprint import MediaFingerprint
from app.schemas.library import LibraryItem
from app.services.ai.dedup import DedupEngine, DuplicateMatch
from app.services.downloader.download_orchestrator import (
    DownloadOrchestrator,
    DuplicateFoundError,
)
from app.services.storage.library_service import LibraryService

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# /api/v1/dedup/* — pre-download duplicate check
# ------------------------------------------------------------------ #
dedup_router = APIRouter(prefix="/dedup", tags=["Dedup"])


@dedup_router.get("/check")
async def check_url_duplicates(
    url: str = Query(..., description="Source URL to check for duplicates"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> list[dict]:
    """Return duplicate matches for ``url`` using its thumbnail phash."""
    engine = DedupEngine(db, current_user=current_user)
    try:
        matches = await engine.check_url(url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [m.to_dict() for m in matches]


# ------------------------------------------------------------------ #
# /api/v1/library/* — bulk dedup scan, report and cleanup
# ------------------------------------------------------------------ #
lib_router = APIRouter(prefix="/library", tags=["Library"])


@lib_router.post("/dedup-scan", status_code=202)
async def enqueue_dedup_scan() -> dict:
    """Enqueue a background scan that fingerprints all unfingerprinted downloads."""
    try:
        from app.workers.maintenance_tasks import dedup_scan_task

        dedup_scan_task.delay()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to enqueue scan: {exc}") from exc
    return {"message": "Dedup scan enqueued"}


@lib_router.get("/dedup-report")
async def get_dedup_report() -> list[dict[str, Any]]:
    """Return the latest dedup report from Redis (or empty list)."""
    try:
        from app.workers.maintenance_tasks import read_dedup_report

        report = read_dedup_report()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return report


@lib_router.post("/dedup-cleanup")
async def dedup_cleanup(
    delete_ids: list[str],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> dict:
    """Delete the specified duplicate downloads from disk and the database.

    Reuses :class:`~app.services.storage.library_service.LibraryService.delete_media`.
    """
    if not delete_ids:
        return {"deleted": 0}

    library = LibraryService(db, current_user=current_user)
    deleted = 0
    visible = await visible_users(current_user, db) if current_user else []
    for download_id in delete_ids:
        try:
            await library.delete_media(download_id)
            fingerprint_query = MediaFingerprint.__table__.delete().where(MediaFingerprint.download_id == download_id)
            if visible:
                fingerprint_query = fingerprint_query.where(MediaFingerprint.owner_id.in_(visible))
            await db.execute(fingerprint_query)
            deleted += 1
        except Exception as exc:
            logger.warning("Failed to delete duplicate %s: %s", download_id, exc)

    try:
        await db.commit()
    except Exception:
        await db.rollback()

    return {"deleted": deleted}
