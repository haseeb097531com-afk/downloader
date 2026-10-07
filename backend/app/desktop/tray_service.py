"""System tray service for Phase 7A."""

from __future__ import annotations

import logging
import threading
import webbrowser
from typing import Optional

from app.core.config import settings

try:
    import pystray
    from pystray import Menu, MenuItem
except ImportError:  # pragma: no cover - optional dependency
    pystray = None  # type: ignore[assignment]
    Menu = None  # type: ignore[assignment]
    MenuItem = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class TrayService:
    """System tray icon with quick controls for MediaVault.

    The tray runs in a dedicated daemon thread so it never blocks the API
    server. All menu actions are wrapped so a failure degrades to a log entry.
    """

    def __init__(self, on_exit: Optional[threading.Event] = None) -> None:
        self._on_exit = on_exit or threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._icon: Optional["pystray.Icon"] = None

    def start(self) -> None:
        """Start the system tray if not already running."""
        if self.is_running():
            return
        if pystray is None:
            logger.warning("pystray is not installed; tray service disabled")
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="tray-service")
        self._thread.start()
        logger.info("Tray service started")

    def stop(self) -> None:
        """Stop the tray and signal the exit event."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as exc:
                logger.debug("Tray stop error: %s", exc)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._on_exit.set()
        logger.info("Tray service stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        try:
            icon = self._create_icon()
            menu = self._create_menu()
            self._icon = pystray.Icon("mediavault", icon, "MediaVault", menu)
            self._icon.run()
        except Exception as exc:
            logger.warning("Tray service error: %s", exc)

    def _create_icon(self) -> "pystray.Icon":
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            logger.warning("Pillow is not installed; tray icon disabled")
            raise RuntimeError("Pillow is required for the tray icon")

        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        from PIL import ImageColor
        color1 = ImageColor.getrgb("#6C5CE7")
        color2 = ImageColor.getrgb("#00D2FF")

        for y in range(size):
            ratio = y / max(size - 1, 1)
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(0, y), (size - 1, y)], fill=(r, g, b, 255))

        draw.rounded_rectangle([4, 4, size - 5, size - 5], radius=12, fill=(255, 255, 255, 255))
        for y in range(12, size - 12):
            ratio = (y - 12) / max((size - 24 - 1), 1)
            r = int(color2[0] * ratio + color1[0] * (1 - ratio))
            g = int(color2[1] * ratio + color1[1] * (1 - ratio))
            b = int(color2[2] * ratio + color1[2] * (1 - ratio))
            draw.line([(8, y), (size - 9, y)], fill=(r, g, b, 255))

        return pystray.Icon("mediavault", image, "MediaVault")

    def _create_menu(self) -> "Menu":
        return Menu(
            MenuItem("Open Dashboard", self._open_dashboard),
            MenuItem("Pause All Downloads", self._pause_all),
            MenuItem("Resume All Downloads", self._resume_all),
            Menu.SEPARATOR,
            MenuItem("Exit MediaVault", self._exit_app),
        )

    def _open_dashboard(self, icon: "pystray.Icon", item: "pystray.MenuItem") -> None:
        try:
            base = settings.PUBLIC_BASE_URL or "http://localhost:3000"
            webbrowser.open(base)
        except Exception as exc:
            logger.warning("Failed to open dashboard: %s", exc)

    def _pause_all(self, icon: "pystray.Icon", item: "pystray.MenuItem") -> None:
        try:
            import httpx
            base = settings.PUBLIC_BASE_URL or "http://localhost:8000"
            httpx.post(f"{base}/api/v1/queue/pause-all", timeout=5)
        except Exception as exc:
            logger.warning("Failed to pause all downloads: %s", exc)

    def _resume_all(self, icon: "pystray.Icon", item: "pystray.MenuItem") -> None:
        try:
            import httpx
            base = settings.PUBLIC_BASE_URL or "http://localhost:8000"
            httpx.post(f"{base}/api/v1/queue/resume-all", timeout=5)
        except Exception as exc:
            logger.warning("Failed to resume all downloads: %s", exc)

    def _exit_app(self, icon: "pystray.Icon", item: "pystray.MenuItem") -> None:
        self.stop()
