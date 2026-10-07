from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class DownloadOption(BaseModel):
    quality: str = Field(..., description="Human-readable quality")
    format_id: str = Field(..., description="yt-dlp format ID")
    extension: str = Field(..., description="File extension")
    file_size_estimate: Optional[int] = Field(None, description="Estimated file size in bytes")
    url: str = Field(..., description="Direct stream URL")
    is_watermark_free: bool = Field(False, description="Whether the media contains no watermark")
    codec: Optional[str] = Field(None, description="Video/Audio codec info")
    resolution: Optional[str] = Field(None, description="Resolution if applicable")

class MediaMetadata(BaseModel):
    title: str = Field(..., description="Title of the media")
    description: Optional[str] = Field(None, description="Description of the media")
    duration: Optional[int] = Field(None, description="Duration in seconds")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    uploader_name: Optional[str] = Field(None, description="Uploader or author name")
    uploader_url: Optional[str] = Field(None, description="Uploader profile URL")
    upload_date: Optional[str] = Field(None, description="Upload date")
    view_count: Optional[int] = Field(None, description="Number of views")
    like_count: Optional[int] = Field(None, description="Number of likes")
    comment_count: Optional[int] = Field(None, description="Number of comments")
    tags: List[str] = Field(default_factory=list, description="Associated tags")
    platform: str = Field(..., description="Platform name")
    content_type: str = Field(..., description="Type of content")
    
    # Internal usage fields for plugin implementations
    id: Optional[str] = None
    formats: List[DownloadOption] = Field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None
