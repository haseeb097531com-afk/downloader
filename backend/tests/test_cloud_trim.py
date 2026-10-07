"""Phase 9A tests: video section trim and cloud backup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core.config import settings
from app.db.database import get_db
from app.services.cloud.cloud_sync import CloudTokenStore, GoogleDriveClient, DropboxClient, get_client
from app.services.extractor.ytdlp_engine import YTDLPEngine
from app.workers.cloud_tasks import _build_cloud_folder


# ---------------------------------------------------------------------------
# Trim download tests
# ---------------------------------------------------------------------------

@patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
def test_trim_download_sections_and_filename_suffix(mock_ydl):
    engine = YTDLPEngine()
    mock_instance = MagicMock()
    mock_ydl.return_value.__enter__.return_value = mock_instance
    info = {
        "id": "vid123",
        "title": "Amazing Video",
        "ext": "mp4",
        "extractor": "youtube",
    }
    mock_instance.extract_info.return_value = info
    mock_instance.prepare_filename.return_value = "/downloads/youtube/Amazing Video.mp4"

    result = engine.download_media(
        "https://youtube.com/watch?v=vid123",
        "/downloads/youtube/%(title)s.%(ext)s",
        start_time="00:01:30",
        end_time="00:05:00",
    )
    assert result.replace("\\", "/") == "/downloads/youtube/Amazing Video [00:01:30-00:05:00].mp4"
    options_passed = mock_ydl.call_args[0][0]
    assert options_passed["download_sections"] == ["*00:01:30-00:05:00"]


@patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
def test_trim_with_seconds(mock_ydl):
    engine = YTDLPEngine()
    mock_instance = MagicMock()
    mock_ydl.return_value.__enter__.return_value = mock_instance
    info = {
        "id": "vid456",
        "title": "Clip",
        "ext": "mp4",
        "extractor": "youtube",
    }
    mock_instance.extract_info.return_value = info
    mock_instance.prepare_filename.return_value = "/downloads/youtube/Clip.mp4"

    result = engine.download_media(
        "https://youtube.com/watch?v=vid456",
        "/downloads/youtube/%(title)s.%(ext)s",
        start_time="30",
        end_time="120",
    )
    assert result.replace("\\", "/") == "/downloads/youtube/Clip [30-120].mp4"
    options_passed = mock_ydl.call_args[0][0]
    assert options_passed["download_sections"] == ["*30-120"]


@patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
def test_no_trim_keeps_original_filename(mock_ydl):
    engine = YTDLPEngine()
    mock_instance = MagicMock()
    mock_ydl.return_value.__enter__.return_value = mock_instance
    info = {
        "id": "vid789",
        "title": "Full Video",
        "ext": "mp4",
        "extractor": "youtube",
    }
    mock_instance.extract_info.return_value = info
    mock_instance.prepare_filename.return_value = "/downloads/youtube/Full Video.mp4"

    result = engine.download_media(
        "https://youtube.com/watch?v=vid789",
        "/downloads/youtube/%(title)s.%(ext)s",
    )
    assert result.replace("\\", "/") == "/downloads/youtube/Full Video.mp4"
    options_passed = mock_ydl.call_args[0][0]
    assert "download_sections" not in options_passed


# ---------------------------------------------------------------------------
# Token encryption tests
# ---------------------------------------------------------------------------

def test_token_round_trip(tmp_path, monkeypatch):
    token_file = tmp_path / "cloud_tokens.json"
    monkeypatch.setattr(settings, "CLOUD_TOKENS_FILE", str(token_file))
    CloudTokenStore.clear()

    CloudTokenStore.set("google", "ya29.secret_token")
    CloudTokenStore.set("dropbox", "sl.secret_token")

    loaded = CloudTokenStore.load()
    assert loaded["google"] == "ya29.secret_token"
    assert loaded["dropbox"] == "sl.secret_token"
    assert not token_file.read_text().startswith("{")


def test_token_delete(tmp_path, monkeypatch):
    token_file = tmp_path / "cloud_tokens.json"
    monkeypatch.setattr(settings, "CLOUD_TOKENS_FILE", str(token_file))
    CloudTokenStore.clear()

    CloudTokenStore.set("google", "ya29.token")
    assert CloudTokenStore.get("google") == "ya29.token"

    CloudTokenStore.delete("google")
    assert CloudTokenStore.get("google") is None
    assert CloudTokenStore.load().get("google") is None


def test_corrupt_token_file(tmp_path, monkeypatch):
    token_file = tmp_path / "cloud_tokens.json"
    monkeypatch.setattr(settings, "CLOUD_TOKENS_FILE", str(token_file))
    token_file.write_bytes(b"not-valid-json")

    result = CloudTokenStore.load()
    assert result == {}


# ---------------------------------------------------------------------------
# Cloud folder path tests
# ---------------------------------------------------------------------------

class _FakeDownload:
    def __init__(self, platform, category, metadata_json):
        self.platform = platform
        self.category = category
        self.metadata_json = metadata_json


def test_build_cloud_folder():
    download = _FakeDownload(
        platform="youtube",
        category="Music",
        metadata_json={"uploader_name": "TopArtist"},
    )
    assert _build_cloud_folder(download) == "MediaVault/youtube/@TopArtist/music"


def test_build_cloud_folder_fallback_username():
    download = _FakeDownload(
        platform="tiktok",
        category="Clips",
        metadata_json={},
    )
    assert _build_cloud_folder(download) == "MediaVault/tiktok/@unknown/clips"


# ---------------------------------------------------------------------------
# Cloud client connection tests
# ---------------------------------------------------------------------------

@patch("requests.post")
def test_google_exchange_code(mock_post, tmp_path, monkeypatch):
    from app.core.config import settings as s

    token_file = tmp_path / "cloud_tokens.json"
    monkeypatch.setattr(s, "CLOUD_TOKENS_FILE", str(token_file))
    monkeypatch.setattr(s, "GOOGLE_DRIVE_CLIENT_ID", "client-id")
    monkeypatch.setattr(s, "GOOGLE_DRIVE_CLIENT_SECRET", "client-secret")
    CloudTokenStore.clear()

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"access_token": "ya29.new_token"}

    client = GoogleDriveClient()
    client.exchange_code("auth-code-123")
    assert CloudTokenStore.get("google") == "ya29.new_token"


@patch("requests.post")
def test_dropbox_connect(mock_post, tmp_path, monkeypatch):
    token_file = tmp_path / "cloud_tokens.json"
    monkeypatch.setattr(settings, "CLOUD_TOKENS_FILE", str(token_file))
    CloudTokenStore.clear()

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"account_id": "dbid:test"}

    client = DropboxClient()
    client.connect("sl.new_token")
    assert CloudTokenStore.get("dropbox") == "sl.new_token"
    assert client.is_connected()


@patch("requests.post")
def test_dropbox_connect_invalid_token(mock_post):
    mock_post.return_value.status_code = 401
    mock_post.return_value.raise_for_status.side_effect = Exception("Invalid token")

    client = DropboxClient()
    with pytest.raises(Exception):
        client.connect("invalid-token")


def test_get_client_returns_none_when_not_connected():
    assert get_client("google") is None
    assert get_client("dropbox") is None
    assert get_client("unknown") is None


# ---------------------------------------------------------------------------
# Endpoint tests using dependency overrides
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cloud_status_endpoint(async_client):
    response = await async_client.get("/api/v1/cloud/status")
    assert response.status_code == 200
    data = response.json()
    assert "google_connected" in data
    assert "dropbox_connected" in data
    assert "cloud_backup_enabled" in data
    assert "cloud_provider" in data


@pytest.mark.asyncio
async def test_google_callback_stores_token(async_client, tmp_path, monkeypatch):
    from app.main import app

    token_file = tmp_path / "cloud_tokens.json"
    monkeypatch.setattr(settings, "CLOUD_TOKENS_FILE", str(token_file))
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_CLIENT_SECRET", "client-secret")

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "ya29.callback_token"}

        response = await async_client.get("/api/v1/cloud/google/callback?code=auth-code")
    assert response.status_code == 200
    assert "Connected" in response.json().get("html", "")

    assert CloudTokenStore.get("google") == "ya29.callback_token"


@pytest.mark.asyncio
async def test_manual_backup_enqueues_task(async_client, db_session, tmp_path, monkeypatch):
    from app.models.download import Download, DownloadStatus
    from app.main import app

    download = Download(
        url="https://example.com/video",
        platform="youtube",
        content_type="video",
        title="Test Video",
        status=DownloadStatus.COMPLETED,
        file_path=str(tmp_path / "test.mp4"),
    )
    (tmp_path / "test.mp4").write_text("fake")
    db_session.add(download)
    await db_session.commit()
    await db_session.refresh(download)

    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "dropbox")
    monkeypatch.setattr(settings, "CLOUD_BACKUP_ENABLED", True)

    fake_client = MagicMock()
    fake_client.upload_file.return_value = "https://dropbox.com/file/123"

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.workers.cloud_tasks.cloud_upload_task.delay") as mock_delay, \
             patch("app.api.v1.endpoints.cloud.get_client", return_value=fake_client):
            mock_delay.return_value.id = "task-123"
            response = await async_client.post(f"/api/v1/downloads/{download.id}/backup")
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        assert response.json()["task_id"] == "task-123"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_manual_backup_requires_completed(async_client, db_session, monkeypatch):
    from app.models.download import Download, DownloadStatus
    from app.main import app

    download = Download(
        url="https://example.com/video",
        platform="youtube",
        content_type="video",
        title="Pending Video",
        status=DownloadStatus.PENDING,
    )
    db_session.add(download)
    await db_session.commit()
    await db_session.refresh(download)

    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "dropbox")
    monkeypatch.setattr(settings, "CLOUD_BACKUP_ENABLED", True)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = await async_client.post(f"/api/v1/downloads/{download.id}/backup")
        assert response.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)
