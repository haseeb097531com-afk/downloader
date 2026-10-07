"""Remote control device model for Phase 19.

Pairs a phone PWA with the desktop app using a restricted device token.
"""

from __future__ import annotations

import enum
import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.user import User


class DevicePermission(str, enum.Enum):
    """Granular permissions that can be granted to a remote device."""

    VIEW = "view"
    CONTROL = "control"
    SCRAPE = "scrape"


class Device(BaseModel):
    """A paired remote device (phone PWA, tablet, etc)."""

    __tablename__ = "devices"

    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String(120), nullable=False)
    platform_hint = Column(String(50), nullable=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    permissions = Column(JSON, nullable=False, default=lambda: ["view"])
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_seen_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    owner = relationship("User", back_populates="devices")
    tenant = relationship("Tenant")

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Return the SHA-256 hex digest of ``raw_token``."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_token() -> str:
        """Return a new cryptographically secure device token."""
        return secrets.token_urlsafe(32)


User.devices = relationship("Device", back_populates="owner")
