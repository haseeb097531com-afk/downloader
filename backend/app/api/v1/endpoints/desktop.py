"""Desktop integration endpoints for Phase 7A."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.config import settings
from app.desktop.manager import DesktopManager
from app.models.pending_link import PendingLink, PendingLinkStatus
from app.schemas.settings import ProcessingSettings
from app.services.downloader.download_orchestrator import DownloadOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Desktop"])

_desktop_manager: Optional[DesktopManager] = None


def get_desktop_manager() -> DesktopManager:
    global _desktop_manager
    if _desktop_manager is None:
        _desktop_manager = DesktopManager()
    return _desktop_manager


def set_desktop_manager(manager: DesktopManager) -> None:
    global _desktop_manager
    _desktop_manager = manager


@router.get("/desktop/status")
async def get_desktop_status(manager: DesktopManager = Depends(get_desktop_manager)) -> dict:
    return {
        "clipboard_running": manager.clipboard_running,
        "tray_running": manager.tray_running,
        "clipboard_enabled": settings.CLIPBOARD_ENABLED,
        "tray_enabled": settings.TRAY_ENABLED,
    }


@router.post("/desktop/start")
async def start_desktop_services(
    payload: Optional[dict] = None,
    manager: DesktopManager = Depends(get_desktop_manager),
) -> dict:
    data = payload or {}
    clipboard = data.get("clipboard", True)
    tray = data.get("tray", True)
    manager.start(clipboard=bool(clipboard), tray=bool(tray))
    return {
        "clipboard_running": manager.clipboard_running,
        "tray_running": manager.tray_running,
    }


@router.post("/desktop/stop")
async def stop_desktop_services(manager: DesktopManager = Depends(get_desktop_manager)) -> dict:
    manager.stop()
    return {"clipboard_running": manager.clipboard_running, "tray_running": manager.tray_running}


@router.get("/desktop/pending")
async def list_pending_links(
    db: AsyncSession = Depends(get_db),
    manager: DesktopManager = Depends(get_desktop_manager),
) -> dict:
    result = await db.execute(
        select(PendingLink)
        .where(PendingLink.status == PendingLinkStatus.PENDING)
        .order_by(PendingLink.detected_at.desc())
        .limit(5)
    )
    links = result.scalars().all()
    return {
        "items": [
            {
                "id": str(link.id),
                "url": link.url,
                "platform": link.platform,
                "status": link.status.value,
                "detected_at": link.detected_at.isoformat() if link.detected_at else None,
            }
            for link in links
        ]
    }


@router.post("/desktop/pending/{link_id}/dismiss")
async def dismiss_pending_link(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    manager: DesktopManager = Depends(get_desktop_manager),
) -> dict:
    result = await db.execute(select(PendingLink).where(PendingLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Pending link not found")
    link.status = PendingLinkStatus.DISMISSED
    await db.commit()
    return {"id": str(link.id), "status": link.status.value}


@router.post("/desktop/pending/{link_id}/download")
async def download_pending_link(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    manager: DesktopManager = Depends(get_desktop_manager),
) -> dict:
    from app.models.pending_link import PendingLinkStatus
    from app.services.downloader.download_orchestrator import DownloadOrchestrator

    result = await db.execute(select(PendingLink).where(PendingLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Pending link not found")

    platform = link.platform or "other"
    orchestrator = DownloadOrchestrator(db)
    try:
        download = await orchestrator.create_download(
            link.url,
            force=True,
            platform=platform,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    link.status = PendingLinkStatus.DOWNLOADED
    await db.commit()

    # TODO: push hook for clipboard pending download
    # from app.services.notifications.push_service import PushService
    # await PushService().send_to_user(db, link.owner_id, "Clipboard download started", link.url, "clipboard", f"/downloads/{download.id}")

    return {"id": str(link.id), "status": link.status.value, "download_id": str(download.id)}


@router.websocket("/ws/clipboard")
async def clipboard_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    from app.core.redis_client import get_async_redis

    client = get_async_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe("clipboard:new")
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            try:
                data = json.loads(message["data"])
                await websocket.send_json(data)
            except (TypeError, ValueError, KeyError):
                logger.debug("Dropping malformed clipboard message")
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Clipboard socket ended: %s", exc)
    finally:
        try:
            await pubsub.unsubscribe("clipboard:new")
            await pubsub.aclose()
        except Exception as exc:
            logger.debug("Error closing clipboard pubsub: %s", exc)
