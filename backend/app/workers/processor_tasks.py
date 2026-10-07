"""Post-processing Celery task."""

from __future__ import annotations

import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.processor.pipeline import ProcessingPipeline

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.processor_tasks.process_media_task")
def process_media_task(download_id: str) -> None:
    """Run :class:`ProcessingPipeline` for ``download_id``."""
    asyncio.run(_run_process(download_id))


async def _run_process(download_id: str) -> None:
    await ProcessingPipeline().process_download(download_id)

    provider = (settings.CLOUD_PROVIDER or "").strip().lower()
    if settings.CLOUD_BACKUP_ENABLED and provider:
        from app.services.cloud.cloud_sync import get_client

        if get_client(provider) is not None:
            try:
                from app.workers.cloud_tasks import cloud_upload_task

                cloud_upload_task.delay(download_id)
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("Failed to chain cloud backup for %s: %s", download_id, exc)
