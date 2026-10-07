"""Cloud backup endpoints for Phase 9A."""

from __future__ import annotations

import html
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.config import settings
from app.models.download import Download, DownloadStatus
from app.schemas.settings import ProcessingSettings
from app.services.cloud.cloud_sync import GoogleDriveClient, DropboxClient, get_client, CloudTokenStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Cloud"])


@router.get("/cloud/status")
async def cloud_status() -> dict:
    """Return cloud connection status and configured provider."""
    google_connected = GoogleDriveClient().is_connected()
    dropbox_connected = DropboxClient().is_connected()
    return {
        "google_connected": google_connected,
        "dropbox_connected": dropbox_connected,
        "cloud_backup_enabled": settings.CLOUD_BACKUP_ENABLED,
        "cloud_provider": settings.CLOUD_PROVIDER or None,
    }


@router.get("/cloud/google/auth-url")
async def google_auth_url() -> dict:
    """Return a Google OAuth2 authorization URL."""
    client = GoogleDriveClient()
    try:
        url = client.build_auth_url()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"url": url}


@router.get("/cloud/google/callback")
async def google_callback(request: Request, code: str = Query(...)) -> dict:
    """Exchange the OAuth2 code for tokens and store them encrypted."""
    client = GoogleDriveClient()
    try:
        client.exchange_code(code)
    except Exception as exc:
        logger.warning("Google OAuth callback failed: %s", exc)
        return {
            "status": "error",
            "message": str(exc),
            "html": f"<h2>Connection failed</h2><p>{html.escape(str(exc))}</p>",
        }
    return {
        "status": "connected",
        "html": "<html><body><h2>Connected</h2><p>You can close this tab.</p></body></html>",
    }


@router.post("/cloud/dropbox/connect")
async def dropbox_connect(payload: dict) -> dict:
    """Validate and store a Dropbox access token."""
    access_token = (payload or {}).get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token is required")
    client = DropboxClient()
    try:
        client.connect(access_token)
    except Exception as exc:
        logger.warning("Dropbox connect failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "connected", "provider": "dropbox"}


@router.post("/cloud/disconnect/{provider}")
async def cloud_disconnect(provider: str) -> dict:
    """Disconnect a cloud provider and delete stored tokens."""
    provider = provider.strip().lower()
    if provider == "google":
        GoogleDriveClient().disconnect()
    elif provider == "dropbox":
        DropboxClient().disconnect()
    else:
        raise HTTPException(status_code=400, detail="provider must be 'google' or 'dropbox'")
    CloudTokenStore.delete(provider)
    return {"status": "disconnected", "provider": provider}


@router.post("/downloads/{download_id}/backup")
async def manual_backup(download_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Manually enqueue a cloud backup for a completed download."""
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalars().first()
    if download is None:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.status != DownloadStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Download is not completed")

    provider = (settings.CLOUD_PROVIDER or "").strip().lower()
    if not provider:
        raise HTTPException(status_code=400, detail="No cloud provider configured")

    client = get_client(provider)
    if client is None:
        raise HTTPException(status_code=503, detail=f"{provider} is not connected")

    from app.workers.cloud_tasks import cloud_upload_task

    try:
        task = cloud_upload_task.delay(download_id)
    except Exception as exc:
        logger.error("Failed to enqueue cloud backup for %s: %s", download_id, exc)
        raise HTTPException(status_code=503, detail="Failed to enqueue backup task") from exc

    return {"status": "queued", "download_id": download_id, "task_id": task.id}
