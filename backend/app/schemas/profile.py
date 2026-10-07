from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.schemas.platform import PlatformInfo

class ProfileVideoBase(BaseModel):
    video_url: str
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    upload_date: Optional[str] = None
    status: str
    download_id: Optional[str] = None

class ProfileBase(BaseModel):
    platform: str
    username: str
    profile_url: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    total_videos: int = 0
    last_scraped_at: Optional[datetime] = None
    auto_download: bool = False

class ScrapeResult(BaseModel):
    profile_info: PlatformInfo
    total_discovered: int
    new_count: int
    skipped_count: int
    videos: List[str]

class BulkEnqueueResult(BaseModel):
    enqueued: int
    skipped: int
    failed: int
