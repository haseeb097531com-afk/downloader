import enum
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.user import User

class DownloadStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class Download(BaseModel):
    """
    SQLAlchemy model representing a download entity in the system.
    """
    __tablename__ = "downloads"

    url = Column(String(1024), index=True, nullable=False)
    platform = Column(String(50), nullable=False)
    content_type = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    thumbnail_url = Column(String(1024), nullable=True)
    status = Column(Enum(DownloadStatus), default=DownloadStatus.PENDING, nullable=False)
    progress = Column(Float, default=0.0)
    file_path = Column(String(1024), nullable=True)
    file_size = Column(Integer, nullable=True)
    quality = Column(String(50), nullable=True)
    error_message = Column(String(2000), nullable=True)
    retry_count = Column(Integer, default=0)
    is_watermark_free = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    celery_task_id = Column(String(50), index=True, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    thumbnail_local = Column(String(1024), nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    processing_error = Column(String(2000), nullable=True)
    category = Column(String(100), nullable=True, index=True)
    trim_start = Column(String(20), nullable=True)
    trim_end = Column(String(20), nullable=True)
    cloud_backed_up = Column(Boolean, default=False, nullable=False)
    cloud_url = Column(String(1024), nullable=True)
    quarantined = Column(Boolean, default=False, nullable=False)
    quarantine_reason = Column(String(500), nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    pushed = Column(Boolean, nullable=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    owner = relationship("User", back_populates="downloads")
    tenant = relationship("Tenant")
