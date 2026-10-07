"""Push subscription model for web push notifications."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class PushSubscription(BaseModel):
    """Web push subscription for a user."""

    __tablename__ = "push_subscriptions"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    endpoint = Column(String(2048), nullable=False, unique=True, index=True)
    p256dh = Column(String(256), nullable=False)
    auth = Column(String(128), nullable=False)
    user_agent = Column(String(1024), nullable=True)
    last_sent_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, nullable=False, default=0)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    owner = relationship("User", back_populates="push_subscriptions")
    tenant = relationship("Tenant")
