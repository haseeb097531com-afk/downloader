"""Audit log model for security and compliance tracking."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base

from app.models.base import BaseModel
from app.models.user import User


class AuditAction(str, enum.Enum):
    """Types of actions tracked in the audit log."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    LOCKOUT = "lockout"
    PERMISSION_DENIED = "permission_denied"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    PASSWORD_CHANGE = "password_change"
    SETTINGS_CHANGE = "settings_change"
    DOWNLOAD_DELETE = "download_delete"
    DOWNLOAD_PURGE = "download_purge"
    EXPORT_CSV = "export_csv"
    EXPORT_PDF = "export_pdf"


class AuditLog(BaseModel):
    """Immutable record of security-relevant actions."""

    __tablename__ = "audit_logs"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(Enum(AuditAction), nullable=False, index=True)
    resource = Column(String(255), nullable=True)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(1024), nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    meta = Column(Text, nullable=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    actor = relationship("User", back_populates="audit_logs")
    tenant = relationship("Tenant")


__all__ = ["AuditLog", "AuditAction"]
