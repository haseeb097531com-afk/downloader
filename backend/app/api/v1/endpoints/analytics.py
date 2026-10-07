"""Analytics and export endpoints for Phase 15A."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user, require_feature, visible_users
from app.db.database import get_db
from app.schemas.analytics import (
    CategoryStorage,
    CreatorStat,
    ExportCsvResponse,
    ExportFilters,
    ExportPdfRequest,
    OverviewStats,
    TimelineEntry,
)
from app.services.analytics.analytics_service import AnalyticsService
from app.services.analytics.export_service import ExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"], dependencies=[Depends(require_feature("analytics_basic"))])


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> OverviewStats:
    """Return high-level library analytics."""
    visible = await visible_users(current_user, db)
    service = AnalyticsService(db, visible_user_ids=visible)
    return await service.get_overview()


@router.get("/timeline", response_model=list[TimelineEntry])
async def get_timeline(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> list[TimelineEntry]:
    """Return daily download counts for the last N days."""
    visible = await visible_users(current_user, db)
    service = AnalyticsService(db, visible_user_ids=visible)
    return await service.get_timeline(days=days)


@router.get("/creators", response_model=list[CreatorStat])
async def get_top_creators(
    limit: int = Query(10, ge=1, le=100, description="Maximum creators to return"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> list[CreatorStat]:
    """Return the most-downloaded creators ranked by download count."""
    visible = await visible_users(current_user, db)
    service = AnalyticsService(db, visible_user_ids=visible)
    return await service.get_top_creators(limit=limit)


@router.get("/storage", response_model=list[CategoryStorage])
async def get_storage_heatmap(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> list[CategoryStorage]:
    """Return storage usage grouped by category."""
    visible = await visible_users(current_user, db)
    service = AnalyticsService(db, visible_user_ids=visible)
    return await service.get_storage_heatmap()


@router.post("/export/csv")
async def export_csv(
    filters: Optional[ExportFilters] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_feature("analytics_full")),
) -> Response:
    """Export download data as CSV.

    Accepts optional filters in the request body. Returns a CSV file download.
    """
    visible = await visible_users(current_user, db)
    service = ExportService(db, visible_user_ids=visible)
    try:
        csv_bytes = await service.export_csv(filters=filters)
    except Exception as exc:
        logger.error("CSV export failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate CSV export") from exc

    filename = f"mediavault_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        row_count = len(csv_bytes.decode("utf-8").strip().splitlines()) - 1
    except Exception:
        row_count = 0

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.post("/export/pdf")
async def export_pdf(
    payload: ExportPdfRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_feature("analytics_full")),
) -> Response:
    """Export an analytics report as PDF.

    ``report_type`` may be ``"overview"`` (summary stats) or ``"full"``
    (includes top creators and storage breakdown).
    """
    if payload.report_type not in ("overview", "full"):
        raise HTTPException(status_code=400, detail="report_type must be 'overview' or 'full'")

    visible = await visible_users(current_user, db)
    service = ExportService(db, visible_user_ids=visible)
    try:
        pdf_bytes = await service.export_pdf(report_type=payload.report_type)
    except Exception as exc:
        logger.error("PDF export failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate PDF export") from exc

    filename = f"mediavault_report_{payload.report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )
