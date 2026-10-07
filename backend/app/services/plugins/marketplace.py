"""Marketplace service for installing and managing user plugins from git repositories."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import git
from git.exc import GitCommandError, InvalidGitRepositoryError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Required manifest keys
_REQUIRED_MANIFEST_KEYS = {"name", "version", "entry_point"}


class MarketplaceError(Exception):
    """Base exception for marketplace operations."""


class InvalidManifestError(MarketplaceError):
    """Raised when a plugin manifest is missing required fields."""


class PluginInstallError(MarketplaceError):
    """Raised when a plugin cannot be installed."""


def _user_plugins_dir() -> Path:
    """Return the resolved user plugins directory, creating it if needed."""
    path = Path(settings.USER_PLUGINS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_manifest(manifest: Dict[str, Any]) -> None:
    """Ensure manifest contains all required keys."""
    missing = _REQUIRED_MANIFEST_KEYS - set(manifest.keys())
    if missing:
        raise InvalidManifestError(f"manifest.json missing required keys: {missing}")


def _read_manifest(plugin_dir: Path) -> Dict[str, Any]:
    """Load and validate manifest.json from a plugin directory."""
    manifest_path = plugin_dir / "manifest.json"
    if not manifest_path.is_file():
        raise InvalidManifestError("manifest.json not found in plugin root")
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        raise InvalidManifestError(f"Failed to read manifest.json: {exc}") from exc
    _validate_manifest(manifest)
    return manifest


def _install_pip_dependencies(dependencies: List[str], target_dir: Path) -> None:
    """Install pip dependencies into the current environment."""
    if not dependencies:
        return
    logger.info("Installing pip dependencies for plugin: %s", dependencies)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *dependencies],
            cwd=str(target_dir),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Failed to install plugin dependencies %s: %s\n%s",
            dependencies,
            exc.stdout,
            exc.stderr,
        )
        raise PluginInstallError(
            f"pip install failed for dependencies: {dependencies}"
        ) from exc


def list_installed_plugins() -> List[Dict[str, Any]]:
    """Scan USER_PLUGINS_DIR and return manifest data for each installed plugin."""
    plugins: List[Dict[str, Any]] = []
    plugins_dir = _user_plugins_dir()
    if not plugins_dir.exists():
        return plugins
    for entry in plugins_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            manifest = _read_manifest(entry)
            manifest["path"] = str(entry)
            plugins.append(manifest)
        except InvalidManifestError as exc:
            logger.warning("Skipping invalid plugin at %s: %s", entry, exc)
    return plugins


def install_from_git(repo_url: str) -> Dict[str, Any]:
    """Clone a plugin repo, validate its manifest, and install it.

    Args:
        repo_url: Git repository URL to clone.

    Returns:
        The parsed manifest dict.

    Raises:
        PluginInstallError: If cloning, validation, or dependency install fails.
    """
    import tempfile
    import shutil

    temp_dir: Optional[Path] = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="mv_plugin_install_"))
        logger.info("Cloning plugin repo %s into %s", repo_url, temp_dir)
        try:
            git.Repo.clone_from(repo_url, str(temp_dir), depth=1)
        except (GitCommandError, InvalidGitRepositoryError) as exc:
            raise PluginInstallError(f"Failed to clone repo: {exc}") from exc

        manifest = _read_manifest(temp_dir)
        plugin_name = manifest["name"]

        # Security: prevent overwriting core files or escaping the plugins dir.
        safe_name = "".join(c for c in plugin_name if c.isalnum() or c in "-_")
        if not safe_name or safe_name in (".", ".."):
            raise PluginInstallError(f"Invalid plugin name: {plugin_name!r}")

        target = _user_plugins_dir() / safe_name
        if target.exists():
            shutil.rmtree(str(target))

        shutil.move(str(temp_dir), str(target))
        temp_dir = None  # moved, don't cleanup

        deps = manifest.get("dependencies", [])
        if isinstance(deps, list):
            _install_pip_dependencies(deps, target)

        logger.info("Plugin %s installed successfully to %s", plugin_name, target)
        return manifest
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(str(temp_dir), ignore_errors=True)


def uninstall_plugin(plugin_name: str) -> None:
    """Remove an installed plugin by name.

    Args:
        plugin_name: Name declared in the plugin's manifest.json.

    Raises:
        PluginInstallError: If the plugin directory cannot be removed.
    """
    import shutil

    plugins_dir = _user_plugins_dir()
    target = plugins_dir / plugin_name
    if not target.exists():
        raise PluginInstallError(f"Plugin {plugin_name!r} is not installed")
    try:
        shutil.rmtree(str(target))
        logger.info("Plugin %s uninstalled", plugin_name)
    except OSError as exc:
        raise PluginInstallError(f"Failed to remove plugin {plugin_name!r}: {exc}") from exc
