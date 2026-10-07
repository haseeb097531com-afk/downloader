"""Plugin manager with dynamic user plugin loading and hot-reload support."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import List, Optional

from app.core.config import settings
from app.plugins.base import PlatformPlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """Auto-discovers and manages core and user-installed plugins."""

    def __init__(self) -> None:
        self._plugins: List[PlatformPlugin] = []
        self._user_plugin_modules: List[ModuleType] = []
        self.load_plugins()

    def _load_core_plugins(self) -> None:
        """Discover built-in plugins under app.plugins."""
        import app.plugins as plugins
        import pkgutil

        for _, module_name, _ in pkgutil.iter_modules(plugins.__path__):
            if module_name in ("base", "manager"):
                continue
            try:
                module = importlib.import_module(f"app.plugins.{module_name}")
            except Exception as exc:
                logger.warning("Failed to load core plugin %s: %s", module_name, exc)
                continue
            self._register_plugin_classes(module)

    def _load_user_plugins(self) -> None:
        """Discover and dynamically import plugins from USER_PLUGINS_DIR."""
        plugins_dir = Path(settings.USER_PLUGINS_DIR)
        if not plugins_dir.exists() or not plugins_dir.is_dir():
            logger.debug("User plugins dir does not exist: %s", plugins_dir)
            return

        for plugin_dir in plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            manifest_path = plugin_dir / "manifest.json"
            if not manifest_path.is_file():
                logger.debug("Skipping %s: no manifest.json", plugin_dir)
                continue

            try:
                with manifest_path.open("r", encoding="utf-8") as handle:
                    manifest = _load_manifest_from_handle(handle)
            except Exception as exc:
                logger.warning("Skipping invalid plugin at %s: %s", plugin_dir, exc)
                continue

            entry_point = manifest.get("entry_point", "main.py")
            module_path = plugin_dir / entry_point
            if not module_path.is_file():
                logger.warning("Plugin %s missing entry point: %s", plugin_dir, entry_point)
                continue

            module_name = f"user_plugin_{manifest.get('name', plugin_dir.name)}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, str(module_path))
                if spec is None or spec.loader is None:
                    logger.warning("Could not create spec for plugin %s", plugin_dir)
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                self._user_plugin_modules.append(module)
                self._register_plugin_classes(module)
                logger.info("Loaded user plugin: %s", manifest.get("name"))
            except Exception as exc:
                logger.warning("Failed to load user plugin %s: %s", plugin_dir, exc)

    def _register_plugin_classes(self, module) -> None:
        """Find and register PlatformPlugin subclasses from a module."""
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if (
                isinstance(attribute, type)
                and issubclass(attribute, PlatformPlugin)
                and attribute is not PlatformPlugin
            ):
                self.register_plugin(attribute())

    def register_plugin(self, plugin: PlatformPlugin) -> None:
        self._plugins.append(plugin)

    def deregister_plugin(self, platform_name: str) -> None:
        self._plugins = [p for p in self._plugins if p.platform_name != platform_name]

    def load_plugins(self) -> None:
        """Clear and reload all plugins (core + user)."""
        self._plugins.clear()
        self._user_plugin_modules.clear()
        self._load_core_plugins()
        self._load_user_plugins()

    def reload(self) -> None:
        """Hot-reload all plugins."""
        self.load_plugins()
        logger.info("Plugins reloaded. Total plugins: %d", len(self._plugins))

    def list_all_plugins(self) -> List[dict]:
        return [
            {
                "name": p.platform_name,
                "color": p.get_platform_color(),
                "patterns": p.supported_patterns,
            }
            for p in self._plugins
        ]

    def get_plugin_for_url(self, url: str) -> Optional[PlatformPlugin]:
        """Iterates over loaded plugins and returns the first one that validates the URL."""
        for plugin in self._plugins:
            if plugin.validate_url(url):
                return plugin
        return None


def _load_manifest(handle) -> dict:
    """Parse and validate a manifest.json file handle."""
    import json
    manifest = json.load(handle)
    required = {"name", "version", "entry_point"}
    missing = required - set(manifest.keys())
    if missing:
        raise ValueError(f"manifest.json missing required keys: {missing}")
    return manifest


def _load_manifest_from_handle(handle) -> dict:
    """Parse and validate a manifest.json file handle."""
    import json
    manifest = json.load(handle)
    required = {"name", "version", "entry_point"}
    missing = required - set(manifest.keys())
    if missing:
        raise ValueError(f"manifest.json missing required keys: {missing}")
    return manifest


plugin_manager = PluginManager()
