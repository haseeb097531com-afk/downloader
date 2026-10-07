"""Tests for Turbo Mode, aria2c integration, and extraction caching."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from app.services.extractor.ytdlp_engine import YTDLPEngine, YTDLPEngineError
from app.core.config import settings


@pytest.fixture
def engine():
    return YTDLPEngine()


@pytest.fixture(autouse=True)
def _reset_turbo_settings(monkeypatch):
    """Ensure each test starts with predictable turbo defaults."""
    monkeypatch.setattr(settings, "TURBO_MODE", True, raising=False)
    monkeypatch.setattr(settings, "CONCURRENT_FRAGMENTS", 16, raising=False)
    monkeypatch.setattr(settings, "ARIA2_CONNECTIONS", 16, raising=False)
    yield


class TestTurboModeAria2:
    """TASK 6: aria2 args applied when turbo on + aria2 present."""

    @patch("app.services.extractor.ytdlp_engine.shutil.which", return_value="/usr/bin/aria2c")
    @patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
    def test_turbo_adds_aria2_args_when_available(self, mock_ydl, mock_which, engine):
        """When turbo_mode=True and aria2c is on PATH, external_downloader args are set."""
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {
            "id": "vid1",
            "title": "Turbo Test",
            "extractor": "youtube",
            "formats": [
                {"format_id": "1", "ext": "mp4", "url": "http://vid1", "vcodec": "avc", "acodec": "mp4a", "height": 1080, "filesize": 1000},
            ],
        }

        engine.download_media("http://example.com/video", "/tmp/test.%(ext)s")

        called_options = mock_ydl.call_args[0][0]
        assert called_options["external_downloader"] == "aria2c"
        assert called_options["external_downloader_args"]["aria2c"] == [
            "-x16", "-s16", "-k1M", "--max-connection-per-server=16", "--min-split-size=1M"
        ]
        assert called_options["concurrent_fragments"] == 16

    @patch("app.services.extractor.ytdlp_engine.shutil.which", return_value=None)
    @patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
    def test_turbo_falls_back_without_aria2(self, mock_ydl, mock_which, engine):
        """When turbo_mode=True but aria2c is missing, native downloader is used."""
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {
            "id": "vid1",
            "title": "Fallback Test",
            "extractor": "youtube",
            "formats": [
                {"format_id": "1", "ext": "mp4", "url": "http://vid1", "vcodec": "avc", "acodec": "mp4a", "height": 720, "filesize": 500},
            ],
        }

        engine.download_media("http://example.com/video", "/tmp/test.%(ext)s")

        called_options = mock_ydl.call_args[0][0]
        assert "external_downloader" not in called_options
        assert called_options["concurrent_fragments"] == 16

    @patch("app.services.extractor.ytdlp_engine.shutil.which", return_value="/usr/bin/aria2c")
    @patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
    def test_turbo_disabled_skips_aria2(self, mock_ydl, mock_which, engine, monkeypatch):
        """When turbo_mode=False, aria2c options are never applied."""
        monkeypatch.setattr(settings, "TURBO_MODE", False, raising=False)

        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {
            "id": "vid1",
            "title": "No Turbo",
            "extractor": "youtube",
            "formats": [
                {"format_id": "1", "ext": "mp4", "url": "http://vid1", "vcodec": "avc", "acodec": "mp4a", "height": 720, "filesize": 500},
            ],
        }

        engine.download_media("http://example.com/video", "/tmp/test.%(ext)s")

        called_options = mock_ydl.call_args[0][0]
        assert "external_downloader" not in called_options
        assert "concurrent_fragments" not in called_options


class TestExtractionCache:
    """TASK 3 + TASK 6: Redis extraction cache with TTL and cache-hit bypass."""

    @patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
    def test_cache_hit_returns_without_calling_yt_dlp(self, mock_ydl, engine, fake_redis):
        """On cache hit, extract_info returns cached data and yt-dlp is not invoked."""
        url = "http://example.com/cached-video"
        cached_data = {
            "id": "cached123",
            "title": "Cached Title",
            "formats": [
                {"format_id": "1", "ext": "mp4", "url": "http://vid1", "vcodec": "avc", "acodec": "mp4a", "height": 1080, "filesize": 1000},
            ],
        }
        fake_redis.store[engine._cache_key(url)] = json.dumps(cached_data)

        result = engine.extract_info(url, download=False)

        assert result["id"] == "cached123"
        assert result["title"] == "Cached Title"
        mock_ydl.assert_not_called()

    @patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
    def test_cache_miss_writes_to_redis(self, mock_ydl, engine, fake_redis):
        """On cache miss, extract_info calls yt-dlp and writes the result to Redis."""
        url = "http://example.com/new-video"
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {
            "id": "new123",
            "title": "Fresh Title",
            "extractor": "youtube",
            "formats": [
                {"format_id": "1", "ext": "mp4", "url": "http://vid1", "vcodec": "avc", "acodec": "mp4a", "height": 720, "filesize": 500},
            ],
        }

        result = engine.extract_info(url, download=False)

        assert result["id"] == "new123"
        mock_ydl.assert_called_once()
        cached_key = engine._cache_key(url)
        assert cached_key in fake_redis.store
        cached_value = fake_redis.store[cached_key]
        assert json.loads(cached_value)["id"] == "new123"

    @patch("app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL")
    def test_cache_skipped_for_downloads(self, mock_ydl, engine, fake_redis):
        """extract_info(download=True) never reads or writes the cache."""
        url = "http://example.com/download-video"
        fake_redis.store[engine._cache_key(url)] = json.dumps({"id": "should-not-use"})

        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {
            "id": "real123",
            "title": "Real Download",
            "extractor": "youtube",
            "formats": [],
        }

        result = engine.extract_info(url, download=True)

        assert result["id"] == "real123"
        mock_ydl.assert_called_once()


class TestConcurrencyAutoTune:
    """TASK 4: Celery worker concurrency is set at import time."""

    def test_celery_concurrency_scales_with_resources(self, monkeypatch):
        """worker_concurrency should reflect ResourceGuard recommendation."""
        import app.core.celery_app as celery_module

        monkeypatch.setattr(
            "app.services.processor.resource_guard.ResourceGuard.get_recommended_concurrency",
            lambda: 4,
        )
        monkeypatch.setattr(settings, "TURBO_MODE", False, raising=False)

        import importlib
        importlib.reload(celery_module)

        assert celery_module.celery_app.conf.worker_concurrency == 4

    def test_turbo_doubles_concurrency(self, monkeypatch):
        """When turbo_mode=True, worker_concurrency should be doubled (min 1)."""
        import app.core.celery_app as celery_module

        monkeypatch.setattr(
            "app.services.processor.resource_guard.ResourceGuard.get_recommended_concurrency",
            lambda: 3,
        )
        monkeypatch.setattr(settings, "TURBO_MODE", True, raising=False)

        import importlib
        importlib.reload(celery_module)

        assert celery_module.celery_app.conf.worker_concurrency == 6
