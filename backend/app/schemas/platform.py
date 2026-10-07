from pydantic import BaseModel, Field
from typing import Optional

class PlatformInfo(BaseModel):
    platform_name: str = Field(..., description='e.g. "youtube", "tiktok", "instagram", "facebook", "twitter", "other"')
    platform_display_name: str = Field(..., description='e.g. "YouTube", "TikTok"')
    platform_color: str = Field(..., description='Hex color code for UI glow effect')
    content_type: str = Field(..., description='e.g. "video", "reel", "short", "post", "story", "live", "unknown"')
    is_profile: bool = Field(..., description='Whether the URL is a profile/user page')
    is_playlist: bool = Field(..., description='Whether the URL is a playlist/album')
    extracted_id: Optional[str] = Field(None, description='The video/post ID if detectable')
    username: Optional[str] = Field(None, description='The creator username if detectable from URL')

class ValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Whether the URL is valid and belongs to a supported platform")
    platform_info: Optional[PlatformInfo] = Field(None, description="Detailed platform info if valid")
    error_message: Optional[str] = Field(None, description="Error message if validation fails")
