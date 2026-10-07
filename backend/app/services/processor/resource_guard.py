"""System resource guard for download concurrency."""

from __future__ import annotations

import logging

import psutil

from app.core.config import settings

logger = logging.getLogger(__name__)


class ResourceGuard:
    """CPU/RAM based throttling helpers."""

    @staticmethod
    def get_recommended_concurrency() -> int:
        """Return a safe worker concurrency based on available CPU and RAM."""
        cpu_count = psutil.cpu_count(logical=True) or 1
        total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        return max(1, min(cpu_count - 1, int(total_ram_gb / 2)))

    @staticmethod
    def is_system_overloaded() -> bool:
        """Return ``True`` when CPU or RAM usage exceeds configured thresholds."""
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        if cpu_percent > settings.MAX_CPU_PERCENT:
            logger.debug("System overloaded: CPU %.1f%% > %d%%", cpu_percent, settings.MAX_CPU_PERCENT)
            return True
        if ram.percent > settings.MAX_RAM_PERCENT:
            logger.debug("System overloaded: RAM %.1f%% > %d%%", ram.percent, settings.MAX_RAM_PERCENT)
            return True
        return False
