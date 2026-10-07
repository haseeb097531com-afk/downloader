"""AI analysis endpoints for Phase 10A."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import OwnerFilter, get_current_user, visible_users
from app.api.v1.deps import get_db
from app.core.config import settings
from app.models.video_analysis import AnalysisStatus, VideoAnalysis
from app.models.user import User
from app.schemas.settings import ProcessingSettings
from app.services.ai.analysis_pipeline import AnalysisPipeline

router = APIRouter(tags=["Analysis"])
logger = logging.getLogger(__name__)


@router.get("/analysis/{download_id}")
async def get_analysis(download_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    """Return the analysis record for a download, or 404 if none."""
    visible = await visible_users(current_user, db)
    result = await db.execute(
        OwnerFilter.apply(current_user, select(VideoAnalysis).where(VideoAnalysis.download_id == download_id), VideoAnalysis, visible_user_ids=visible)
    )
    analysis = result.scalars().first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {
        "id": str(analysis.id),
        "download_id": analysis.download_id,
        "status": analysis.status.value if hasattr(analysis.status, "value") else str(analysis.status),
        "language": analysis.language,
        "transcript_text": analysis.transcript_text,
        "srt_path": analysis.srt_path,
        "summary_text": analysis.summary_text,
        "keywords": analysis.keywords or [],
        "translated": analysis.translated or {},
        "error": analysis.error,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
    }


@router.post("/analysis/{download_id}/run")
async def run_analysis(download_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    """Enqueue an analysis task for ``download_id``."""
    visible = await visible_users(current_user, db)
    result = await db.execute(
        OwnerFilter.apply(current_user, select(VideoAnalysis).where(VideoAnalysis.download_id == download_id), VideoAnalysis, visible_user_ids=visible)
    )
    analysis = result.scalars().first()
    if analysis is None:
        analysis = VideoAnalysis(
            download_id=download_id,
            status=AnalysisStatus.PENDING,
            owner_id=current_user.id if current_user else None,
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)

    if analysis.status == AnalysisStatus.PROCESSING:
        return {"status": "processing", "analysis_id": str(analysis.id)}

    try:
        from app.workers.ai_tasks import analysis_task
        analysis_task.delay(download_id)
    except Exception as exc:
        logger.warning("Failed to enqueue analysis task: %s", exc)
        raise HTTPException(status_code=503, detail="Failed to enqueue analysis task") from exc

    return {"status": "queued", "analysis_id": str(analysis.id)}


@router.post("/analysis/{download_id}/translate")
async def translate_analysis(download_id: str, lang: str = Query(..., min_length=2, max_length=10), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    """Enqueue translation of the SRT into ``lang``."""
    visible = await visible_users(current_user, db)
    result = await db.execute(
        OwnerFilter.apply(current_user, select(VideoAnalysis).where(VideoAnalysis.download_id == download_id), VideoAnalysis, visible_user_ids=visible)
    )
    analysis = result.scalars().first()
    if analysis is None or not analysis.srt_path:
        raise HTTPException(status_code=404, detail="Analysis or SRT not found")

    try:
        from app.workers.ai_tasks import translation_task
        translation_task.delay(download_id, lang)
    except Exception as exc:
        logger.warning("Failed to enqueue translation task: %s", exc)
        raise HTTPException(status_code=503, detail="Failed to enqueue translation task") from exc

    return {"status": "queued", "analysis_id": str(analysis.id), "lang": lang}


@router.get("/analysis/{download_id}/content/{kind}")
async def get_analysis_content(download_id: str, kind: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    """Serve transcript, summary, or SRT content for a download."""
    visible = await visible_users(current_user, db)
    result = await db.execute(
        OwnerFilter.apply(current_user, select(VideoAnalysis).where(VideoAnalysis.download_id == download_id), VideoAnalysis, visible_user_ids=visible)
    )
    analysis = result.scalars().first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if kind == "transcript":
        return {"content": analysis.transcript_text or ""}
    if kind == "summary":
        return {"content": analysis.summary_text or ""}
    if kind == "srt":
        if not analysis.srt_path or not Path(analysis.srt_path).exists():
            raise HTTPException(status_code=404, detail="SRT not found")
        return {"content": Path(analysis.srt_path).read_text(encoding="utf-8")}
    raise HTTPException(status_code=400, detail="Invalid kind. Use transcript, summary, or srt")
