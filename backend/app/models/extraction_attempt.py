"""Extraction attempt audit log."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

from app.models.base import BaseModel


class ProviderName(str, enum.Enum):
    DIRECT = "direct"
    SCRAPERAPI = "scraperapi"
    ZENROWS = "zenrows"
    RAPIDAPI = "rapidapi"


class ExtractionAttempt(BaseModel):
    """Record a single extraction attempt for auditing and debugging."""

    __tablename__ = "extraction_attempts"

    url = Column(String(2048), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    tenant = relationship("Tenant")
