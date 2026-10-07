import pytest
from app.services.extractor.platform_detector import PlatformDetector

@pytest.fixture
def detector():
    return PlatformDetector()

def test_youtube_detection(detector):
    """Test standard YouTube watch URLs."""
    info = detector.detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert info.platform_name == "youtube"
    assert info.content_type == "video"
    assert info.extracted_id == "dQw4w9WgXcQ"

def test_tiktok_detection(detector):
    """Test standard TikTok video URLs."""
    info = detector.detect_platform("https://www.tiktok.com/@user/video/1234567890")
    assert info.platform_name == "tiktok"
    assert info.content_type == "video"
    assert info.username == "user"
    assert info.extracted_id == "1234567890"

def test_instagram_reel(detector):
    """Test Instagram Reels URLs."""
    info = detector.detect_platform("https://www.instagram.com/reel/abcdefg/")
    assert info.platform_name == "instagram"
    assert info.content_type == "reel"

def test_facebook_video(detector):
    """Test Facebook video URLs."""
    info = detector.detect_platform("https://www.facebook.com/watch/?v=12345")
    assert info.platform_name == "facebook"
    assert info.content_type == "video"

def test_twitter_post(detector):
    """Test Twitter/X status URLs."""
    info = detector.detect_platform("https://twitter.com/user/status/123456")
    assert info.platform_name == "twitter"
    assert info.content_type == "post"
    assert info.extracted_id == "123456"

def test_invalid_url(detector):
    """Test fallback logic for invalid or malformed URLs."""
    res = detector.validate_url("not_a_url")
    assert res.is_valid == False

def test_url_normalization(detector):
    """Test URL normalization (stripping tracking params)."""
    norm = detector.normalize_url("https://www.youtube.com/watch?v=123&feature=share")
    assert "feature=" not in norm
    assert "v=123" in norm
