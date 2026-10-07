import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import requests
from app.schemas.platform import PlatformInfo, ValidationResult
from app.core.config import settings

class PlatformDetector:
    """
    Detects and analyzes social media URLs to identify the platform, 
    content type, and other relevant metadata.
    """
    
    PLATFORM_COLORS = {
        "youtube": "#FF0000",
        "tiktok": "#00F2EA",
        "instagram": "#E4405F",
        "facebook": "#1877F2",
        "twitter": "#1DA1F2",
        "other": "#6C5CE7"
    }

    PLATFORM_DISPLAY_NAMES = {
        "youtube": "YouTube",
        "tiktok": "TikTok",
        "instagram": "Instagram",
        "facebook": "Facebook",
        "twitter": "Twitter",
        "other": "Unknown"
    }

    def __init__(self):
        pass

    def _resolve_short_url(self, url: str) -> str:
        """Resolves known short URLs to their full path."""
        try:
            # Add timeout to avoid hanging on dead links
            response = requests.head(url, allow_redirects=True, timeout=5)
            return response.url
        except requests.RequestException:
            return url

    def normalize_url(self, url: str) -> str:
        """
        Cleans up URLs (removes tracking parameters, shortens, standardizes).
        Handles shortened URLs (youtu.be, bit.ly, fb.watch, vm.tiktok.com, tiktok.com/t/).
        """
        # 1. Resolve shorteners
        short_domains = ['bit.ly', 'youtu.be', 'fb.watch', 'vm.tiktok.com', 'tiktok.com/t/']
        if any(d in url for d in short_domains):
            url = self._resolve_short_url(url)
            
        # 2. Parse and strip tracking params
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        
        # Parameters to keep based on platform
        keep_params = {}
        if 'youtube.com' in parsed.netloc:
            if 'v' in query:
                keep_params['v'] = query['v']
            if 'list' in query:
                keep_params['list'] = query['list']
        elif 'facebook.com' in parsed.netloc:
            if 'v' in query:
                keep_params['v'] = query['v']
            if 'story_fbid' in query:
                keep_params['story_fbid'] = query['story_fbid']
                keep_params['id'] = query.get('id', [])

        new_query = urlencode(keep_params, doseq=True)
        # Reconstruct canonical URL (forcing https and lowercase netloc)
        canonical_url = urlunparse((
            'https', 
            parsed.netloc.lower().replace('www.', ''), 
            parsed.path, 
            parsed.params, 
            new_query, 
            '' # Strip fragments
        ))
        return canonical_url

    def detect_platform(self, url: str) -> PlatformInfo:
        """
        Accepts any social media URL and returns a PlatformInfo object.
        """
        canonical_url = self.normalize_url(url)
        parsed = urlparse(canonical_url)
        netloc = parsed.netloc
        path = parsed.path
        query = parse_qs(parsed.query)

        platform_name = "other"
        content_type = "unknown"
        is_profile = False
        is_playlist = False
        extracted_id = None
        username = None

        # YouTube Detection
        if 'youtube.com' in netloc or 'youtu.be' in netloc:
            platform_name = "youtube"
            if 'list=' in canonical_url:
                is_playlist = True
                content_type = "playlist"
                extracted_id = query.get('list', [None])[0]
            elif '/watch' in path:
                content_type = "video"
                extracted_id = query.get('v', [None])[0]
            elif '/shorts/' in path:
                content_type = "short"
                extracted_id = path.split('/shorts/')[-1].split('/')[0]
            elif '/reel/' in path:
                content_type = "reel"
                extracted_id = path.split('/reel/')[-1].split('/')[0]
            elif '/@' in path:
                is_profile = True
                content_type = "profile"
                username = path.split('/@')[-1].split('/')[0]
            elif '/c/' in path or '/channel/' in path or '/user/' in path:
                is_profile = True
                content_type = "profile"
                username = path.split('/')[-1]

        # TikTok Detection
        elif 'tiktok.com' in netloc:
            platform_name = "tiktok"
            if '/video/' in path:
                content_type = "video"
                parts = path.split('/')
                try:
                    video_index = parts.index('video')
                    extracted_id = parts[video_index + 1]
                    username_part = parts[video_index - 1]
                    if username_part.startswith('@'):
                        username = username_part[1:]
                except (ValueError, IndexError):
                    pass
            elif '/@' in path:
                parts = path.split('/')
                for p in parts:
                    if p.startswith('@'):
                        username = p[1:]
                if not extracted_id:
                    is_profile = True
                    content_type = "profile"

        # Instagram Detection
        elif 'instagram.com' in netloc:
            platform_name = "instagram"
            if '/reel/' in path or '/reels/' in path:
                content_type = "reel"
                parts = path.strip('/').split('/')
                if len(parts) >= 2:
                    extracted_id = parts[1]
            elif '/p/' in path:
                content_type = "post"
                parts = path.strip('/').split('/')
                if len(parts) >= 2:
                    extracted_id = parts[1]
            elif '/tv/' in path:
                content_type = "video"
                parts = path.strip('/').split('/')
                if len(parts) >= 2:
                    extracted_id = parts[1]
            elif '/stories/' in path:
                content_type = "story"
                parts = path.strip('/').split('/')
                if len(parts) >= 3:
                    username = parts[1]
                    extracted_id = parts[2]
            else:
                parts = path.strip('/').split('/')
                if len(parts) == 1 and parts[0] not in ['explore', 'direct', 'reels']:
                    is_profile = True
                    content_type = "profile"
                    username = parts[0]

        # Facebook Detection
        elif 'facebook.com' in netloc or 'fb.watch' in netloc:
            platform_name = "facebook"
            if '/watch' in path or 'fb.watch' in netloc:
                content_type = "video"
                extracted_id = query.get('v', [None])[0] or path.strip('/').split('/')[-1]
            elif '/reel/' in path or '/reels/' in path:
                content_type = "reel"
                parts = path.strip('/').split('/')
                if len(parts) >= 2:
                    extracted_id = parts[-1]
            elif '/videos/' in path:
                content_type = "video"
                parts = path.strip('/').split('/')
                try:
                    vid_idx = parts.index('videos')
                    extracted_id = parts[vid_idx + 1]
                    username = parts[0]
                except (ValueError, IndexError):
                    pass
            else:
                parts = path.strip('/').split('/')
                if len(parts) == 1:
                    is_profile = True
                    content_type = "profile"
                    username = parts[0]

        # Twitter/X Detection
        elif 'twitter.com' in netloc or 'x.com' in netloc:
            platform_name = "twitter"
            if '/status/' in path:
                content_type = "post"
                parts = path.strip('/').split('/')
                try:
                    stat_idx = parts.index('status')
                    extracted_id = parts[stat_idx + 1]
                    username = parts[stat_idx - 1]
                except (ValueError, IndexError):
                    pass
            else:
                parts = path.strip('/').split('/')
                if len(parts) == 1 and parts[0] not in ['home', 'explore', 'notifications', 'messages']:
                    is_profile = True
                    content_type = "profile"
                    username = parts[0]

        return PlatformInfo(
            platform_name=platform_name,
            platform_display_name=self.PLATFORM_DISPLAY_NAMES.get(platform_name, "Unknown"),
            platform_color=self.PLATFORM_COLORS.get(platform_name, "#FFFFFF"),
            content_type=content_type,
            is_profile=is_profile,
            is_playlist=is_playlist,
            extracted_id=extracted_id,
            username=username
        )

    def validate_url(self, url: str) -> ValidationResult:
        """
        Checks if the URL is valid and belongs to a supported platform.
        """
        if not url or not url.startswith('http'):
            return ValidationResult(
                is_valid=False,
                error_message="Invalid URL format. Must start with http:// or https://"
            )
            
        try:
            platform_info = self.detect_platform(url)
            
            if platform_info.platform_name == "other":
                return ValidationResult(
                    is_valid=False,
                    platform_info=platform_info,
                    error_message="Unsupported platform. MediaVault currently supports YouTube, TikTok, Instagram, Facebook, and Twitter/X."
                )
                
            if platform_info.platform_name not in settings.ALLOWED_PLATFORMS:
                return ValidationResult(
                    is_valid=False,
                    platform_info=platform_info,
                    error_message=f"{platform_info.platform_display_name} is currently disabled in system settings."
                )
                
            return ValidationResult(
                is_valid=True,
                platform_info=platform_info
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Error validating URL: {str(e)}"
            )
