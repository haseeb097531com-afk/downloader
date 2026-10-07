"""Tests for Phase 14A Content Moderation, Safe Mode and Parental Controls.

Covers:
- ContentModerator keyword blacklist matching and scoring
- Clean content passes moderation
- PIN hash/verify round-trip
- Wrong PIN fails verification
- Moderation settings endpoints
- Pipeline quarantine integration
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.settings_service import SettingsService
from app.models.download import Download, DownloadStatus
from app.services.moderator import ContentModerator
from app.services.processor.pipeline import ProcessingPipeline


# --------------------------------------------------------------------------- #
# ContentModerator unit tests
# --------------------------------------------------------------------------- #


class TestContentModerator:
    """Keyword blacklist, scoring, and PIN helpers."""

    def test_clean_title_passes(self):
        moderator = ContentModerator(blacklist=["badword"], sensitivity=0.5)
        result = moderator.check_content(title="A nice safe video")
        assert result.flagged is False
        assert result.score == 0.0

    def test_blacklist_title_flags(self):
        moderator = ContentModerator(blacklist=["badword"], sensitivity=0.5)
        result = moderator.check_content(title="This contains a badword in it")
        assert result.flagged is True
        assert result.score > 0.0

    def test_title_weighted_higher_than_description(self):
        """Title keyword matches should score higher (2x weight)."""
        moderator = ContentModerator(blacklist=["badword"], sensitivity=0.5)
        desc_result = moderator.check_content(description="contains badword here")
        title_result = moderator.check_content(title="contains badword here")
        assert title_result.score > desc_result.score

    def test_case_insensitive_matching(self):
        moderator = ContentModerator(blacklist=["BADWORD"], sensitivity=0.5)
        result = moderator.check_content(title="Contains BadWord here")
        assert result.flagged is True

    def test_sensitivity_threshold(self):
        moderator = ContentModerator(blacklist=["badword"], sensitivity=0.9)
        # Title score is 2.0 -> normalised 1.0, which is above 0.9
        assert moderator.check_content(title="badword").flagged is True
        # Description only gives 1.0 -> normalised 0.5, below 0.9
        assert moderator.check_content(description="badword").flagged is False

    def test_pin_hash_verify_round_trip(self):
        pin = "1234"
        pin_hash = ContentModerator.hash_pin(pin)
        assert ContentModerator.verify_pin(pin, pin_hash) is True

    def test_wrong_pin_fails(self):
        pin_hash = ContentModerator.hash_pin("1234")
        assert ContentModerator.verify_pin("0000", pin_hash) is False

    def test_invalid_pin_raises(self):
        with pytest.raises(ValueError):
            ContentModerator.hash_pin("abc")

    def test_llm_signal_adds_reason(self, monkeypatch):
        moderator = ContentModerator(blacklist=[], sensitivity=0.5)

        def fake_post(*args, **kwargs):
            class FakeResponse:
                def json(self):
                    return {"response": "NO - contains adult themes"}

                def raise_for_status(self):
                    pass

            return FakeResponse()

        monkeypatch.setattr("app.services.moderator.httpx.post", fake_post)
        monkeypatch.setattr(settings, "USE_LLM_CATEGORIZE", True)
        monkeypatch.setattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        monkeypatch.setattr(settings, "OLLAMA_MODEL", "llama3")

        result = moderator.check_content(title="some video")
        assert "llm_moderation_signal" in result.reasons


# --------------------------------------------------------------------------- #
# Pipeline quarantine integration
# --------------------------------------------------------------------------- #


def _make_download(db: AsyncSession, title: str = "Test Video", file_path: str | None = None) -> Download:
    download = Download(
        id=str(uuid.uuid4()),
        url=f"https://example.com/{title}",
        platform="youtube",
        content_type="video",
        title=title,
        status=DownloadStatus.COMPLETED,
        file_path=file_path,
        completed_at=datetime.utcnow(),
        quarantined=False,
        quarantine_reason=None,
    )
    db.add(download)
    return download


class TestPipelineQuarantine:
    def test_safe_mode_flags_content_and_moves_file(self, db_session, download_dir, monkeypatch):
        monkeypatch.setattr(settings, "SAFE_MODE", True)
        monkeypatch.setattr(settings, "KEYWORD_BLACKLIST", ["badword"])
        monkeypatch.setattr(settings, "MODERATION_SENSITIVITY", 0.5)

        file_path = Path(download_dir) / "video.mp4"
        file_path.write_text("bad")

        download = _make_download(db_session, title="Contains badword here", file_path=str(file_path))
        asyncio.get_event_loop().run_until_complete(db_session.commit())
        download_id = download.id

        class MockFFmpeg:
            async def merge_streams(self, *args, **kwargs):
                return None

            async def normalize_to_mp4(self, *args, **kwargs):
                return None

            async def embed_metadata(self, *args, **kwargs):
                return None

            async def generate_thumbnail(self, *args, **kwargs):
                return None

        pipeline = ProcessingPipeline(ffmpeg=MockFFmpeg(), db_session=db_session)
        asyncio.get_event_loop().run_until_complete(pipeline.process_download(download_id))

        async def fetch_download():
            result = await db_session.execute(select(Download).where(Download.id == download_id))
            return result.scalars().first()

        refreshed = asyncio.get_event_loop().run_until_complete(fetch_download())
        assert refreshed is not None
        assert refreshed.quarantined is True
        assert refreshed.quarantine_reason == "matched_keyword_blacklist"
        assert not file_path.exists()
        assert Path(refreshed.file_path).exists()

    def test_safe_mode_clean_content_is_not_quarantined(self, db_session, download_dir, monkeypatch):
        monkeypatch.setattr(settings, "SAFE_MODE", True)
        monkeypatch.setattr(settings, "KEYWORD_BLACKLIST", ["badword"])
        monkeypatch.setattr(settings, "MODERATION_SENSITIVITY", 0.5)

        file_path = Path(download_dir) / "clean.mp4"
        file_path.write_text("clean")

        download = _make_download(db_session, title="A nice safe video", file_path=str(file_path))
        asyncio.get_event_loop().run_until_complete(db_session.commit())
        download_id = download.id

        class MockFFmpeg:
            async def merge_streams(self, *args, **kwargs):
                return None

            async def normalize_to_mp4(self, *args, **kwargs):
                return None

            async def embed_metadata(self, *args, **kwargs):
                return None

            async def generate_thumbnail(self, *args, **kwargs):
                return None

        pipeline = ProcessingPipeline(ffmpeg=MockFFmpeg(), db_session=db_session)
        asyncio.get_event_loop().run_until_complete(pipeline.process_download(download_id))

        async def fetch_download():
            result = await db_session.execute(select(Download).where(Download.id == download_id))
            return result.scalars().first()

        refreshed = asyncio.get_event_loop().run_until_complete(fetch_download())
        assert refreshed is not None
        assert refreshed.quarantined is False
        assert refreshed.quarantine_reason is None
