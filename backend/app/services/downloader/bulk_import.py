"""Mass bulk import service for Phase 16A.

Supports two modes:
- ``links``: ingest a list of video URLs, dedupe, validate and enqueue them all.
- ``profiles``: ingest a list of profile URLs, create/find each profile and kick off
  scraping plus automatic video downloads for each.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.bulk_import import BulkJob, BulkItem, BulkJobStatus, BulkItemStatus, BulkJobType
from app.models.profile import Profile
from app.models.user import User
from app.api.deps_auth import OwnerFilter, visible_users
from app.services.extractor.platform_detector import PlatformDetector
from app.services.downloader.download_orchestrator import DownloadOrchestrator
from app.services.scraper.profile_scraper import ProfileScraper
from app.services.storage.file_manager import FileManager

logger = logging.getLogger(__name__)


class BulkImportService:
    """Coordinates bulk ingestion of links or profile URLs."""

    def __init__(self, db: AsyncSession, current_user: Optional[User] = None) -> None:
        self.db = db
        self.current_user = current_user
        self.detector = PlatformDetector()

    async def _owner_query(self, query, model):
        if self.current_user is not None:
            visible = await visible_users(self.current_user, self.db)
            return OwnerFilter.apply(self.current_user, query, model, visible_user_ids=visible)
        return query

    # ------------------------------------------------------------------ #
    # Links import
    # ------------------------------------------------------------------ #

    async def import_links(self, urls: List[str]) -> BulkJob:
        """Import a list of video URLs as a single bulk job.

        Each URL is normalised, deduped against the job itself, and validated
        via ``PlatformDetector``. Invalid URLs become ``failed`` ``BulkItem``
        rows so the caller still receives a full accounting.
        """
        job = BulkJob(
            job_type=BulkJobType.LINKS,
            total_items=0,
            owner_id=self.current_user.id if self.current_user else None,
        )
        self.db.add(job)
        await self.db.flush()

        seen_urls: set[str] = set()
        valid_items: List[BulkItem] = []

        for raw_url in urls:
            url = (raw_url or "").strip()
            if not url:
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            platform = None
            username = None
            try:
                validation = self.detector.validate_url(url)
                if not validation.is_valid or not validation.platform_info:
                    item = BulkItem(
                        job_id=job.id,
                        url=url,
                        platform=None,
                        username=None,
                        status=BulkItemStatus.FAILED,
                        error=f"Invalid URL: {validation.error_message or 'unsupported platform'}",
                    )
                    self.db.add(item)
                    continue
                info = validation.platform_info
                platform = info.platform_name
                username = info.username
            except Exception as exc:
                item = BulkItem(
                    job_id=job.id,
                    url=url,
                    platform=None,
                    username=None,
                    status=BulkItemStatus.FAILED,
                    error=f"Invalid URL: {exc}",
                )
                self.db.add(item)
                continue

            item = BulkItem(
                job_id=job.id,
                url=url,
                platform=platform,
                username=username,
                status=BulkItemStatus.PENDING,
            )
            self.db.add(item)
            valid_items.append(item)

        job.total_items = len(valid_items) + sum(1 for i in self.db.new if isinstance(i, BulkItem) and i.job_id == job.id and i.status == BulkItemStatus.FAILED)
        await self.db.flush()

        orchestrator = DownloadOrchestrator(self.db)
        processed = 0
        failed = 0
        for item in valid_items:
            try:
                download = await orchestrator.create_download(item.url, force=True)
                item.status = BulkItemStatus.QUEUED
                item.download_id = download.id
                processed += 1
            except Exception as exc:
                logger.warning("Bulk import link failed %s: %s", item.url, exc)
                item.status = BulkItemStatus.FAILED
                item.error = str(exc)[:500]
                failed += 1

        job.processed_items = processed
        job.failed_items = failed + (job.total_items - len(valid_items))
        if job.failed_items == 0:
            job.status = BulkJobStatus.COMPLETED
        elif job.processed_items == 0:
            job.status = BulkJobStatus.RUNNING
        else:
            job.status = BulkJobStatus.PARTIAL

        await self.db.commit()
        return job

    # ------------------------------------------------------------------ #
    # Profiles import
    # ------------------------------------------------------------------ #

    async def import_profiles(self, profile_urls: List[str], limit: int = 50, bulk_job_id: Optional[str] = None) -> BulkJob:
        """Import a list of profile URLs.

        Each unique profile URL gets (or creates) a ``Profile`` record and its
        dedicated ``platform/@username`` folder. ``scrape_profile_task`` is
        enqueued for every profile.
        """
        if bulk_job_id:
            job = await self.db.get(BulkJob, bulk_job_id)
            if not job:
                raise ValueError("Bulk job not found")
        else:
            job = BulkJob(
                job_type=BulkJobType.PROFILES,
                total_items=0,
                owner_id=self.current_user.id if self.current_user else None,
            )
            self.db.add(job)
            await self.db.flush()

        seen_urls: set[str] = set()
        processed = 0
        failed = 0

        for raw_url in profile_urls:
            url = (raw_url or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            item = BulkItem(
                job_id=job.id,
                url=url,
                status=BulkItemStatus.PENDING,
            )
            self.db.add(item)

            platform = None
            username = None
            try:
                validation = self.detector.validate_url(url)
                if not validation.is_valid or not validation.platform_info:
                    item.status = BulkItemStatus.FAILED
                    item.error = f"Invalid URL: {validation.error_message or 'unsupported platform'}"
                    failed += 1
                    continue
                info = validation.platform_info
                platform = info.platform_name
                username = info.username
            except Exception as exc:
                item.status = BulkItemStatus.FAILED
                item.error = f"Invalid URL: {exc}"
                failed += 1
                continue

            item.platform = platform
            item.username = username

            profile = await self._get_or_create_profile(url, platform, username)
            FileManager().ensure_parent_dir(self._profile_folder(profile))
            try:
                from app.workers.scrape_tasks import scrape_profile_task
                scrape_profile_task.delay(url, limit)
                item.status = BulkItemStatus.QUEUED
                processed += 1
            except Exception as exc:
                logger.warning("Bulk import profile enqueue failed %s: %s", url, exc)
                item.status = BulkItemStatus.FAILED
                item.error = str(exc)[:500]
                failed += 1

        job.total_items = processed + failed
        job.processed_items = processed
        job.failed_items = failed
        if failed == 0 and processed > 0:
            job.status = BulkJobStatus.COMPLETED
        elif processed > 0:
            job.status = BulkJobStatus.PARTIAL
        await self.db.commit()
        return job

    # ------------------------------------------------------------------ #
    # Progress
    # ------------------------------------------------------------------ #

    async def get_job_progress(self, job_id: str) -> dict:
        result = await self.db.execute(
            self._owner_query(select(BulkJob).where(BulkJob.id == job_id), BulkJob)
        )
        job = result.scalars().first()
        if not job:
            raise ValueError("Bulk job not found")

        result = await self.db.execute(
            self._owner_query(select(BulkItem).where(BulkItem.job_id == job_id), BulkItem)
        )
        items = result.scalars().all()

        processed = sum(1 for i in items if i.status in (BulkItemStatus.COMPLETED, BulkItemStatus.QUEUED, BulkItemStatus.DOWNLOADING))
        failed = sum(1 for i in items if i.status == BulkItemStatus.FAILED)
        percent = 0.0
        if job.total_items > 0:
            percent = round((processed + failed) / job.total_items * 100, 1)

        return {
            "job_id": job.id,
            "total": job.total_items,
            "processed": processed,
            "failed": failed,
            "percent": percent,
            "status": job.status.value,
            "items": [
                {
                    "id": i.id,
                    "url": i.url,
                    "platform": i.platform,
                    "username": i.username,
                    "status": i.status.value,
                    "error": i.error,
                    "download_id": i.download_id,
                }
                for i in items
            ],
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _get_or_create_profile(self, profile_url: str, platform: str, username: str):
        result = await self.db.execute(select(Profile).where(Profile.profile_url == profile_url))
        profile = result.scalars().first()
        if profile:
            return profile
        profile = Profile(
            platform=platform,
            username=username or "unknown",
            profile_url=profile_url,
            display_name=username,
            last_scraped_at=datetime.utcnow(),
            owner_id=self.current_user.id if self.current_user else None,
        )
        self.db.add(profile)
        await self.db.flush()
        return profile

    @staticmethod
    def _profile_folder(profile: Profile) -> str:
        safe_username = (profile.username or "unknown").replace("/", "_").replace("\\", "_")
        return f"{profile.platform}/@{safe_username}"
