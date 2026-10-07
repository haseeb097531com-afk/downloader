from typing import List
from app.plugins.base import PlatformPlugin
from app.schemas.media import MediaMetadata, DownloadOption
from app.services.extractor.ytdlp_engine import YTDLPEngine

class InstagramPlugin(PlatformPlugin):
    platform_name = "instagram"
    supported_patterns = [
        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/p\/([a-zA-Z0-9_-]+)",
        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/reel\/([a-zA-Z0-9_-]+)",
        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/tv\/([a-zA-Z0-9_-]+)",
        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/stories\/([a-zA-Z0-9_.-]+)\/(\d+)",
        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/([a-zA-Z0-9_.-]+)"
    ]

    def __init__(self):
        self.engine = YTDLPEngine()
        # Ensure cookie file can be used for authentication (crucial for IG)
        # self.engine.base_options['cookiefile'] = 'cookies.txt'

    def _map_to_download_option(self, format_dict: dict) -> DownloadOption:
        return DownloadOption(
            quality=format_dict.get('quality', 'unknown'),
            format_id=format_dict.get('format_id', ''),
            extension=format_dict.get('ext', 'mp4'),
            file_size_estimate=format_dict.get('filesize'),
            url=format_dict.get('url', ''),
            is_watermark_free=not format_dict.get('watermarked', False),
            codec=f"{format_dict.get('vcodec', '')}/{format_dict.get('acodec', '')}",
            resolution=f"{format_dict.get('height', '')}p" if format_dict.get('height') else None
        )

    def extract_metadata(self, url: str) -> MediaMetadata:
        raw_info = self.engine.extract_info(url, download=False)
        content_type = "post"
        if "/reel/" in url: content_type = "reel"
        elif "/tv/" in url: content_type = "tv"
        elif "/stories/" in url: content_type = "story"
        elif "/p/" not in url: content_type = "profile"
        
        return MediaMetadata(
            title=raw_info.get('title', 'Instagram Post'),
            description=raw_info.get('description'),
            duration=raw_info.get('duration'),
            thumbnail_url=raw_info.get('thumbnail'),
            uploader_name=raw_info.get('uploader'),
            uploader_url=raw_info.get('uploader_url'),
            upload_date=raw_info.get('upload_date'),
            view_count=raw_info.get('view_count'),
            like_count=raw_info.get('like_count'),
            comment_count=raw_info.get('comment_count'),
            tags=raw_info.get('tags', []),
            platform=self.platform_name,
            content_type=content_type,
            id=raw_info.get('id'),
            raw_data=raw_info
        )

    def get_download_urls(self, url: str) -> List[DownloadOption]:
        raw_info = self.engine.extract_info(url, download=False)
        return [self._map_to_download_option(f) for f in raw_info.get('formats', [])]

    def get_profile_videos(self, profile_url: str, limit: int = 50) -> List[str]:
        options = self.engine.base_options.copy()
        options.update({'extract_flat': True, 'playlistend': limit})
        import yt_dlp
        urls = []
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(profile_url, download=False)
                if 'entries' in info:
                    urls = [entry['url'] for entry in info['entries'] if entry.get('url')]
        except Exception:
            pass
        return urls

    def get_platform_color(self) -> str:
        return "#E4405F"
