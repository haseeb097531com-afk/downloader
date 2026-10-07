import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.plugins.manager import PluginManager, plugin_manager
from app.services.plugins.marketplace import (
    InvalidManifestError,
    PluginInstallError,
    _validate_manifest,
    list_installed_plugins,
    uninstall_plugin,
)


class TestPluginManager:
    def test_core_plugins_load(self):
        manager = PluginManager()
        plugins = manager.list_all_plugins()
        names = [p["name"] for p in plugins]
        assert "youtube" in names

    def test_reload_preserves_core(self):
        manager = PluginManager()
        before = len(manager.list_all_plugins())
        manager.reload()
        after = len(manager.list_all_plugins())
        assert before == after

    def test_get_plugin_for_url(self):
        plugin = plugin_manager.get_plugin_for_url("https://youtube.com/watch?v=123")
        assert plugin is not None
        assert plugin.platform_name == "youtube"


class TestMarketplaceValidation:
    def test_valid_manifest_passes(self):
        manifest = {"name": "test", "version": "1.0.0", "entry_point": "main.py"}
        _validate_manifest(manifest)

    def test_missing_keys_raises(self):
        with pytest.raises(InvalidManifestError):
            _validate_manifest({"name": "test"})


class TestMarketplaceList:
    def test_list_returns_empty_when_no_user_plugins(self, monkeypatch, tmp_path):
        monkeypatch.setattr("app.services.plugins.marketplace._user_plugins_dir", lambda: tmp_path)
        assert list_installed_plugins() == []

    def test_list_discovers_user_plugins(self, monkeypatch, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        plugin_dir = plugins_dir / "my_plugin"
        plugin_dir.mkdir()
        manifest = {"name": "my_plugin", "version": "1.0.0", "entry_point": "main.py"}
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest))
        monkeypatch.setattr("app.services.plugins.marketplace._user_plugins_dir", lambda: plugins_dir)
        results = list_installed_plugins()
        assert len(results) == 1
        assert results[0]["name"] == "my_plugin"


class TestMarketplaceUninstall:
    def test_uninstall_removes_plugin(self, monkeypatch, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        plugin_dir = plugins_dir / "to_remove"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text(json.dumps({"name": "to_remove"}))
        monkeypatch.setattr("app.services.plugins.marketplace._user_plugins_dir", lambda: plugins_dir)
        uninstall_plugin("to_remove")
        assert not plugin_dir.exists()

    def test_uninstall_missing_raises(self, monkeypatch, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        monkeypatch.setattr("app.services.plugins.marketplace._user_plugins_dir", lambda: plugins_dir)
        with pytest.raises(PluginInstallError):
            uninstall_plugin("nonexistent")


class TestPluginEndpoints:
    @pytest.mark.asyncio
    async def test_list_plugins_endpoint(self, async_client, monkeypatch):
        monkeypatch.setattr(
            "app.api.v1.endpoints.plugins.list_installed_plugins",
            lambda: [],
        )
        response = await async_client.get("/api/v1/plugins")
        assert response.status_code == 200
        assert "core" in response.json()

    @pytest.mark.asyncio
    async def test_reload_endpoint(self, async_client):
        response = await async_client.post("/api/v1/plugins/reload")
        assert response.status_code == 200
        assert response.json()["status"] == "reloaded"

    @pytest.mark.asyncio
    async def test_uninstall_endpoint_not_found(self, async_client, monkeypatch):
        monkeypatch.setattr(
            "app.api.v1.endpoints.plugins.uninstall_plugin",
            lambda name: (_ for _ in ()).throw(PluginInstallError("not installed")),
        )
        response = await async_client.post("/api/v1/plugins/uninstall/nonexistent")
        assert response.status_code == 404
