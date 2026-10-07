"""Tests for Phase 8A AI auto-categorization and storage guard."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient

from app.services.ai.categorizer import ContentCategorizer
from app.services.storage.storage_guard import get_disk_status


@pytest_asyncio.fixture
async def client(db_session, download_dir, monkeypatch):
    import app.main as main_module
    from app.db.database import get_db
    from app.core.config import settings as app_settings

    async def override_get_db():
        yield db_session

    monkeypatch.setattr(app_settings, "DATA_DIR", str(download_dir))
    app = main_module.app
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client

    app.dependency_overrides.clear()


class TestContentCategorizer:
    def test_gaming_keyword_match(self):
        categorizer = ContentCategorizer()
        result = categorizer.categorize(title="Epic gaming highlights 2024", description="", tags=[])
        assert result.category == "Gaming"
        assert result.confidence > 0

    def test_cooking_keyword_match(self):
        categorizer = ContentCategorizer()
        result = categorizer.categorize(title="Easy chicken recipe in 10 minutes", description="", tags=[])
        assert result.category == "Cooking"
        assert result.confidence > 0

    def test_nonsense_text_returns_other(self):
        categorizer = ContentCategorizer()
        result = categorizer.categorize(title="asdf qwerty zxcv", description="no keywords here at all", tags=[])
        assert result.category == "Other"

    def test_confidence_threshold(self, monkeypatch):
        monkeypatch.setattr("app.services.ai.categorizer.settings.MIN_CONFIDENCE", 0.9)
        categorizer = ContentCategorizer()
        # Two categories match weakly -> confidence below 0.9
        result = categorizer.categorize(title="news gaming", description="some text", tags=[])
        assert result.category == "Other"

    def test_tags_weighted_equally_to_title(self):
        categorizer = ContentCategorizer()
        result = categorizer.categorize(title="random", description="random text", tags=["gaming"])
        assert result.category == "Gaming"

    def test_llm_fallback_on_keyword_other(self, monkeypatch):
        monkeypatch.setattr("app.services.ai.categorizer.settings.USE_LLM_CATEGORIZE", True)
        monkeypatch.setattr("app.services.ai.categorizer.settings.OLLAMA_HOST", "http://localhost:11434")
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"response": "Gaming"}

        categorizer = ContentCategorizer()
        with patch("httpx.post", return_value=fake_response):
            result = categorizer.categorize(title="random", description="random text", tags=[])
        assert result.category == "Gaming"
        assert result.confidence == 0.95

    def test_llm_falls_back_on_error(self, monkeypatch):
        monkeypatch.setattr("app.services.ai.categorizer.settings.USE_LLM_CATEGORIZE", True)
        monkeypatch.setattr("app.services.ai.categorizer.settings.OLLAMA_HOST", "http://localhost:11434")

        categorizer = ContentCategorizer()
        with patch("httpx.post", side_effect=Exception("connection refused")):
            result = categorizer.categorize(title="random", description="random text", tags=[])
        assert result.category == "Other"


class TestPipelineAutoMove:
    @pytest.mark.asyncio
    async def test_file_move_updates_db_path(self, tmp_path, db_session, monkeypatch):
        from app.models.download import Download, DownloadStatus
        from app.services.processor.pipeline import ProcessingPipeline

        download_dir = tmp_path / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        platform_dir = download_dir / "youtube"
        platform_dir.mkdir(parents=True, exist_ok=True)
        src = platform_dir / "video.mp4"
        src.write_bytes(b"fake video data")

        monkeypatch.setattr("app.core.config.settings.AUTO_CATEGORIZE", True)
        monkeypatch.setattr("app.core.config.settings.AUTO_MERGE", False)
        monkeypatch.setattr("app.core.config.settings.EMBED_METADATA", False)
        monkeypatch.setattr("app.core.config.settings.GENERATE_THUMBNAILS", False)
        monkeypatch.setattr("app.core.config.settings.DOWNLOAD_DIR", str(download_dir))

        download = Download(
            url="https://youtube.com/watch?v=abc123",
            platform="youtube",
            content_type="video",
            title="Epic gaming highlights",
            file_path=str(src),
            status=DownloadStatus.COMPLETED,
            metadata_json={"uploader_name": "Gamer123", "description": "Best gaming moments", "tags": ["gaming"]},
        )
        db_session.add(download)
        await db_session.commit()
        await db_session.refresh(download)

        pipeline = ProcessingPipeline(db_session=db_session)
        await pipeline.process_download(download.id)

        result = await db_session.execute(
            __import__("sqlalchemy").select(Download).where(Download.id == download.id)
        )
        updated = result.scalars().first()
        assert updated.category == "Gaming"
        assert updated.file_path is not None
        assert "Gaming" in updated.file_path
        assert not src.exists()

    @pytest.mark.asyncio
    async def test_move_failure_keeps_original_path(self, tmp_path, db_session, monkeypatch):
        from app.models.download import Download, DownloadStatus
        from app.services.processor.pipeline import ProcessingPipeline

        download_dir = tmp_path / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        platform_dir = download_dir / "youtube"
        platform_dir.mkdir(parents=True, exist_ok=True)
        src = platform_dir / "video.mp4"
        src.write_bytes(b"fake video data")

        monkeypatch.setattr("app.core.config.settings.AUTO_CATEGORIZE", True)
        monkeypatch.setattr("app.core.config.settings.AUTO_MERGE", False)
        monkeypatch.setattr("app.core.config.settings.EMBED_METADATA", False)
        monkeypatch.setattr("app.core.config.settings.GENERATE_THUMBNAILS", False)
        monkeypatch.setattr("app.core.config.settings.DOWNLOAD_DIR", str(download_dir))

        download = Download(
            url="https://youtube.com/watch?v=abc123",
            platform="youtube",
            content_type="video",
            title="Epic gaming highlights",
            file_path=str(src),
            status=DownloadStatus.COMPLETED,
            metadata_json={"uploader_name": "Gamer123", "description": "Best gaming moments", "tags": ["gaming"]},
        )
        db_session.add(download)
        await db_session.commit()
        await db_session.refresh(download)

        with patch("shutil.move", side_effect=OSError("disk full")):
            pipeline = ProcessingPipeline(db_session=db_session)
            await pipeline.process_download(download.id)

        result = await db_session.execute(
            __import__("sqlalchemy").select(Download).where(Download.id == download.id)
        )
        updated = result.scalars().first()
        assert updated.file_path == str(src)
        assert updated.processing_error is not None


class TestStorageGuard:
    def test_disk_status_shape(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.DOWNLOAD_DIR", str(tmp_path))
        (tmp_path / "file.txt").write_text("x")
        status = get_disk_status(str(tmp_path))
        assert hasattr(status, "total_gb")
        assert hasattr(status, "free_gb")
        assert hasattr(status, "used_percent")
        assert hasattr(status, "guard_active")

    @pytest.mark.asyncio
    async def test_storage_monitor_sets_flag_when_low(self, monkeypatch, fake_redis):
        from app.workers.monitor_tasks import storage_monitor_task
        from app.services.storage.storage_guard import DiskStatus

        monkeypatch.setattr("app.workers.monitor_tasks.get_disk_status", lambda: DiskStatus(total_gb=100.0, free_gb=0.1, used_percent=99.9, guard_active=True))

        storage_monitor_task()

        assert fake_redis.store.get("storage_guard") == "1"
        published = [json.loads(m) for _, m in fake_redis.published]
        assert any(item.get("type") == "storage_low" for item in published)

    @pytest.mark.asyncio
    async def test_storage_monitor_clears_flag_when_recovered(self, monkeypatch, fake_redis):
        from app.workers.monitor_tasks import storage_monitor_task
        from app.services.storage.storage_guard import DiskStatus

        fake_redis.store["storage_guard"] = "1"
        monkeypatch.setattr("app.workers.monitor_tasks.get_disk_status", lambda: DiskStatus(total_gb=100.0, free_gb=10.0, used_percent=10.0, guard_active=False))

        storage_monitor_task()

        assert "storage_guard" not in fake_redis.store
        published = [json.loads(m) for _, m in fake_redis.published]
        assert any(item.get("type") == "storage_ok" for item in published)


class TestEndpoints:
    @pytest.mark.asyncio
    async def test_system_disk_endpoint(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.DOWNLOAD_DIR", str(tmp_path))
        response = await client.get("/api/v1/system/disk")
        assert response.status_code == 200
        body = response.json()
        assert "total_gb" in body
        assert "free_gb" in body
        assert "used_percent" in body
        assert "guard_active" in body

    @pytest.mark.asyncio
    async def test_library_categories_endpoint_empty(self, client):
        response = await client.get("/api/v1/library/categories")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_library_category_filter(self, client, db_session, monkeypatch):
        from app.models.download import Download, DownloadStatus

        download_dir = Path(client.base_url.host or ".").resolve() / "tmp_downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        file_path = download_dir / "video.mp4"
        file_path.write_bytes(b"x")

        d1 = Download(
            url="https://youtube.com/watch?v=1",
            platform="youtube",
            content_type="video",
            title="Gaming video",
            file_path=str(file_path),
            status=DownloadStatus.COMPLETED,
            category="Gaming",
        )
        d2 = Download(
            url="https://youtube.com/watch?v=2",
            platform="youtube",
            content_type="video",
            title="Cooking video",
            file_path=str(file_path),
            status=DownloadStatus.COMPLETED,
            category="Cooking",
        )
        db_session.add_all([d1, d2])
        await db_session.commit()

        response = await client.get("/api/v1/library?category=Gaming")
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["category"] == "Gaming"
