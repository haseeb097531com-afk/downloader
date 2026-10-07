"""Telegram bot status endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps_auth import get_current_user, require_role
from app.core.config import settings
from app.models.user import UserRole

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Bot"])


@router.get("/bot/telegram/status")
async def telegram_status(
    current_user=Depends(require_role(UserRole.OWNER)),
) -> dict:
    try:
        from app.services.bot.telegram_bot import TelegramBotService
        service = TelegramBotService()
        service.start(
            getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "",
            getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", "") or "",
        )
        return {
            "enabled": getattr(settings, "TELEGRAM_BOT_ENABLED", False) and bool(getattr(settings, "TELEGRAM_BOT_TOKEN", "")),
            "connected": False,
            "bot_username": "",
        }
    except Exception as exc:
        logger.warning("Telegram status check failed: %s", exc)
        return {
            "enabled": False,
            "connected": False,
            "bot_username": "",
        }
