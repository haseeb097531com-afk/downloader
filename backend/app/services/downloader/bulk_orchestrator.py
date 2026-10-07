from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import logging
from typing import Optional, List
from app.models.user import User
from app.api.deps_auth import OwnerFilter, visible_users
from app.core.config import settings
from app.models.profile import ProfileVideo, ProfileVideoStatus
from app.models.download import Download, DownloadStatus
from app.schemas.profile import BulkEnqueueResult
from app.services.downloader.download_orchestrator import DownloadOrchestrator

class BulkOrchestrator:
    def __init__(self, db: AsyncSession, current_user: Optional[User] = None) -> None:
        self.db = db
        self.current_user = current_user

    async def _owner_query(self, query, model):
        if self.current_user is not None:
            visible = await visible_users(self.current_user, self.db)
            return OwnerFilter.apply(self.current_user, query, model, visible_user_ids=visible)
        return query

    async def enqueue_profile_videos(self, profile_id: str, video_ids: list[str] = None, quality: str = "best") -> BulkEnqueueResult:
        query = self._owner_query(select(ProfileVideo).where(ProfileVideo.profile_id == profile_id), ProfileVideo)
        if video_ids:
            query = query.where(ProfileVideo.id.in_(video_ids))
        else:
            query = query.where(ProfileVideo.status == ProfileVideoStatus.NEW)
            
        result = await self.db.execute(query)
        videos = result.scalars().all()
        
        orchestrator = DownloadOrchestrator(self.db, current_user=self.current_user)
        
        enqueued = 0
        skipped = 0
        failed = 0
        
        for video in videos:
            if video.status in [ProfileVideoStatus.QUEUED, ProfileVideoStatus.DOWNLOADED]:
                skipped += 1
                continue
                
            try:
                download = await orchestrator.create_download(
                    video.video_url,
                    force=True,
                    platform="bulk",
                )
                download.quality = quality
                download.title = f"Bulk Download {video.id}"
                video.status = ProfileVideoStatus.QUEUED
                video.download_id = download.id
                enqueued += 1
            except Exception as exc:
                logging.error("Failed to enqueue profile video %s: %s", video.id, exc)
                failed += 1
            
        await self.db.commit()
        return BulkEnqueueResult(enqueued=enqueued, skipped=skipped, failed=failed)

    async def enqueue_auto_profiles(self):
        pass # Phase 12 logic
