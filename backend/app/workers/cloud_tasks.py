"""Celery task for uploading completed downloads to cloud storage."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.download import Download, DownloadStatus
from app.services.cloud.cloud_sync import get_client

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.cloud_tasks.cloud_upload_task")
def cloud_upload_task(download_id: str) -> None:
    """Upload a completed download to the active cloud provider.

    On success the download's ``cloud_backed_up`` and ``cloud_url`` columns are
    updated. On failure the error is recorded in ``processing_error`` but the
    download remains ``completed`` so the local copy is preserved.
    """
    asyncio.run(_run_upload(download_id))


async def _run_upload(download_id: str) -> None:
    provider = (settings.CLOUD_PROVIDER or "").strip().lower()
    if not provider:
        logger.info("Cloud backup skipped for %s: no provider configured", download_id)
        return

    client = get_client(provider)
    if client is None:
        logger.info("Cloud backup skipped for %s: provider %s is not connected", download_id, provider)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Download).where(Download.id == download_id))
        download = result.scalars().first()

        if download is None:
            logger.warning("Cloud upload skipped: download %s not found", download_id)
            return

        if download.status != DownloadStatus.COMPLETED:
            logger.info("Cloud upload skipped for %s: status is %s", download_id, download.status)
            return

        file_path = download.file_path
        if not file_path or not Path(file_path).is_file():
            msg = f"Cannot back up: file not found at {file_path}"
            download.processing_error = (download.processing_error or "") + f"; {msg}"
            await db.commit()
            logger.warning(msg)
            return

        folder_path = _build_cloud_folder(download)

        try:
            url = await asyncio.to_thread(client.upload_file, file_path, folder_path)
            download.cloud_backed_up = True
            download.cloud_url = url
            if download.processing_error and "cloud" in download.processing_error.lower():
                download.processing_error = download.processing_error.split("; cloud")[0].rstrip("; ")
            await db.commit()
            logger.info("Cloud backup complete for %s -> %s", download_id, url)
        except Exception as exc:
            logger.warning("Cloud backup failed for %s: %s", download_id, exc)
            note = f"Cloud backup failed: {exc}"
            existing = download.processing_error or ""
            download.processing_error = (existing + f"; {note}").strip()
            await db.commit()


def _build_cloud_folder(download: Download) -> str:
    """Build a deterministic remote folder path from the download metadata."""
    platform = (download.platform or "unknown").lower()
    category = (download.category or "Unsorted").lower()
    metadata = download.metadata_json or {}
    uploader = metadata.get("uploader_name") or metadata.get("uploader") or metadata.get("username") or "unknown"
    username = str(uploader).replace("/", "_").replace("\\", "_").strip()
    if not username:
        username = "unknown"
    return f"MediaVault/{platform}/@{username}/{category}"
