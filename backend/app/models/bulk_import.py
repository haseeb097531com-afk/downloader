import enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.user import User


class BulkJobType(str, enum.Enum):
    LINKS = "links"
    PROFILES = "profiles"


class BulkJobStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"


class BulkItemStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


class BulkJob(BaseModel):
    __tablename__ = "bulk_jobs"

    job_type = Column(Enum(BulkJobType), nullable=False)
    total_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)
    failed_items = Column(Integer, nullable=False, default=0)
    status = Column(Enum(BulkJobStatus), nullable=False, default=BulkJobStatus.RUNNING)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    items = relationship("BulkItem", back_populates="job", cascade="all, delete-orphan")
    owner = relationship("User", back_populates="bulk_jobs")
    tenant = relationship("Tenant")


class BulkItem(BaseModel):
    __tablename__ = "bulk_items"

    job_id = Column(String(36), ForeignKey("bulk_jobs.id"), nullable=False, index=True)
    url = Column(String(1024), nullable=False)
    platform = Column(String(50), nullable=True)
    username = Column(String(255), nullable=True)
    status = Column(Enum(BulkItemStatus), nullable=False, default=BulkItemStatus.PENDING)
    download_id = Column(String(36), ForeignKey("downloads.id"), nullable=True)
    error = Column(String(500), nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    job = relationship("BulkJob", back_populates="items")
    owner = relationship("User")
    tenant = relationship("Tenant")
