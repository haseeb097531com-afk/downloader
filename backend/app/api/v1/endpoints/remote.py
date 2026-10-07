"""Remote control endpoints for Phase 19.

Exposes a restricted surface for paired mobile devices under ``/api/v1/remote``.
All remote endpoints require a valid device token and respect the device's
permission set. Admin-only device management lives under ``/api/v1/devices``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import shutil
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user, require_feature, require_role
from app.api.deps_device import get_current_device, require_permission
from app.core.config import settings
from app.core import redis_client
from app.core.rate_limit import rate_limit, RateLimiter
from app.db.database import get_db
from app.models.device import Device, DevicePermission
from app.models.download import Download, DownloadStatus
from app.models.download_queue import QueueItem
from app.models.pending_link import PendingLink
from app.models.profile import Profile
from app.models.user import User
from app.services.downloader.download_orchestrator import (
    DownloadOrchestrator,
    DownloadNotFound,
    InvalidTransition,
    QueueError,
)
from app.services.scraper.profile_scraper import ProfileScraper
from app.services.storage.file_manager import FileManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remote", tags=["Remote"], dependencies=[Depends(require_feature("remote"))])

# ------------------------------------------------------------------ #
# Rate limit helpers
# ------------------------------------------------------------------ #

_PAIR_LIMITER = RateLimiter(requests=5, window_seconds=60)
_DEVICE_LIMITER = RateLimiter(requests=60, window_seconds=60)


def _device_rate_limit(device: Device) -> None:
    key = f"ratelimit:device:{device.token_hash}"
    allowed, retry_after = _DEVICE_LIMITER.is_allowed(key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for device",
            headers={"Retry-After": str(retry_after)},
        )


def device_dep(permissions: tuple[str, ...] = ()) -> Callable[[], Device]:
    """Return a dependency that resolves the device and enforces rate limiting."""
    perms = permissions

    async def _resolve(
        device: Device = Depends(require_permission(*perms) if perms else get_current_device),
    ) -> Device:
        _device_rate_limit(device)
        return device

    return _resolve

# ------------------------------------------------------------------ #
# Schemas
# ------------------------------------------------------------------ #

class PairRequest(BaseModel):
    code: str = Field(..., description="Pairing code from the desktop")
    name: Optional[str] = Field(None, description="Friendly device name")


class PairResponse(BaseModel):
    deviceId: str
    token: str
    permissions: list[str]
    name: str


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Media URL to download")
    quality: Optional[str] = Field(None, description="Preferred quality")
    start_time: Optional[str] = Field(None, description="Start time for trim")
    end_time: Optional[str] = Field(None, description="End time for trim")


class ScrapeRequest(BaseModel):
    url: str = Field(..., description="Profile URL to scrape")
    limit: int = Field(50, description="Max videos to fetch")


class ClipboardSubmitRequest(BaseModel):
    text: str = Field(..., description="Clipboard text containing a media URL")


class DeviceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    permissions: list[str] = Field(default_factory=lambda: ["view"])


class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    permissions: Optional[list[str]] = Field(None)
    is_active: Optional[bool] = Field(None)


class DeviceResponse(BaseModel):
    id: str
    name: str
    platform_hint: Optional[str]
    permissions: list[str]
    is_active: bool
    last_seen_at: Optional[str]
    created_at: Optional[str]
    revoked_at: Optional[str]


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _device_to_response(device: Device) -> DeviceResponse:
    return DeviceResponse(
        id=str(device.id),
        name=device.name,
        platform_hint=device.platform_hint,
        permissions=device.permissions or [],
        is_active=device.is_active,
        last_seen_at=device.last_seen_at.isoformat() if device.last_seen_at else None,
        created_at=device.created_at.isoformat() if device.created_at else None,
        revoked_at=device.revoked_at.isoformat() if device.revoked_at else None,
    )


def _owner_filter_device(device: Device, query, model):
    if not getattr(settings, "AUTH_ENABLED", False):
        return query
    if device.owner_id is None:
        return query.where(model.id == None)  # noqa: E711
    owner_col = getattr(model, "owner_id", None)
    if owner_col is None:
        return query
    return query.where(owner_col == device.owner_id)


# ------------------------------------------------------------------ #
# Pairing
# ------------------------------------------------------------------ #

@router.post("/pair", response_model=PairResponse)
async def pair_device(
    payload: PairRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PairResponse:
    """Consume a pairing code and create a device token.

    Public endpoint called by the phone during setup.
    """
    from app.services.remote.pairing import consume_pairing_code

    result = await consume_pairing_code(payload.code, payload.name)
    return PairResponse(**result)


# ------------------------------------------------------------------ #
# Device info
# ------------------------------------------------------------------ #

@router.get("/me", response_model=DeviceResponse)
async def get_me(device: Device = Depends(device_dep())) -> DeviceResponse:
    """Return the current device's metadata."""
    return _device_to_response(device)


# ------------------------------------------------------------------ #
# Summary
# ------------------------------------------------------------------ #

@router.get("/summary")
async def get_summary(
    device: Device = Depends(device_dep()),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a compact dashboard summary for the remote UI."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    owner_q = lambda q: _owner_filter_device(device, q, Download)

    active_q = owner_q(select(func.count()).select_from(Download).where(Download.status == DownloadStatus.DOWNLOADING))
    queued_q = owner_q(select(func.count()).select_from(Download).where(Download.status == DownloadStatus.PENDING))
    paused_q = owner_q(select(func.count()).select_from(Download).where(Download.status == DownloadStatus.PAUSED))
    completed_today_q = owner_q(
        select(func.count())
        .select_from(Download)
        .where(Download.status == DownloadStatus.COMPLETED)
        .where(Download.completed_at >= today_start)
    )

    active_count = (await db.execute(active_q)).scalar() or 0
    queued_count = (await db.execute(queued_q)).scalar() or 0
    paused_count = (await db.execute(paused_q)).scalar() or 0
    completed_today = (await db.execute(completed_today_q)).scalar() or 0

    disk_free_gb = 0.0
    try:
        fm = FileManager()
        usage = shutil.disk_usage(fm.directory)
        disk_free_gb = round(usage.free / (1024 ** 3), 1)
    except Exception:
        pass

    return {
        "active": active_count,
        "queued": queued_count,
        "paused": paused_count,
        "completed_today": completed_today,
        "disk_free_gb": disk_free_gb,
        "guard_active": getattr(settings, "STORAGE_GUARD_ENABLED", False),
        "turbo_mode": getattr(settings, "TURBO_MODE", False),
        "current_speed_mbps": getattr(settings, "BANDWIDTH_LIMIT_MBPS", 0),
    }


# ------------------------------------------------------------------ #
# Queue (compact)
# ------------------------------------------------------------------ #

@router.get("/queue")
async def get_queue(
    device: Device = Depends(device_dep()),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a compact queue view for the remote UI."""
    orchestrator = DownloadOrchestrator(db, current_user=None)
    # We need to scope by device owner manually since orchestrator expects a User
    result = await db.execute(
        _owner_filter_device(
            device,
            select(Download, QueueItem)
            .outerjoin(QueueItem, QueueItem.download_id == Download.id)
            .where(Download.status.notin_(["completed", "failed", "cancelled"])),
            Download,
        )
    )
    rows = result.all()

    items = []
    for download, queue_item in rows:
        items.append({
            "id": str(download.id),
            "title": download.title,
            "status": download.status.value if hasattr(download.status, "value") else str(download.status),
            "progress": download.progress or 0.0,
            "position": queue_item.position if queue_item else 0,
        })

    return {"items": items}


# ------------------------------------------------------------------ #
# Recent
# ------------------------------------------------------------------ #

@router.get("/recent")
async def get_recent(
    device: Device = Depends(device_dep()),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return the last 15 completed downloads for the device owner."""
    result = await db.execute(
        _owner_filter_device(
            device,
            select(Download)
            .where(Download.status == DownloadStatus.COMPLETED)
            .order_by(Download.completed_at.desc().nullslast())
            .limit(15),
            Download,
        )
    )
    downloads = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "platform": d.platform,
            "completed_at": d.completed_at.isoformat() if d.completed_at else None,
        }
        for d in downloads
    ]


# ------------------------------------------------------------------ #
# Media formats listing
# ------------------------------------------------------------------ #

class FormatOption(BaseModel):
    format_id: str
    quality: str
    extension: str
    url: str
    file_size_estimate: Optional[int] = None
    is_watermark_free: bool = True
    resolution: Optional[str] = None
    codec: Optional[str] = None


class FormatsResponse(BaseModel):
    url: str
    formats: list[FormatOption]
    max_height: int


@router.get("/media/formats", response_model=FormatsResponse)
async def list_media_formats(
    url: str,
    device: Device = Depends(device_dep("scrape")),
) -> FormatsResponse:
    """Return available download formats for a media URL.

    The list is derived from yt-dlp extraction and includes every usable
    rendition (video, audio-only, merged). The ``max_height`` field lets the
    caller source-aware quality selection without guessing.
    """
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


# ------------------------------------------------------------------ #
# Downloads (control)
# ------------------------------------------------------------------ #

@router.post("/downloads", response_model=dict)
async def create_download(
    payload: DownloadRequest,
    device: Device = Depends(device_dep("control")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new download from the remote device."""
    if device.owner_id:
        from app.services.billing.quota_service import QuotaService
        quota = QuotaService(db)
        check = await quota.can_create_download(device.owner_id)
        if not check.allowed:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=check.reason,
            )

    orchestrator = DownloadOrchestrator(db, current_user=None)
    download = Download(
        url=payload.url,
        platform="unknown",
        content_type="video",
        title=payload.url,
        status=DownloadStatus.PENDING,
        owner_id=device.owner_id,
    )
    if payload.quality:
        download.quality = payload.quality
    if payload.start_time:
        download.trim_start = payload.start_time
    if payload.end_time:
        download.trim_end = payload.end_time

    db.add(download)
    await db.flush()

    await orchestrator.enqueue_download(download, dispatch=True)
    await db.commit()

    return {"download_id": str(download.id), "status": "queued"}


# ------------------------------------------------------------------ #
# Profiles (scrape)
# ------------------------------------------------------------------ #

@router.post("/profiles/scrape", response_model=dict)
async def scrape_profile(
    payload: ScrapeRequest,
    device: Device = Depends(device_dep("scrape")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Scrape a profile and return discovered videos."""
    scraper = ProfileScraper()
    try:
        result = await scraper.scrape_profile(db, payload.url, limit=payload.limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    videos = []
    for video in getattr(result, "videos", []):
        videos.append({
            "url": getattr(video, "video_url", ""),
            "title": getattr(video, "title", ""),
            "thumbnail_url": getattr(video, "thumbnail_url", ""),
        })

    return {"videos": videos}


# ------------------------------------------------------------------ #
# Queue actions
# ------------------------------------------------------------------ #

@router.post("/queue/pause-all")
async def pause_all(
    device: Device = Depends(device_dep("control")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Pause all active and queued downloads for the device owner."""
    from app.core.redis_client import set_pause_all

    result = await db.execute(
        _owner_filter_device(
            device,
            select(Download).where(
                Download.status.in_([DownloadStatus.DOWNLOADING, DownloadStatus.PROCESSING, DownloadStatus.PENDING])
            ),
            Download,
        )
    )
    downloads = result.scalars().all()
    set_pause_all()
    for d in downloads:
        d.status = DownloadStatus.PAUSED
    await db.commit()
    return {"affected": len(downloads)}


@router.post("/queue/resume-all")
async def resume_all(
    device: Device = Depends(device_dep("control")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resume all paused downloads for the device owner."""
    from app.core.redis_client import clear_pause_all

    result = await db.execute(
        _owner_filter_device(
            device,
            select(Download).where(Download.status == DownloadStatus.PAUSED),
            Download,
        )
    )
    downloads = result.scalars().all()
    clear_pause_all()
    orchestrator = DownloadOrchestrator(db, current_user=None)
    affected = 0
    for d in downloads:
        try:
            await orchestrator.resume_download(str(d.id))
            affected += 1
        except Exception as exc:
            logger.warning("Failed to resume download %s: %s", d.id, exc)
    return {"affected": affected}


# ------------------------------------------------------------------ #
# Single download actions
# ------------------------------------------------------------------ #

@router.post("/downloads/{id}/pause")
async def remote_pause_download(
    id: str,
    device: Device = Depends(device_dep("control")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Pause a single download."""
    result = await db.execute(
        _owner_filter_device(device, select(Download).where(Download.id == id), Download)
    )
    download = result.scalars().first()
    if download is None:
        raise HTTPException(status_code=404, detail="Download not found")

    orchestrator = DownloadOrchestrator(db, current_user=None)
    try:
        res = await orchestrator.pause_download(str(download.id))
        return {"status": res.status, "message": res.message}
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/downloads/{id}/resume")
async def remote_resume_download(
    id: str,
    device: Device = Depends(device_dep("control")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resume a single paused download."""
    result = await db.execute(
        _owner_filter_device(device, select(Download).where(Download.id == id), Download)
    )
    download = result.scalars().first()
    if download is None:
        raise HTTPException(status_code=404, detail="Download not found")

    orchestrator = DownloadOrchestrator(db, current_user=None)
    try:
        res = await orchestrator.resume_download(str(download.id))
        return {"status": res.status, "message": res.message, "celery_task_id": res.celery_task_id}
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/downloads/{id}/cancel")
async def remote_cancel_download(
    id: str,
    device: Device = Depends(device_dep("control")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a single download."""
    result = await db.execute(
        _owner_filter_device(device, select(Download).where(Download.id == id), Download)
    )
    download = result.scalars().first()
    if download is None:
        raise HTTPException(status_code=404, detail="Download not found")

    download.status = DownloadStatus.CANCELLED
    await db.commit()
    return {"status": "cancelled", "message": "Download cancelled"}


@router.post("/downloads/{id}/retry")
async def remote_retry_download(
    id: str,
    device: Device = Depends(device_dep("control")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retry a failed download."""
    result = await db.execute(
        _owner_filter_device(device, select(Download).where(Download.id == id), Download)
    )
    download = result.scalars().first()
    if download is None:
        raise HTTPException(status_code=404, detail="Download not found")

    download.status = DownloadStatus.PENDING
    download.error_message = None
    await db.commit()

    orchestrator = DownloadOrchestrator(db, current_user=None)
    try:
        await orchestrator.enqueue_download(download, dispatch=True)
        await db.commit()
        return {"status": "queued", "message": "Download retried"}
    except QueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ------------------------------------------------------------------ #
# Clipboard
# ------------------------------------------------------------------ #

@router.post("/clipboard/submit")
async def submit_clipboard(
    payload: ClipboardSubmitRequest,
    device: Device = Depends(device_dep("control")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit clipboard text as a pending link for later download."""
    link = PendingLink(
        url=payload.text,
        platform="unknown",
        status="pending",
        owner_id=device.owner_id,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return {"pending_link_id": str(link.id)}


# ------------------------------------------------------------------ #
# Device management (JWT/admin)
# ------------------------------------------------------------------ #

class DeviceIntentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    permissions: list[str] = Field(default_factory=lambda: ["view"])


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DeviceResponse]:
    """List all devices (no raw tokens)."""
    result = await db.execute(select(Device).order_by(Device.created_at.desc()))
    devices = result.scalars().all()
    return [_device_to_response(d) for d in devices]


@router.post("/devices/intent", response_model=dict)
async def create_device_intent(
    payload: DeviceIntentRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a pairing intent for the current user."""
    from app.services.remote.pairing import create_pairing_intent

    intent = create_pairing_intent(str(current_user.id), payload.name, payload.permissions)
    return intent


@router.patch("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    payload: DeviceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceResponse:
    """Update a device's name, permissions, or active status."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalars().first()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if payload.name is not None:
        device.name = payload.name
    if payload.permissions is not None:
        device.permissions = payload.permissions
    if payload.is_active is not None:
        device.is_active = payload.is_active

    await db.commit()
    await db.refresh(device)
    return _device_to_response(device)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a device by setting revoked_at."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalars().first()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    device.revoked_at = datetime.now(timezone.utc)
    device.is_active = False
    await db.commit()
