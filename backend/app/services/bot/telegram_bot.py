"""Telegram bot service for MediaVault."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.core.config import settings
from app.core import redis_client
from app.db.database import AsyncSessionLocal
from app.models.download import Download
from app.services.downloader.download_orchestrator import DownloadOrchestrator
from app.services.extractor.platform_detector import PlatformDetector
from app.services.integrations.secrets import get_secret
from sqlalchemy import select

logger = logging.getLogger(__name__)

try:
    from telegram import Update
    from telegram.ext import Application, CallbackContext, CommandHandler, MessageHandler, filters
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed; Telegram bot disabled")


class TelegramBotService:
    """Thin Telegram bot that queues downloads on the MediaVault backend."""

    def __init__(self) -> None:
        self.enabled = False
        self.application: Optional[object] = None
        self.allowed_chat_ids: set[int] = set()
        self._running = False

    async def start_from_store(self) -> None:
        """Start the bot using token from the encrypted key store."""
        if not TELEGRAM_AVAILABLE:
            logger.warning("Cannot start Telegram bot: python-telegram-bot not installed")
            return

        token = await get_secret("telegram_bot_token")
        allowed_chat_ids = getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", "") or ""
        
        if not token:
            logger.info("Telegram bot disabled: no token configured in key store")
            return

        await self._start(token, allowed_chat_ids)

    async def _start(self, token: str, allowed_chat_ids_str: str) -> None:
        if not TELEGRAM_AVAILABLE:
            logger.warning("Cannot start Telegram bot: python-telegram-bot not installed")
            return

        if not token:
            logger.info("Telegram bot disabled: no token configured")
            return

        try:
            self.application = Application.builder().token(token).build()
        except Exception as exc:
            logger.error("Failed to build Telegram application: %s", exc)
            return

        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

        self.allowed_chat_ids = set()
        for part in (allowed_chat_ids_str or "").split(","):
            part = part.strip()
            if part.isdigit():
                self.allowed_chat_ids.add(int(part))

        self.enabled = True
        logger.info("Telegram bot handlers registered; allowed_chat_ids=%s", self.allowed_chat_ids or "any first chat")

    async def run(self) -> None:
        if not self.enabled or self.application is None:
            return
        self._running = True
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started")
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        if self.application is not None:
            try:
                updater = getattr(self.application, "updater", None)
                if updater is not None:
                    await updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as exc:
                logger.debug("Telegram shutdown error: %s", exc)
        logger.info("Telegram bot stopped")

    def _is_allowed(self, chat_id: int) -> bool:
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids

    async def _cmd_start(self, update: Update, context: CallbackContext) -> None:
        if not update.effective_chat:
            return
        chat_id = update.effective_chat.id
        if not self._is_allowed(chat_id):
            await update.message.reply_text("Not authorized.")
            return
        if not self.allowed_chat_ids:
            self.allowed_chat_ids.add(chat_id)
        await update.message.reply_text(
            "MediaVault bot ready.\nSend me any YouTube / TikTok / Instagram / Facebook / Twitter link and I'll queue it here."
        )

    async def _cmd_status(self, update: Update, context: CallbackContext) -> None:
        if not update.effective_chat:
            return
        chat_id = update.effective_chat.id
        if not self._is_allowed(chat_id):
            await update.message.reply_text("Not authorized.")
            return
        r = redis_client.get_redis()
        key = f"telegram:chat:{chat_id}:download"
        download_id = r.get(key)
        if not download_id:
            await update.message.reply_text("No recent download found.")
            return
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Download).where(Download.id == str(download_id)))
            download = result.scalars().first()
        if not download:
            await update.message.reply_text("Download not found.")
            return
        await update.message.reply_text(f"Status: {download.status.value}\nProgress: {download.progress or 0:.1f}%")

    async def _on_message(self, update: Update, context: CallbackContext) -> None:
        if not update.effective_chat or not update.message or not update.message.text:
            return
        chat_id = update.effective_chat.id
        if not self._is_allowed(chat_id):
            await update.message.reply_text("Not authorized.")
            return

        url = update.message.text.strip()
        detector = PlatformDetector()
        validation = detector.validate_url(url)
        if not validation.is_valid:
            await update.message.reply_text(f"Unsupported link: {validation.error_message}")
            return

        try:
            async with AsyncSessionLocal() as db:
                orchestrator = DownloadOrchestrator(db, current_user=None)
                download = await orchestrator.create_download(url, force=False)
        except Exception as exc:
            await update.message.reply_text(f"Failed to queue: {exc}")
            return

        r = redis_client.get_redis()
        r.setex(f"telegram:chat:{chat_id}:download", 3600, download.id)

        try:
            from app.workers.download_tasks import download_media_task
            download_media_task.delay(str(download.id))
        except Exception:
            pass

        await update.message.reply_text(f"Queued ✅ id={download.id}")
