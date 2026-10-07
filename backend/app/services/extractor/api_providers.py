"""API provider registry with monthly rate limiting."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.core import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProviderStatus:
    name: str
    enabled: bool
    has_key: bool
    used_this_month: int
    monthly_limit: int
    remaining: int
    status: str = "ok"


class ProviderRegistry:
    """Manage fallback API provider configuration and rate limits."""

    PROVIDERS = ["scraperapi", "zenrows", "rapidapi"]

    def list_providers(self) -> List[ProviderStatus]:
        """Return status for all configured providers."""
        now = datetime.utcnow()
        month_key = now.strftime("%Y-%m")
        result: List[ProviderStatus] = []

        for provider in self.PROVIDERS:
            if provider == "scraperapi":
                key = settings.SCRAPER_API_KEY
                provider_enabled = settings.FALLBACK_ENABLED and settings.SCRAPER_PROVIDER == "scraperapi"
            elif provider == "zenrows":
                key = settings.SCRAPER_API_KEY if settings.SCRAPER_PROVIDER == "zenrows" else ""
                provider_enabled = settings.FALLBACK_ENABLED and settings.SCRAPER_PROVIDER == "zenrows"
            elif provider == "rapidapi":
                key = settings.RAPID_API_KEY
                provider_enabled = settings.FALLBACK_ENABLED
            else:
                key = ""
                provider_enabled = False

            used = self._get_monthly_usage(provider, month_key)
            limit = settings.PROVIDER_MONTHLY_LIMIT
            remaining = max(0, limit - used)
            near_limit = used >= int(limit * 0.9)

            status = "ok"
            if not provider_enabled:
                status = "disabled"
            elif not key:
                status = "no_key"
            elif near_limit:
                status = "near_limit"
            elif used >= limit:
                status = "exhausted"

            result.append(
                ProviderStatus(
                    name=provider,
                    enabled=provider_enabled,
                    has_key=bool(key),
                    used_this_month=used,
                    monthly_limit=limit,
                    remaining=remaining,
                    status=status,
                )
            )

        return result

    def can_use(self, provider: str) -> bool:
        """Return True when the provider is available and within its monthly limit."""
        if not settings.FALLBACK_ENABLED:
            return False

        if provider == "scraperapi":
            if settings.SCRAPER_PROVIDER != "scraperapi" or not settings.SCRAPER_API_KEY:
                return False
        elif provider == "zenrows":
            if settings.SCRAPER_PROVIDER != "zenrows" or not settings.SCRAPER_API_KEY:
                return False
        elif provider == "rapidapi":
            if not settings.RAPID_API_KEY:
                return False
        else:
            return False

        now = datetime.utcnow()
        month_key = now.strftime("%Y-%m")
        used = self._get_monthly_usage(provider, month_key)
        return used < settings.PROVIDER_MONTHLY_LIMIT

    def record_usage(self, provider: str) -> None:
        """Increment the monthly usage counter for ``provider``."""
        now = datetime.utcnow()
        month_key = now.strftime("%Y-%m")
        try:
            redis_client.get_redis().incr(f"api_usage:{provider}:{month_key}")
        except Exception as exc:
            logger.warning("Failed to record API usage for %s: %s", provider, exc)

    def reset_monthly_counters(self) -> None:
        """Clear all monthly usage counters (called on the 1st of each month)."""
        now = datetime.utcnow()
        prefix = f"api_usage:{now.strftime('%Y-%m')}"
        try:
            client = redis_client.get_redis()
            for provider in self.PROVIDERS:
                client.delete(f"api_usage:{provider}:{prefix}")
        except Exception as exc:
            logger.warning("Failed to reset monthly API counters: %s", exc)

    def _get_monthly_usage(self, provider: str, month_key: str) -> int:
        """Return the current monthly usage count for ``provider``."""
        try:
            value = redis_client.get_redis().get(f"api_usage:{provider}:{month_key}")
            return int(value) if value is not None else 0
        except Exception as exc:
            logger.warning("Failed to read API usage for %s: %s", provider, exc)
            return 0
