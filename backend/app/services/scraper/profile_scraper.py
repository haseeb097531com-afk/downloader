from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
import logging

from app.schemas.profile import ScrapeResult
from app.schemas.platform import PlatformInfo
from app.services.extractor.platform_detector import PlatformDetector
from app.plugins.manager import plugin_manager
from app.models.profile import Profile, ProfileVideo, ProfileVideoStatus
from app.models.download import Download, DownloadStatus

logger = logging.getLogger(__name__)

class ProfileScraperError(Exception):
    pass

class ProfileScraper:
    def __init__(self):
        self.detector = PlatformDetector()

    def parse_profile_url(self, url: str) -> PlatformInfo:
        validation = self.detector.validate_url(url)
        if not validation.is_valid or not validation.platform_info:
            raise ProfileScraperError(f"Invalid URL: {validation.error_message}")
        
        info = validation.platform_info
        if not info.is_profile:
            raise ProfileScraperError(f"URL is not a profile. Detected content type: {info.content_type}")
            
        return info

    async def scrape_profile(self, db: AsyncSession, profile_url: str, limit: int = 50) -> ScrapeResult:
        info = self.parse_profile_url(profile_url)
        
        plugin = plugin_manager.get_plugin_for_url(profile_url)
        if not plugin:
            raise ProfileScraperError("No plugin found for this profile URL")
            
        video_urls = plugin.get_profile_videos(profile_url, limit=limit)
        
        result = await db.execute(select(Profile).where(Profile.profile_url == profile_url))
        profile = result.scalars().first()
        
        if not profile:
            profile = Profile(
                platform=info.platform_name,
                username=info.username or "unknown",
                profile_url=profile_url,
                display_name=info.username,
                last_scraped_at=datetime.utcnow()
            )
            db.add(profile)
            await db.flush()
        else:
            profile.last_scraped_at = datetime.utcnow()
            profile.total_videos = max(profile.total_videos, len(video_urls))
            
        new_count = 0
        skipped_count = 0
        
        for v_url in video_urls:
            v_res = await db.execute(select(ProfileVideo).where(ProfileVideo.video_url == v_url))
            existing_video = v_res.scalars().first()
            
            if existing_video:
                if existing_video.status == ProfileVideoStatus.DOWNLOADED:
                    skipped_count += 1
                continue
                
            d_res = await db.execute(select(Download).where(Download.url == v_url))
            existing_download = d_res.scalars().first()
            
            status = ProfileVideoStatus.NEW
            download_id = None
            if existing_download and existing_download.status == DownloadStatus.COMPLETED:
                status = ProfileVideoStatus.SKIPPED
                skipped_count += 1
                download_id = existing_download.id
            else:
                new_count += 1
                
            new_vid = ProfileVideo(
                profile_id=profile.id,
                video_url=v_url,
                status=status,
                download_id=download_id
            )
            db.add(new_vid)

        await db.commit()

        return ScrapeResult(
            profile_info=info,
            total_discovered=len(video_urls),
            new_count=new_count,
            skipped_count=skipped_count,
            videos=video_urls
        )
