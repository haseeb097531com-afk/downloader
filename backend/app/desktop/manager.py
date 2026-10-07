"""Desktop integration manager for Phase 7A."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from app.core.config import settings
from app.desktop.clipboard_monitor import ClipboardMonitor
from app.desktop.tray_service import TrayService

logger = logging.getLogger(__name__)


class DesktopManager:
    """Own the clipboard monitor and system tray services.

    Start and stop are idempotent and never raise: every error is logged and
    the manager continues to function so the API server is never disturbed.
    """

    def __init__(self) -> None:
        self._exit_event = threading.Event()
        self._clipboard = ClipboardMonitor()
        self._tray = TrayService(on_exit=self._exit_event)

    def start(self, *, clipboard: bool = True, tray: bool = True) -> None:
        """Start requested desktop services.

        Args:
            clipboard: Start the clipboard monitor when True.
            tray: Start the system tray when True.
        """
        if clipboard and settings.CLIPBOARD_ENABLED:
            try:
                self._clipboard.start()
            except Exception as exc:
                logger.warning("Failed to start clipboard monitor: %s", exc)

        if tray and settings.TRAY_ENABLED:
            try:
                self._tray.start()
            except Exception as exc:
                logger.warning("Failed to start tray service: %s", exc)

    def stop(self) -> None:
        """Stop both desktop services."""
        try:
            self._clipboard.stop()
        except Exception as exc:
            logger.warning("Error stopping clipboard monitor: %s", exc)
        try:
            self._tray.stop()
        except Exception as exc:
            logger.warning("Error stopping tray service: %s", exc)

    @property
    def clipboard_running(self) -> bool:
        return self._clipboard.is_running()

    @property
    def tray_running(self) -> bool:
        return self._tray.is_running()

    @property
    def clipboard_monitor(self) -> ClipboardMonitor:
        return self._clipboard

    @property
    def tray_service(self) -> TrayService:
        return self._tray
