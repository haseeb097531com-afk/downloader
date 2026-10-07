"""Tests for Phase 10A AI transcription, summarization and translation."""

from __future__ import annotations

import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.services.ai.summarizer import Summarizer
from app.services.ai.transcriber import Segment, Transcriber
from app.services.ai.translator import Translator


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


class TestTranscriber:
    def test_srt_format_is_valid(self, tmp_path):
        transcriber = Transcriber()
        segments = [
            Segment(start=0.0, end=2.5, text="Hello world"),
            Segment(start=3.0, end=5.5, text="This is a test"),
        ]
        srt_path = str(tmp_path / "out.srt")
        transcriber.write_srt(segments, srt_path)
        content = Path(srt_path).read_text(encoding="utf-8")
        assert "1\n" in content
        assert "00:00:00,000 --> 00:00:02,500" in content
        assert "Hello world" in content
        assert "2\n" in content
        assert "00:00:03,000 --> 00:00:05,500" in content
        assert "This is a test" in content

    def test_transcribe_missing_file_raises(self, tmp_path):
        transcriber = Transcriber()
        with pytest.raises(Exception):
            transcriber.transcribe(str(tmp_path / "missing.mp4"))


class TestSummarizer:
    def test_fallback_produces_summary_and_keywords(self):
        summarizer = Summarizer()
        result = summarizer.summarize("This is a test. Testing is fun. We test things. Testing makes quality. Tests pass.")
        assert result.summary
        assert len(result.keywords) <= 5

    def test_ollm_unreachable_falls_back(self, monkeypatch):
        summarizer = Summarizer()
        with patch("httpx.post", side_effect=Exception("connection refused")):
            result = summarizer.summarize("This is a test. Testing is fun. We test things. Testing makes quality. Tests pass.")
        assert result.summary
        assert len(result.keywords) <= 5


class TestTranslator:
    def test_translate_preserves_timing_lines(self, tmp_path):
        srt = tmp_path / "in.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n2\n00:00:03,000 --> 00:00:05,000\nTesting\n", encoding="utf-8")
        translator = Translator()
        fake_translator = MagicMock()
        fake_translator.translate_batch.return_value = ["Translated hello", "Translated test"]
        with patch("deep_translator.GoogleTranslator", return_value=fake_translator):
            out = str(tmp_path / "out.srt")
            translator.translate_srt(str(srt), "es", out)
        content = Path(out).read_text(encoding="utf-8")
        assert "00:00:00,000 --> 00:00:02,000" in content
        assert "00:00:03,000 --> 00:00:05,000" in content
        assert "Translated hello" in content
        assert "Translated test" in content

    def test_missing_srt_raises(self, tmp_path):
        translator = Translator()
        with pytest.raises(Exception):
            translator.translate_srt(str(tmp_path / "missing.srt"), "es", str(tmp_path / "out.srt"))


class TestAnalysisEndpoints:
    @pytest.mark.asyncio
    async def test_get_analysis_returns_404_when_missing(self, client):
        response = await client.get("/api/v1/analysis/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_run_analysis_queues_202(self, client, db_session, monkeypatch):
        from app.models.download import Download, DownloadStatus

        download = Download(
            url="https://youtube.com/watch?v=1",
            platform="youtube",
            content_type="video",
            title="Test",
            status=DownloadStatus.COMPLETED,
            file_path="",
        )
        db_session.add(download)
        await db_session.commit()
        await db_session.refresh(download)

        with patch("app.workers.ai_tasks.analysis_task.delay", return_value=MagicMock()):
            response = await client.post(f"/api/v1/analysis/{download.id}/run")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "queued"
        assert "analysis_id" in body

    @pytest.mark.asyncio
    async def test_translate_returns_404_when_no_analysis(self, client):
        response = await client.post("/api/v1/analysis/00000000-0000-0000-0000-000000000000/translate?lang=es")
        assert response.status_code == 404
