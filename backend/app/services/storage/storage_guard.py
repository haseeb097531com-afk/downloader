"""Storage guard service for Phase 8A."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import psutil

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DiskStatus:
    total_gb: float
    free_gb: float
    used_percent: float
    guard_active: bool


def get_disk_status(path: Optional[str] = None) -> DiskStatus:
    """Return disk usage for the drive containing ``path``.

    Args:
        path: Path to check. Defaults to ``settings.DOWNLOAD_DIR``.

    Returns:
        A :class:`DiskStatus` with total, free, used percent, and guard state.
    """
    target = path or settings.DOWNLOAD_DIR
    try:
        usage = psutil.disk_usage(str(target))
        return DiskStatus(
            total_gb=round(usage.total / (1024 ** 3), 2),
            free_gb=round(usage.free / (1024 ** 3), 2),
            used_percent=round(usage.percent, 2),
            guard_active=usage.free / (1024 ** 3) < float(settings.MIN_FREE_GB),
        )
    except Exception as exc:
        logger.warning("Failed to read disk status for %s: %s", target, exc)
        return DiskStatus(total_gb=0.0, free_gb=0.0, used_percent=0.0, guard_active=False)
