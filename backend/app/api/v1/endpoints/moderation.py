"""Content moderation, safe mode and parental control endpoints."""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import OwnerFilter, get_current_user, require_feature, visible_users
from app.core.config import settings
from app.core.settings_service import SettingsService
from app.db.database import get_db
from app.models.download import Download, DownloadStatus
from app.models.user import User
from app.schemas.settings import ProcessingSettings
from app.services.moderator import ContentModerator

router = APIRouter(prefix="/moderation", tags=["Moderation"], dependencies=[Depends(require_feature("safety"))])
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Settings
# ------------------------------------------------------------------ #

class ModerationSettings(BaseModel):
    safe_mode: bool = False
    keyword_blacklist: List[str] = []
    moderation_sensitivity: float = 0.5


class SetPinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit parental control PIN")


class VerifyPinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit parental control PIN")


class RestoreRequest(BaseModel):
    pass


@router.get("/settings", response_model=ModerationSettings)
async def read_moderation_settings() -> ModerationSettings:
    svc = SettingsService()
    data = svc.get_settings()
    return ModerationSettings(
        safe_mode=bool(data.get("safe_mode", False)),
        keyword_blacklist=list(data.get("keyword_blacklist", [])),
        moderation_sensitivity=float(data.get("moderation_sensitivity", 0.5)),
    )


@router.put("/settings", response_model=ModerationSettings)
async def update_moderation_settings(payload: ModerationSettings) -> ModerationSettings:
    svc = SettingsService()
    data = svc.update_settings({
        "safe_mode": payload.safe_mode,
        "keyword_blacklist": payload.keyword_blacklist,
        "moderation_sensitivity": payload.moderation_sensitivity,
    })
    return ModerationSettings(
        safe_mode=bool(data.get("safe_mode", False)),
        keyword_blacklist=list(data.get("keyword_blacklist", [])),
        moderation_sensitivity=float(data.get("moderation_sensitivity", 0.5)),
    )


# ------------------------------------------------------------------ #
# PIN management
# ------------------------------------------------------------------ #

@router.post("/set-pin")
async def set_parental_pin(req: SetPinRequest) -> dict:
    if not re.fullmatch(r"\d{4}", req.pin):
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    pin_hash = ContentModerator.hash_pin(req.pin)
    svc = SettingsService()
    svc.update_settings({"pin_hash": pin_hash})
    return {"message": "PIN set successfully"}


@router.post("/verify-pin")
async def verify_parental_pin(req: VerifyPinRequest) -> dict:
    svc = SettingsService()
    data = svc.get_settings()
    pin_hash = data.get("pin_hash", "")
    if not pin_hash:
        raise HTTPException(status_code=400, detail="No PIN has been set")
    valid = ContentModerator.verify_pin(req.pin, pin_hash)
    return {"valid": valid}


# ------------------------------------------------------------------ #
# Quarantine management
# ------------------------------------------------------------------ #

class QuarantinedItem(BaseModel):
    id: str
    title: str
    platform: str
    file_path: str
    quarantine_reason: str | None
    created_at: str | None


class RestoreResult(BaseModel):
    message: str


class PurgeResult(BaseModel):
    message: str


@router.get("/quarantined", response_model=List[QuarantinedItem])
async def list_quarantined(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> List[QuarantinedItem]:
    query = select(Download)
    if getattr(settings, "AUTH_ENABLED", False):
        visible = await visible_users(current_user, db)
        query = OwnerFilter.apply(current_user, query, Download, visible_user_ids=visible)
    result = await db.execute(
        query
        .where(Download.status == DownloadStatus.COMPLETED)
        .where(Download.quarantined.is_(True))
        .order_by(Download.created_at.desc().nullslast())
    )
    downloads = result.scalars().all()
    return [
        QuarantinedItem(
            id=d.id,
            title=d.title or "",
            platform=d.platform or "",
            file_path=d.file_path or "",
            quarantine_reason=d.quarantine_reason,
            created_at=d.created_at.isoformat() if d.created_at else None,
        )
        for d in downloads
    ]


@router.post("/{id}/restore", response_model=RestoreResult)
async def restore_quarantined(id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> RestoreResult:
    visible = await visible_users(current_user, db)
    result = await db.execute(
        OwnerFilter.apply(current_user, select(Download).where(Download.id == id), Download, visible_user_ids=visible)
    )
    download = result.scalars().first()
    if download is None:
        raise HTTPException(status_code=404, detail="Download not found")
    if not download.quarantined:
        raise HTTPException(status_code=400, detail="Download is not quarantined")

    src = Path(download.file_path) if download.file_path else None
    if src and src.exists():
        platform = download.platform or "unknown"
        dest_dir = Path(settings.DOWNLOAD_DIR) / platform
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        try:
            shutil.move(str(src), str(dest))
            download.file_path = str(dest)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to restore file: {exc}") from exc
    else:
        pass

    download.quarantined = False
    download.quarantine_reason = None
    await db.commit()
    return RestoreResult(message="Download restored successfully")


@router.post("/{id}/purge", response_model=PurgeResult)
async def purge_quarantined(id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> PurgeResult:
    visible = await visible_users(current_user, db)
    result = await db.execute(
        OwnerFilter.apply(current_user, select(Download).where(Download.id == id), Download, visible_user_ids=visible)
    )
    download = result.scalars().first()
    if download is None:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.file_path:
        try:
            os.remove(download.file_path)
        except OSError:
            pass

    await db.delete(download)
    await db.commit()
    return PurgeResult(message="Quarantined download purged successfully")
