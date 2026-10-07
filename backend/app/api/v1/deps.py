"""Shared FastAPI dependencies for the v1 API.

Several routers need the same collaborator. Declaring the provider once here means
tests override a single dependency instead of hunting for one copy per router.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user
from app.db.database import get_db
from app.services.downloader.download_orchestrator import DownloadOrchestrator


def get_orchestrator(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> DownloadOrchestrator:
    """Build a :class:`DownloadOrchestrator` for the request."""
    return DownloadOrchestrator(db, current_user=current_user)