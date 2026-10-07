"""User and authentication models for Phase 17A."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, Enum, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """RBAC roles for authenticated users."""

    OWNER = "owner"
    SUB_ADMIN = "sub_admin"
    USER = "user"


class TenantRole(str, enum.Enum):
    """Roles within a multi-tenant context."""

    SUPER_ADMIN = "super_admin"
    TENANT_OWNER = "tenant_owner"
    MEMBER = "member"


class User(BaseModel):
    """Application user for authentication and authorization."""

    __tablename__ = "users"

    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    failed_login_count = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    token_version = Column(Integer, nullable=False, default=0)
    parent_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_role = Column(Enum(TenantRole), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    # Relationships
    parent = relationship("User", remote_side="User.id", back_populates="children")
    children = relationship("User", back_populates="parent")
    downloads = relationship("Download", back_populates="owner")
    profiles = relationship("Profile", back_populates="owner")
    bulk_jobs = relationship("BulkJob", back_populates="owner")
    video_analyses = relationship("VideoAnalysis", back_populates="owner")
    media_fingerprints = relationship("MediaFingerprint", back_populates="owner")
    pending_links = relationship("PendingLink", back_populates="owner")
    queue_items = relationship("QueueItem", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="actor")
    devices = relationship("Device", back_populates="owner")
    push_subscriptions = relationship("PushSubscription", back_populates="owner")

    @property
    def is_super_admin(self) -> bool:
        """Return True when this user is a platform-level super_admin."""
        return self.tenant_role == TenantRole.SUPER_ADMIN


__all__ = ["User", "UserRole", "TenantRole"]
