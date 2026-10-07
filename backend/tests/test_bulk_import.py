"""Tests for Phase 16A: Mass Bulk Import.

Covers:
- Bulk link import creates job + items and enqueues downloads
- Duplicate URLs are deduped within a single job
- Invalid URLs are marked failed without crashing
- Bulk profile import creates profiles and enqueues scrape tasks
- Bulk progress endpoint returns correct counts
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bulk_import import BulkJob, BulkItem, BulkJobType, BulkItemStatus
from app.models.profile import Profile
from app.services.downloader.bulk_import import BulkImportService


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_download(db: AsyncSession, url: str, platform: str = "youtube") -> str:
    from app.models.download import Download, DownloadStatus
    download = Download(
        id=str(uuid.uuid4()),
        url=url,
        platform=platform,
        content_type="video",
        title=f"Video for {url}",
        status=DownloadStatus.COMPLETED,
        progress=100.0,
        completed_at=datetime.utcnow(),
    )
    db.add(download)
    return download.id


# ------------------------------------------------------------------ #
# Bulk links import
# ------------------------------------------------------------------ #

class TestBulkLinksImport:
    def test_import_links_creates_job_and_items(self, db_session):
        urls = [f"https://youtube.com/watch?v={i}" for i in range(5)]
        service = BulkImportService(db_session)
        job = asyncio.get_event_loop().run_until_complete(service.import_links(urls))

        assert job.job_type == BulkJobType.LINKS
        assert job.total_items == 5
        assert job.processed_items == 5
        assert job.failed_items == 0

    def test_import_links_dedupes_duplicate_urls(self, db_session):
        urls = [
            "https://youtube.com/watch?v=abc",
            "https://youtube.com/watch?v=abc",
            "https://youtube.com/watch?v=def",
        ]
        service = BulkImportService(db_session)
        job = asyncio.get_event_loop().run_until_complete(service.import_links(urls))

        assert job.total_items == 2
        assert job.processed_items == 2

    def test_import_links_marks_invalid_urls_failed(self, db_session):
        urls = [
            "https://youtube.com/watch?v=abc",
            "not-a-url",
            "",
            "   ",
        ]
        service = BulkImportService(db_session)
        job = asyncio.get_event_loop().run_until_complete(service.import_links(urls))

        assert job.total_items == 2  # 1 valid + 1 invalid (empty strings skipped)
        assert job.failed_items == 1
        assert job.processed_items == 1

    def test_import_links_100_items(self, db_session):
        urls = [f"https://youtube.com/watch?v={i:04d}" for i in range(100)]
        service = BulkImportService(db_session)
        job = asyncio.get_event_loop().run_until_complete(service.import_links(urls))

        assert job.total_items == 100
        assert job.processed_items + job.failed_items == 100

    def test_import_links_sets_download_id_on_items(self, db_session):
        urls = ["https://youtube.com/watch?v=abc", "https://youtube.com/watch?v=def"]
        service = BulkImportService(db_session)
        job = asyncio.get_event_loop().run_until_complete(service.import_links(urls))

        items = asyncio.get_event_loop().run_until_complete(
            db_session.execute(select(BulkItem).where(BulkItem.job_id == job.id))
        )
        items = items.scalars().all()
        queued = [i for i in items if i.status == BulkItemStatus.QUEUED]
        assert len(queued) == job.processed_items
        for item in queued:
            assert item.download_id is not None


# ------------------------------------------------------------------ #
# Bulk profiles import
# ------------------------------------------------------------------ #

class TestBulkProfilesImport:
    def test_import_profiles_creates_profile_records(self, db_session, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.DOWNLOAD_DIR", str(tmp_path))
        urls = [f"https://youtube.com/@channel{i}" for i in range(10)]
        service = BulkImportService(db_session)

        with monkeypatch.context() as m:
            m.setattr("app.workers.scrape_tasks.scrape_profile_task.delay", lambda *args, **kwargs: None)
            job = asyncio.get_event_loop().run_until_complete(service.import_profiles(urls, limit=10))

        assert job.job_type == BulkJobType.PROFILES
        assert job.total_items == 10
        assert job.processed_items == 10

        profiles = asyncio.get_event_loop().run_until_complete(
            db_session.execute(select(Profile))
        )
        profiles = profiles.scalars().all()
        assert len(profiles) == 10
        usernames = {p.username for p in profiles}
        assert len(usernames) == 10

    def test_import_profiles_creates_own_folder(self, db_session, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.DOWNLOAD_DIR", str(tmp_path))
        urls = ["https://youtube.com/@mychannel"]
        service = BulkImportService(db_session)

        with monkeypatch.context() as m:
            m.setattr("app.workers.scrape_tasks.scrape_profile_task.delay", lambda *args, **kwargs: None)
            asyncio.get_event_loop().run_until_complete(service.import_profiles(urls, limit=10))

        profile = asyncio.get_event_loop().run_until_complete(
            db_session.execute(select(Profile).where(Profile.profile_url == urls[0]))
        )
        profile = profile.scalars().first()
        assert profile is not None

        folder = Path(tmp_path) / "youtube"
        assert folder.exists()

    def test_import_profiles_dedupes_duplicate_urls(self, db_session, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.DOWNLOAD_DIR", str(tmp_path))
        urls = ["https://youtube.com/@channel1", "https://youtube.com/@channel1"]
        service = BulkImportService(db_session)

        with monkeypatch.context() as m:
            m.setattr("app.workers.scrape_tasks.scrape_profile_task.delay", lambda *args, **kwargs: None)
            job = asyncio.get_event_loop().run_until_complete(service.import_profiles(urls, limit=10))

        profiles = asyncio.get_event_loop().run_until_complete(
            db_session.execute(select(Profile))
        )
        profiles = profiles.scalars().all()
        assert len(profiles) == 1
        assert job.total_items == 1

    def test_import_profiles_marks_invalid_failed(self, db_session, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.DOWNLOAD_DIR", str(tmp_path))
        urls = ["https://youtube.com/@good", "not-a-url"]
        service = BulkImportService(db_session)

        with monkeypatch.context() as m:
            m.setattr("app.workers.scrape_tasks.scrape_profile_task.delay", lambda *args, **kwargs: None)
            job = asyncio.get_event_loop().run_until_complete(service.import_profiles(urls, limit=10))

        assert job.total_items == 2
        assert job.failed_items == 1
        assert job.processed_items == 1


# ------------------------------------------------------------------ #
# Progress
# ------------------------------------------------------------------ #

class TestBulkProgress:
    def test_get_job_progress_returns_counts(self, db_session):
        urls = [f"https://youtube.com/watch?v={i}" for i in range(10)]
        service = BulkImportService(db_session)
        job = asyncio.get_event_loop().run_until_complete(service.import_links(urls))

        progress = asyncio.get_event_loop().run_until_complete(
            service.get_job_progress(job.id)
        )
        assert progress["total"] == 10
        assert progress["processed"] + progress["failed"] == 10
        assert progress["percent"] == 100.0
        assert len(progress["items"]) == 10
