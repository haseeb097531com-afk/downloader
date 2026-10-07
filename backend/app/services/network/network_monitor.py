"""Lightweight network monitor for MediaVault Pro.

Measures downstream bandwidth by downloading a small static payload from a fast
CDN, caches the result in Redis, and exposes a quality recommendation helper.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import requests

from app.core.config import settings
from app.core import redis_client

logger = logging.getLogger(__name__)

# A small static file served from Cloudflare's cache (approx 5 MB). This is
# intentionally a public, static asset so the measurement reflects raw throughput
# rather than CDN warm-up or origin latency.
_SPEED_TEST_URL = "https://speed.hetzner.de/5MB.bin"
_SPEED_TEST_TIMEOUT = 30
_REDIS_SPEED_KEY = "mediavault:network:speed_mbps"


class NetworkMonitorError(RuntimeError):
    """Raised when the speed test cannot be completed."""


def get_recommended_quality(speed_mbps: float) -> str:
    """Map a measured bandwidth value to an optimal quality preset."""
    if speed_mbps < 5:
        return "480p"
    if speed_mbps < 15:
        return "720p"
    if speed_mbps < 30:
        return "1080p"
    return "best"


def get_current_speed(force_refresh: bool = False) -> float:
    """Return the cached downstream speed in Mbps, refreshing when stale.

    Args:
        force_refresh: Ignore the cache and perform a fresh measurement.

    Returns:
        Measured speed in megabits per second. Falls back to 0.0 on failure.
    """
    if not force_refresh:
        try:
            cached = redis_client.get_redis().get(_REDIS_SPEED_KEY)
            if cached is not None:
                return float(cached)
        except redis_client.RedisUnavailable:
            logger.debug("Redis unavailable; skipping cached speed read")
        except Exception as exc:
            logger.debug("Failed to read cached network speed: %s", exc)

    speed = _measure_speed()
    if speed > 0:
        try:
            redis_client.get_redis().set(
                _REDIS_SPEED_KEY,
                str(round(speed, 2)),
                ex=settings.NETWORK_SPEED_CACHE_TTL,
            )
        except Exception as exc:
            logger.debug("Failed to cache network speed: %s", exc)

    return speed


def _measure_speed() -> float:
    """Download a small static file and compute throughput in Mbps."""
    try:
        start = time.perf_counter()
        response = requests.get(
            _SPEED_TEST_URL,
            timeout=_SPEED_TEST_TIMEOUT,
            stream=True,
        )
        response.raise_for_status()
        total_bytes = 0
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                total_bytes += len(chunk)
        elapsed = time.perf_counter() - start

        if elapsed <= 0 or total_bytes <= 0:
            return 0.0

        # bits per second -> megabits per second
        return (total_bytes * 8) / (elapsed * 1_000_000)
    except Exception as exc:
        logger.warning("Network speed test failed: %s", exc)
        return 0.0


def get_network_status() -> dict:
    """Return a serializable snapshot of the current network state."""
    speed = get_current_speed()
    recommended = get_recommended_quality(speed)
    return {
        "current_speed_mbps": round(speed, 2),
        "recommended_quality": recommended,
        "limit_mbps": settings.BANDWIDTH_LIMIT_MBPS,
        "is_off_peak": _is_off_peak(),
    }


def _is_off_peak() -> bool:
    """Return True when the current local time falls outside off-peak hours."""
    if not settings.OFF_PEAK_ENABLED:
        return False
    now = datetime.now().time()
    try:
        start = datetime.strptime(settings.OFF_PEAK_START, "%H:%M").time()
        end = datetime.strptime(settings.OFF_PEAK_END, "%H:%M").time()
    except ValueError:
        return False

    if start <= end:
        return now < start or now >= end
    return now < start and now >= end
