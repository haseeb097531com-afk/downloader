"""Media metadata and format listing endpoints."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user
from app.api.deps_device import get_current_device
from app.db.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["Media"])


class FormatOption(BaseModel):
    format_id: str
    quality: str
    extension: str
    url: str
    file_size_estimate: int | None = None
    is_watermark_free: bool = True
    resolution: str | None = None
    codec: str | None = None


class FormatsResponse(BaseModel):
    url: str
    formats: list[FormatOption]
    max_height: int


@router.get("/formats", response_model=FormatsResponse)
async def list_media_formats(
    url: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FormatsResponse:
    """Return available download formats for a media URL."""
    from app.services.extractor.ytdlp_engine import YTDLPEngine, YTDLPEngineError

    engine = YTDLPEngine()
    try:
        info = engine.extract_info(url, download=False)
    except YTDLPEngineError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Extraction failed: {exc}") from exc

    raw_formats = info.get("formats", [])
    parsed = engine._parse_formats(raw_formats, info.get("extractor", ""))

    max_height = 0
    for f in parsed:
        try:
            h = int((f.resolution or "0"))
            if h > max_height:
                max_height = h
        except (ValueError, TypeError):
            pass

    return FormatsResponse(
        url=url,
        formats=[FormatOption(**f.model_dump()) for f in parsed],
        max_height=max_height,
    )
