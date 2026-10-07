"""Device pairing flow for remote control.

Uses a short-lived Redis code to bootstrap trust between the desktop and a
phone PWA without exposing credentials over the network.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core import redis_client
from app.db.database import AsyncSessionLocal
from app.models.device import Device, DevicePermission
from app.models.user import User

logger = logging.getLogger(__name__)

PAIR_PREFIX = "mediavault:pair"


def _pair_key(code: str) -> str:
    return f"{PAIR_PREFIX}:{code}"


async def _local_admin(db: AsyncSession) -> User:
    """Return the seeded local admin user, creating it when missing."""
    result = await db.execute(select(User).where(User.username == "local"))
    user = result.scalars().first()
    if user is None:
        user = User(
            id="00000000-0000-0000-0000-000000000001",
            username="local",
            email=None,
            password_hash="",
            role="owner",
            is_active=True,
            must_change_password=False,
            failed_login_count=0,
            locked_until=None,
            token_version=0,
        )
        db.add(user)
        await db.flush()
    return user


def create_pairing_intent(owner_id: str, name: str, permissions: list[str]) -> dict:
    """Create a single-use pairing intent in Redis.

    Args:
        owner_id: User ID that will own the device after pairing.
        name: Human-readable device name supplied by the phone.
        permissions: List of permission strings to grant.

    Returns:
        Dict with ``code`` and ``qrPayload`` for the phone to consume.
    """
    code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
    ttl = int(getattr(settings, "pairing_ttl_seconds", 120))
    payload = {
        "owner_id": owner_id,
        "name": name,
        "permissions": permissions,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    client = redis_client.get_redis()
    client.set(_pair_key(code), json.dumps(payload), ex=ttl)
    base = getattr(settings, "PUBLIC_BASE_URL", "") or ""
    qr_payload = {
        "v": 1,
        "base": base,
        "code": code,
    }
    return {"code": code, "qrPayload": qr_payload}


async def consume_pairing_code(code: str, device_name: Optional[str] = None) -> dict:
    """Atomically consume a pairing code and create a device.

    Uses Redis GETDEL to ensure the code can only be consumed once.

    Args:
        code: The short-lived pairing code from the phone.
        device_name: Optional override for the device name.

    Returns:
        Dict with ``deviceId``, ``token`` (raw, returned once), ``permissions``,
        and ``name``.

    Raises:
        HTTPException 404: When the code is missing or expired.
    """
    from fastapi import HTTPException, status

    client = redis_client.get_redis()
    raw = client.getdel(_pair_key(code))
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pairing code not found or expired")

    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pairing payload") from exc

    async with AsyncSessionLocal() as db:
        owner_id = payload.get("owner_id")
        if not owner_id:
            admin = _local_admin(db)
            owner_id = admin.id

        raw_token = Device.generate_token()
        token_hash = Device.hash_token(raw_token)

        device = Device(
            owner_id=owner_id,
            name=device_name or payload.get("name") or "Remote Device",
            platform_hint=None,
            token_hash=token_hash,
            permissions=payload.get("permissions") or ["view"],
            is_active=True,
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)

        return {
            "deviceId": str(device.id),
            "token": raw_token,
            "permissions": device.permissions,
            "name": device.name,
        }
