import pytest
from app.plugins.manager import PluginManager

@pytest.fixture
def manager():
    return PluginManager()

def test_plugin_discovery(manager):
    """Test that all specified plugins dynamically load at runtime."""
    plugins = manager.list_all_plugins()
    names = [p['name'] for p in plugins]
    assert "youtube" in names
    assert "tiktok" in names
    assert "instagram" in names
    assert "facebook" in names
    assert "twitter" in names

def test_plugin_selection(manager):
    """Test correct routing of URLs to their respective Plugin instances."""
    yt_plugin = manager.get_plugin_for_url("https://youtube.com/watch?v=123")
    assert yt_plugin is not None
    assert yt_plugin.platform_name == "youtube"
    
    tk_plugin = manager.get_plugin_for_url("https://tiktok.com/@user/video/123")
    assert tk_plugin is not None
    assert tk_plugin.platform_name == "tiktok"
