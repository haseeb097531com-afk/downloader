"""Desktop clipboard monitor for Phase 7A."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.redis_client import get_redis
from app.models.pending_link import PendingLink, PendingLinkStatus
from app.services.extractor.platform_detector import PlatformDetector

try:
    import pyperclip
except ImportError:  # pragma: no cover - optional dependency on headless hosts
    pyperclip = None  # type: ignore[assignment]

try:
    from plyer import notification
except ImportError:  # pragma: no cover - optional dependency
    notification = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class ClipboardMonitor:
    """Background thread that polls the clipboard for social media URLs.

    The monitor never propagates exceptions to the caller: every loop iteration
    is wrapped so a transient OS or library error degrades to a log entry and
    the next poll continues normally.
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_text: str = ""
        self._lock = threading.Lock()
        self._detector = PlatformDetector()

    def start(self) -> None:
        """Start the clipboard monitor daemon thread if not already running."""
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="clipboard-monitor")
        self._thread.start()
        logger.info("Clipboard monitor started (poll=%sms)", settings.CLIPBOARD_POLL_MS)

    def stop(self) -> None:
        """Signal the monitor thread to exit and wait for it."""
        if not self.is_running():
            return
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("Clipboard monitor stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        if pyperclip is None:
            logger.warning("pyperclip is not installed; clipboard monitor disabled")
            return

        poll_interval = max(settings.CLIPBOARD_POLL_MS, 200) / 1000.0

        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Clipboard monitor loop error: %s", exc)
            if self._stop_event.wait(poll_interval):
                break

    def _poll_once(self) -> None:
        try:
            text = pyperclip.paste()
        except Exception as exc:
            logger.debug("Clipboard read failed: %s", exc)
            return

        if not isinstance(text, str):
            return

        with self._lock:
            if text == self._last_text:
                return
            self._last_text = text

        text = text.strip()
        if not text:
            return

        result = self._detector.validate_url(text)
        if not result.is_valid or result.platform_info is None:
            return

        platform = result.platform_info.platform_name
        self._handle_new_link(text, platform)

    def _handle_new_link(self, url: str, platform: str) -> None:
        async def _create_and_publish() -> None:
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

            engine = create_async_engine(
                settings.DATABASE_URL,
                future=True,
                connect_args={"check_same_thread": False},
            )
            try:
                session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                async with session_factory() as db:
                    cutoff = datetime.utcnow() - timedelta(minutes=10)
                    duplicate = await db.execute(
                        select(PendingLink.id)
                        .where(PendingLink.url == url)
                        .where(PendingLink.detected_at >= cutoff)
                        .where(PendingLink.status == PendingLinkStatus.PENDING)
                    )
                    if duplicate.scalar_one_or_none() is not None:
                        return

                    link = PendingLink(url=url, platform=platform, status=PendingLinkStatus.PENDING)
                    db.add(link)
                    await db.flush()
                    await db.commit()
                    payload = {"id": str(link.id), "url": url, "platform": platform}

                try:
                    redis_client = get_redis()
                    redis_client.publish("clipboard:new", json.dumps(payload, default=str))
                except Exception as exc:
                    logger.warning("Failed to publish clipboard event: %s", exc)

                try:
                    if notification is not None:
                        notification.notify(
                            title="MediaVault",
                            message=f"New {platform} link detected - open dashboard to download",
                        )
                except Exception as exc:
                    logger.debug("OS notification failed: %s", exc)
            finally:
                await engine.dispose()

        try:
            asyncio.run(_create_and_publish())
        except Exception as exc:
            logger.warning("Clipboard monitor handler error: %s", exc)
