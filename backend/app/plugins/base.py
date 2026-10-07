from abc import ABC, abstractmethod
from typing import List
import re
from app.schemas.media import MediaMetadata, DownloadOption

class PlatformPlugin(ABC):
    platform_name: str = "base"
    supported_patterns: List[str] = []

    def validate_url(self, url: str) -> bool:
        """Checks if URL matches any supported patterns."""
        for pattern in self.supported_patterns:
            if re.search(pattern, url):
                return True
        return False

    @abstractmethod
    def extract_metadata(self, url: str) -> MediaMetadata:
        """Extract metadata from the target media URL."""
        pass

    @abstractmethod
    def get_download_urls(self, url: str) -> List[DownloadOption]:
        """Get the direct download links for the media."""
        pass

    @abstractmethod
    def get_profile_videos(self, profile_url: str, limit: int = 50) -> List[str]:
        """Fetch video URLs from a given user profile."""
        pass

    @abstractmethod
    def get_platform_color(self) -> str:
        """Return the UI hex color for the platform."""
        pass
