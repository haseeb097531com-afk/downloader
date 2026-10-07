from fastapi import APIRouter

from app.core import redis_client
from app.core.config import settings
from app.services.storage.storage_guard import get_disk_status as get_disk
from app.services.processor.resource_guard import ResourceGuard
from app.services.network.network_monitor import get_current_speed

router = APIRouter(tags=["System"])


@router.get("/system/stats")
async def get_system_stats():
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    is_throttled = redis_client.is_throttled()

    return {
        "cpu_percent": cpu_percent,
        "ram_percent": ram.percent,
        "is_throttled": is_throttled,
    }


@router.get("/system/disk")
async def get_system_disk():
    status = get_disk()
    return status.__dict__


@router.get("/system/speed")
async def get_system_speed():
    """
    Turbo / performance telemetry.

    Returns:
        {
            "turbo_mode": bool,
            "aria2_available": bool,
            "concurrent_fragments": int,
            "active_workers": int,
            "current_speed_mbps": float,
        }
    """
    from app.services.extractor.ytdlp_engine import YTDLPEngine

    speed_mbps = 0.0
    try:
        speed = get_current_speed(force_refresh=False)
        if speed is not None:
            speed_mbps = round(speed, 2)
    except Exception:
        speed_mbps = 0.0

    return {
        "turbo_mode": getattr(settings, "TURBO_MODE", False),
        "aria2_available": YTDLPEngine._aria2_available(),
        "concurrent_fragments": getattr(settings, "CONCURRENT_FRAGMENTS", 16),
        "active_workers": getattr(settings, "MAX_CONCURRENT_DOWNLOADS", ResourceGuard.get_recommended_concurrency()),
        "current_speed_mbps": speed_mbps,
    }
