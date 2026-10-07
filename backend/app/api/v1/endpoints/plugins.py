"""Plugin endpoints: list, install, uninstall, reload."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps_auth import require_feature
from app.core.celery_app import celery_app
from app.plugins.manager import plugin_manager
from app.services.plugins.marketplace import (
    InvalidManifestError,
    PluginInstallError,
    install_from_git,
    list_installed_plugins,
    uninstall_plugin,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Plugins"], dependencies=[Depends(require_feature("plugins"))])


@router.get("/plugins")
async def list_plugins() -> Dict[str, List[Dict[str, Any]]]:
    """Return both core and user-installed plugins."""
    core = plugin_manager.list_all_plugins()
    user = list_installed_plugins()
    return {
        "core": core,
        "user": user,
    }


@router.post("/plugins/install", status_code=202)
async def install_plugin(payload: Dict[str, str], background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Install a plugin from a git repository in the background.

    Request body:
        repo_url: Git repository URL to clone.

    Returns:
        202 Accepted with an acknowledgement.
    """
    repo_url = payload.get("repo_url")
    if not repo_url:
        raise HTTPException(status_code=422, detail="repo_url is required")

    background_tasks.add_task(_background_install, repo_url)
    logger.info("Plugin install queued for %s", repo_url)
    return {"status": "accepted", "repo_url": repo_url}


@router.post("/plugins/uninstall/{name}")
async def uninstall_plugin_endpoint(name: str) -> Dict[str, str]:
    """Uninstall a user plugin by name."""
    try:
        uninstall_plugin(name)
    except PluginInstallError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    plugin_manager.reload()
    return {"status": "uninstalled", "name": name}


@router.post("/plugins/reload")
async def reload_plugins() -> Dict[str, Any]:
    """Hot-reload all plugins (core + user)."""
    plugin_manager.reload()
    return {
        "status": "reloaded",
        "total_plugins": len(plugin_manager.list_all_plugins()),
    }


def _background_install(repo_url: str) -> None:
    """Background task: install plugin from git and reload manager."""
    try:
        manifest = install_from_git(repo_url)
        plugin_manager.reload()
        logger.info("Background install complete for plugin %s", manifest.get("name"))
    except (PluginInstallError, InvalidManifestError) as exc:
        logger.error("Background plugin install failed for %s: %s", repo_url, exc)
