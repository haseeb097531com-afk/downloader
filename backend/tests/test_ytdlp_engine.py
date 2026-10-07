import pytest
from unittest.mock import patch, MagicMock
from app.services.extractor.ytdlp_engine import YTDLPEngine, YTDLPEngineError

@pytest.fixture
def engine():
    return YTDLPEngine()

@patch('app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL')
def test_extract_info(mock_ydl, engine):
    """Test standard metadata extraction flow via mocked yt-dlp response."""
    mock_instance = MagicMock()
    mock_ydl.return_value.__enter__.return_value = mock_instance
    mock_instance.extract_info.return_value = {
        'id': '123',
        'title': 'Test Video',
        'duration': 60,
        'formats': []
    }
    
    result = engine.extract_info("http://test.com/video")
    assert result['title'] == 'Test Video'
    assert result['id'] == '123'
    assert result['duration'] == 60

@patch('app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL')
def test_format_selection(mock_ydl, engine):
    """Test dynamic format resolution (audio_only, 1080p, etc.)."""
    mock_instance = MagicMock()
    mock_ydl.return_value.__enter__.return_value = mock_instance
    mock_instance.extract_info.return_value = {
        'id': '123',
        'title': 'Test',
        'formats': [
            {'format_id': '1', 'ext': 'mp4', 'url': 'http://vid1', 'vcodec': 'avc', 'acodec': 'mp4a', 'height': 720, 'filesize': 100},
            {'format_id': '2', 'ext': 'mp4', 'url': 'http://vid2', 'vcodec': 'avc', 'acodec': 'mp4a', 'height': 1080, 'filesize': 200},
            {'format_id': '3', 'ext': 'm4a', 'url': 'http://aud1', 'vcodec': 'none', 'acodec': 'mp4a', 'filesize': 50},
        ]
    }
    
    best = engine.get_best_format("http://test.com/video", "best")
    assert best['quality'] == "1080p"
    
    audio = engine.get_best_format("http://test.com/video", "audio_only")
    assert audio['quality'] == "audio_only"

@patch('app.services.extractor.ytdlp_engine.yt_dlp.YoutubeDL')
def test_error_handling(mock_ydl, engine):
    """Test explicit domain exception raising (e.g., Age Restriction)."""
    from yt_dlp.utils import DownloadError
    mock_instance = MagicMock()
    mock_ydl.return_value.__enter__.return_value = mock_instance
    mock_instance.extract_info.side_effect = DownloadError("Sign in to confirm your age")
    
    with pytest.raises(YTDLPEngineError) as exc:
        engine.extract_info("http://test.com/video")
    assert exc.value.code == "AGE_RESTRICTED"
