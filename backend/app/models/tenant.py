"""Multi-tenant models for MediaVault backend.

Provides:
- TenantPlan: subscription plan tiers
- TenantStatus: account lifecycle states
- Tenant: top-level tenant/organization record
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Enum, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.user import User


class TenantPlan(str, enum.Enum):
    """Subscription plan tiers for a tenant."""

    TRIAL = "trial"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class TenantStatus(str, enum.Enum):
    """Lifecycle states for a tenant account."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Tenant(BaseModel):
    """Top-level tenant/organization record for multi-tenant scoping."""

    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    plan = Column(Enum(TenantPlan), nullable=False, default=TenantPlan.TRIAL)
    status = Column(Enum(TenantStatus), nullable=False, default=TenantStatus.ACTIVE)
    owner_user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    settings_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    suspended_at = Column(DateTime, nullable=True)
    plan_started_at = Column(DateTime, nullable=True)
    plan_expires_at = Column(DateTime, nullable=True)
    auto_renew = Column(Boolean, nullable=False, default=False)
    trial_used = Column(Boolean, nullable=False, default=False)
    quota_override_until = Column(DateTime, nullable=True)

    # Relationships
    owner_user = relationship("User", foreign_keys=[owner_user_id])


__all__ = ["Tenant", "TenantPlan", "TenantStatus"]
