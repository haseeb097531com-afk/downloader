"""Pending link detected from clipboard for later download."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base

from app.models.base import BaseModel
from app.models.user import User


class PendingLinkStatus(str, enum.Enum):
    """Lifecycle status for a pending clipboard link."""

    PENDING = "pending"
    DISMISSED = "dismissed"
    DOWNLOADED = "downloaded"


class PendingLink(BaseModel):
    """Record a social media URL detected from the system clipboard."""

    __tablename__ = "pending_links"

    url = Column(String(2048), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)
    status = Column(SQLEnum(PendingLinkStatus), nullable=False, default=PendingLinkStatus.PENDING, index=True)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    owner = relationship("User", back_populates="pending_links")
    tenant = relationship("Tenant")
