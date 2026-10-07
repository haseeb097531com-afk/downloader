"""Unit tests for Phase 7A desktop integration."""

from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.desktop.clipboard_monitor import ClipboardMonitor
from app.desktop.manager import DesktopManager
from app.desktop.tray_service import TrayService


@pytest.mark.asyncio
async def test_clipboard_monitor_detects_url(monkeypatch, fake_redis, db_session):
    from app.models.pending_link import PendingLink, PendingLinkStatus

    fake_pyperclip = MagicMock()
    fake_pyperclip.paste.return_value = "https://www.tiktok.com/@user/video/1234567890"
    monkeypatch.setattr("app.desktop.clipboard_monitor.pyperclip", fake_pyperclip)
    monkeypatch.setattr("app.desktop.clipboard_monitor.get_redis", lambda: fake_redis)

    monitor = ClipboardMonitor()
    monitor.start()
    monitor._poll_once()
    monitor.stop()

    result = await db_session.execute(
        __import__("sqlalchemy").select(PendingLink).where(PendingLink.status == PendingLinkStatus.PENDING)
    )
    links = result.scalars().all()
    assert len(links) == 1
    assert links[0].platform == "tiktok"
    assert fake_redis.published
    published = [json.loads(m) for _, m in fake_redis.published]
    assert any(item.get("platform") == "tiktok" for item in published)


@pytest.mark.asyncio
async def test_clipboard_monitor_skips_duplicate_within_window(monkeypatch, fake_redis, db_session):
    from app.models.pending_link import PendingLink, PendingLinkStatus
    from app.core.config import settings as app_settings

    fake_pyperclip = MagicMock()
    fake_pyperclip.paste.return_value = "https://www.tiktok.com/@user/video/1234567890"
    monkeypatch.setattr("app.desktop.clipboard_monitor.pyperclip", fake_pyperclip)
    monkeypatch.setattr("app.desktop.clipboard_monitor.get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.desktop.clipboard_monitor.settings", app_settings)

    link = PendingLink(url="https://www.tiktok.com/@user/video/1234567890", platform="tiktok", status=PendingLinkStatus.PENDING)
    db_session.add(link)
    await db_session.commit()

    monitor = ClipboardMonitor()
    monitor.start()
    monitor._poll_once()
    monitor.stop()

    result = await db_session.execute(
        __import__("sqlalchemy").select(PendingLink).where(PendingLink.status == PendingLinkStatus.PENDING)
    )
    links = result.scalars().all()
    assert len(links) == 1


@pytest.mark.asyncio
async def test_clipboard_monitor_ignores_invalid_text(monkeypatch, fake_redis, db_session):
    from app.models.pending_link import PendingLink, PendingLinkStatus

    fake_pyperclip = MagicMock()
    fake_pyperclip.paste.return_value = "not a url at all"
    monkeypatch.setattr("app.desktop.clipboard_monitor.pyperclip", fake_pyperclip)
    monkeypatch.setattr("app.desktop.clipboard_monitor.get_redis", lambda: fake_redis)

    monitor = ClipboardMonitor()
    monitor.start()
    monitor._poll_once()
    monitor.stop()

    result = await db_session.execute(
        __import__("sqlalchemy").select(PendingLink).where(PendingLink.status == PendingLinkStatus.PENDING)
    )
    links = result.scalars().all()
    assert len(links) == 0


def test_desktop_manager_start_stop_idempotency():
    manager = DesktopManager()
    with patch.object(manager.clipboard_monitor, "start") as mock_clipboard_start, \
         patch.object(manager.tray_service, "start") as mock_tray_start:
        manager.start(clipboard=True, tray=True)
        manager.start(clipboard=True, tray=True)
        mock_clipboard_start.assert_called_once()
        mock_tray_start.assert_called_once()

    with patch.object(manager.clipboard_monitor, "stop") as mock_clipboard_stop, \
         patch.object(manager.tray_service, "stop") as mock_tray_stop:
        manager.stop()
        manager.stop()
        mock_clipboard_stop.assert_called()


def test_desktop_manager_does_not_start_when_disabled():
    from app.core.config import settings

    manager = DesktopManager()
    manager.start(clipboard=True, tray=True)
    assert manager.clipboard_running is False
    assert manager.tray_running is False
    manager.stop()


class TestDesktopEndpoints:
    def test_desktop_status_returns_defaults(self, client, db_session):
        response = client.get("/api/v1/desktop/status")
        assert response.status_code == 200
        body = response.json()
        assert body["clipboard_running"] is False
        assert body["tray_running"] is False
        assert body["clipboard_enabled"] is False
        assert body["tray_enabled"] is False

    def test_desktop_start_stop(self, client, db_session):
        response = client.post("/api/v1/desktop/start", json={"clipboard": False, "tray": False})
        assert response.status_code == 200
        body = response.json()
        assert body["clipboard_running"] is False
        assert body["tray_running"] is False

        response = client.post("/api/v1/desktop/stop")
        assert response.status_code == 200

    def test_desktop_pending_list_empty(self, client, db_session):
        response = client.get("/api/v1/desktop/pending")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []

    @pytest.mark.asyncio
    async def test_desktop_dismiss_and_download(self, client, db_session, monkeypatch):
        from app.models.pending_link import PendingLink, PendingLinkStatus

        link = PendingLink(url="https://www.tiktok.com/@user/video/1234567890", platform="tiktok", status=PendingLinkStatus.PENDING)
        db_session.add(link)
        await db_session.commit()
        await db_session.refresh(link)

        response = client.post(f"/api/v1/desktop/pending/{link.id}/dismiss")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "dismissed"

        link2 = PendingLink(url="https://www.youtube.com/watch?v=abc123", platform="youtube", status=PendingLinkStatus.PENDING)
        db_session.add(link2)
        await db_session.commit()
        await db_session.refresh(link2)

        fake_orchestrator = MagicMock()
        fake_orchestrator.enqueue_download = MagicMock(return_value="task-123")
        monkeypatch.setattr("app.api.v1.endpoints.desktop.DownloadOrchestrator", lambda db: fake_orchestrator)

        response = client.post(f"/api/v1/desktop/pending/{link2.id}/download")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "downloaded"
        assert "download_id" in body
