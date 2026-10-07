"""Periodic system monitor tasks."""

from __future__ import annotations

import logging

from app.core import redis_client
from app.core.celery_app import celery_app
from app.services.network.network_monitor import get_current_speed
from app.services.processor.resource_guard import ResourceGuard
from app.services.storage.storage_guard import get_disk_status

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.monitor_tasks.system_monitor_task")
def system_monitor_task() -> None:
    """Evaluate CPU/RAM load and set or clear the Redis throttle flag."""
    if ResourceGuard.is_system_overloaded():
        redis_client.set_throttle()
    else:
        redis_client.clear_throttle()


@celery_app.task(name="app.workers.monitor_tasks.storage_monitor_task")
def storage_monitor_task() -> None:
    """Evaluate disk space and pause downloads when storage is low."""
    from app.core.config import settings as app_settings

    if not app_settings.STORAGE_GUARD_ENABLED:
        return

    status = get_disk_status()
    min_free = float(app_settings.MIN_FREE_GB)

    if status.free_gb < min_free:
        try:
            redis_client.get_redis().set("storage_guard", "1")
        except Exception as exc:
            logger.warning("Failed to set storage_guard flag: %s", exc)

        try:
            from app.services.notifications.push_service import PushService
            import asyncio

            async def _broadcast_storage_alert() -> None:
                async with AsyncSessionLocal() as db:
                    await PushService().broadcast_admin(
                        db, "Storage Low", f"Only {status.free_gb:.1f} GB free", "storage", "/system"
                    )

            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    asyncio.ensure_future(_broadcast_storage_alert())
                else:
                    asyncio.run(_broadcast_storage_alert())
            except RuntimeError:
                asyncio.run(_broadcast_storage_alert())
        except Exception as exc:
            logger.warning("Storage guard push notification failed: %s", exc)

        try:
            import asyncio

            async def _pause_active() -> None:
                from app.db.database import AsyncSessionLocal
                from sqlalchemy import select
                from app.models.download import Download, DownloadStatus
                from app.services.downloader.download_orchestrator import DownloadOrchestrator

                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Download).where(Download.status == DownloadStatus.DOWNLOADING)
                    )
                    active = result.scalars().all()
                    if active:
                        orchestrator = DownloadOrchestrator(db)
                        try:
                            await orchestrator.pause_all()
                        except Exception as exc:
                            logger.warning("Failed to pause downloads for storage guard: %s", exc)

            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    asyncio.ensure_future(_pause_active())
                else:
                    asyncio.run(_pause_active())
            except RuntimeError:
                asyncio.run(_pause_active())
        except Exception as exc:
            logger.warning("Storage guard pause error: %s", exc)

        try:
            redis_client.get_redis().publish(
                "system:alert",
                __import__("json").dumps({"type": "storage_low", "free_gb": status.free_gb}),
            )
        except Exception as exc:
            logger.warning("Failed to publish storage_low alert: %s", exc)
    elif status.free_gb > min_free + 1.0:
        try:
            redis_client.get_redis().delete("storage_guard")
        except Exception as exc:
            logger.warning("Failed to clear storage_guard flag: %s", exc)

        try:
            redis_client.get_redis().publish(
                "system:alert",
                __import__("json").dumps({"type": "storage_ok", "free_gb": status.free_gb}),
            )
        except Exception as exc:
            logger.warning("Failed to publish storage_ok alert: %s", exc)


@celery_app.task(name="app.workers.monitor_tasks.network_speed_test_task")
def network_speed_test_task() -> None:
    """Refresh the cached network speed measurement."""
    try:
        speed = get_current_speed(force_refresh=True)
        logger.debug("Network speed test complete: %.2f Mbps", speed)
    except Exception as exc:
        logger.warning("Network speed test failed: %s", exc)
