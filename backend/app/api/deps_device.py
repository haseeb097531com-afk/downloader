"""Device authentication and authorization dependencies for FastAPI.

Provides:
- get_current_device: Device token -> Device
- require_permission(*permissions): permission-based access control dependency factory
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_async_redis
from app.db.database import get_db
from app.models.device import Device

logger = logging.getLogger(__name__)


async def get_current_device(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Device:
    """Resolve the current paired device from the X-Device-Token header."""
    token = request.headers.get("X-Device-Token", "")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device token",
        )

    token_hash = Device.hash_token(token)
    result = await db.execute(
        select(Device).where(Device.token_hash == token_hash, Device.is_active == True)
    )
    device = result.scalars().first()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked device token",
        )

    device.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(device)

    return device


def require_permission(*permissions: str) -> Callable:
    """Return a dependency that enforces the required permissions on the device."""
    required = set(permissions)

    async def _check(device: Device = Depends(get_current_device)) -> Device:
        device_perms = set(device.permissions or [])
        if not required.issubset(device_perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device does not have required permissions",
            )
        return device

    return _check
