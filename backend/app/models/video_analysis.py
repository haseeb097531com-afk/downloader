"""Video analysis record for AI transcription, summarization and translation."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, Enum as SQLEnum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

from app.models.base import BaseModel
from app.models.user import User


class AnalysisStatus(str, enum.Enum):
    """Lifecycle status for a video analysis job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoAnalysis(BaseModel):
    """Store AI-generated transcript, summary and subtitles for a download."""

    __tablename__ = "video_analysis"

    download_id = Column(String(36), nullable=False, unique=True, index=True)
    language = Column(String(20), nullable=True)
    transcript_text = Column(Text, nullable=True)
    srt_path = Column(String(1024), nullable=True)
    summary_text = Column(Text, nullable=True)
    keywords = Column(JSONB, nullable=True)
    translated = Column(JSONB, nullable=False, default=dict)
    status = Column(SQLEnum(AnalysisStatus), nullable=False, default=AnalysisStatus.PENDING, index=True)
    error = Column(String(2000), nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    owner = relationship("User", back_populates="video_analyses")
    tenant = relationship("Tenant")
