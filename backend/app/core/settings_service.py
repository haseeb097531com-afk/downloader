"""Persist runtime processing settings to JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class SettingsService:
    """Read/write processing settings from DATA_DIR/settings.json."""

    def __init__(self) -> None:
        self.settings_file = Path(settings.DATA_DIR) / "settings.json"
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)

    def get_settings(self) -> dict[str, Any]:
        """Return current settings, falling back to defaults when the file is missing or corrupt."""
        if not self.settings_file.exists():
            return self._defaults()
        try:
            with self.settings_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                return self._defaults()
            return {**self._defaults(), **data}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read settings file: %s", exc)
            return self._defaults()

    def update_settings(self, partial: dict[str, Any]) -> dict[str, Any]:
        """Merge ``partial`` into persisted settings and return the updated dict."""
        current = self.get_settings()
        current.update(partial)
        self._write(current)
        return current

    def _write(self, data: dict[str, Any]) -> None:
        tmp_path = self.settings_file.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        tmp_path.replace(self.settings_file)

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "auto_merge": settings.AUTO_MERGE,
            "embed_metadata": settings.EMBED_METADATA,
            "generate_thumbnails": settings.GENERATE_THUMBNAILS,
            "max_cpu_percent": settings.MAX_CPU_PERCENT,
            "max_ram_percent": settings.MAX_RAM_PERCENT,
            "scraper_api_key": settings.SCRAPER_API_KEY,
            "scraper_provider": settings.SCRAPER_PROVIDER,
            "rapid_api_key": settings.RAPID_API_KEY,
            "provider_monthly_limit": settings.PROVIDER_MONTHLY_LIMIT,
            "fallback_enabled": settings.FALLBACK_ENABLED,
            "clipboard_enabled": settings.CLIPBOARD_ENABLED,
            "tray_enabled": settings.TRAY_ENABLED,
            "clipboard_poll_ms": settings.CLIPBOARD_POLL_MS,
            "auto_categorize": settings.AUTO_CATEGORIZE,
            "min_confidence": settings.MIN_CONFIDENCE,
            "use_llm_categorize": settings.USE_LLM_CATEGORIZE,
            "ollama_host": settings.OLLAMA_HOST,
            "storage_guard_enabled": settings.STORAGE_GUARD_ENABLED,
            "min_free_gb": settings.MIN_FREE_GB,
            "cloud_backup_enabled": settings.CLOUD_BACKUP_ENABLED,
            "cloud_provider": settings.CLOUD_PROVIDER,
            "google_drive_client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
            "google_drive_client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
            "dropbox_access_token": settings.DROPBOX_ACCESS_TOKEN,
            "cloud_tokens_file": settings.CLOUD_TOKENS_FILE,
            "ai_analysis_enabled": settings.AI_ANALYSIS_ENABLED,
            "whisper_model": settings.WHISPER_MODEL,
            "ollama_model": settings.OLLAMA_MODEL,
            "auto_translate_langs": settings.AUTO_TRANSLATE_LANGS,
            "dedup_enabled": settings.DEDUP_ENABLED,
            "dedup_threshold": settings.DEDUP_THRESHOLD,
            "archive_dedup_enabled": settings.ARCHIVE_DEDUP_ENABLED,
            "archive_dedup_path": settings.ARCHIVE_DEDUP_PATH,
            "safe_mode": settings.SAFE_MODE,
            "pin_hash": settings.PIN_HASH,
            "keyword_blacklist": settings.KEYWORD_BLACKLIST,
            "moderation_sensitivity": settings.MODERATION_SENSITIVITY,
            "bandwidth_limit_mbps": settings.BANDWIDTH_LIMIT_MBPS,
            "auto_adjust_quality": settings.AUTO_ADJUST_QUALITY,
            "off_peak_start": settings.OFF_PEAK_START,
            "off_peak_end": settings.OFF_PEAK_END,
            "off_peak_enabled": settings.OFF_PEAK_ENABLED,
            "turbo_mode": settings.TURBO_MODE,
            "concurrent_fragments": settings.CONCURRENT_FRAGMENTS,
            "aria2_connections": settings.ARIA2_CONNECTIONS,
            "network_speed_cache_ttl": settings.NETWORK_SPEED_CACHE_TTL,
            "user_plugins_dir": settings.USER_PLUGINS_DIR,
            "auth_enabled": settings.AUTH_ENABLED,
            "jwt_secret": settings.JWT_SECRET,
            "jwt_access_ttl_min": settings.JWT_ACCESS_TTL_MIN,
            "jwt_refresh_ttl_days": settings.JWT_REFRESH_TTL_DAYS,
            "max_failed_logins": settings.MAX_FAILED_LOGINS,
            "lock_minutes": settings.LOCK_MINUTES,
            "registration_open": settings.REGISTRATION_OPEN,
            "global_rate_limit": settings.GLOBAL_RATE_LIMIT,
            "push_enabled": settings.PUSH_ENABLED,
            "remote_enabled": settings.REMOTE_ENABLED,
            "pairing_ttl_seconds": settings.PAIRING_TTL_SECONDS,
            "public_base_url": settings.PUBLIC_BASE_URL,
            "telegram_bot_enabled": settings.TELEGRAM_BOT_ENABLED,
            "telegram_bot_token": settings.TELEGRAM_BOT_TOKEN,
            "telegram_allowed_chat_ids": settings.TELEGRAM_ALLOWED_CHAT_IDS,
            "billing_enabled": settings.BILLING_ENABLED,
            "payment_provider": settings.PAYMENT_PROVIDER,
            "stripe_secret_key": settings.STRIPE_SECRET_KEY,
            "stripe_webhook_secret": settings.STRIPE_WEBHOOK_SECRET,
            "stripe_price_starter": settings.STRIPE_PRICE_STARTER,
            "stripe_price_pro": settings.STRIPE_PRICE_PRO,
            "stripe_price_enterprise": settings.STRIPE_PRICE_ENTERPRISE,
        }
