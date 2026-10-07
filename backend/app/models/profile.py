import enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.user import User

class ProfileVideoStatus(str, enum.Enum):
    NEW = "new"
    QUEUED = "queued"
    DOWNLOADED = "downloaded"
    SKIPPED = "skipped"
    FAILED = "failed"

class Profile(BaseModel):
    __tablename__ = "profiles"

    platform = Column(String(50), index=True, nullable=False)
    username = Column(String(255), index=True, nullable=False)
    profile_url = Column(String(1024), unique=True, nullable=False)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(1024), nullable=True)
    total_videos = Column(Integer, default=0)
    last_scraped_at = Column(DateTime, nullable=True)
    auto_download = Column(Boolean, default=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    videos = relationship("ProfileVideo", back_populates="profile", cascade="all, delete-orphan")
    owner = relationship("User", back_populates="profiles")
    tenant = relationship("Tenant")

class ProfileVideo(BaseModel):
    __tablename__ = "profile_videos"

    profile_id = Column(String(36), ForeignKey("profiles.id"), index=True, nullable=False)
    video_url = Column(String(1024), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=True)
    thumbnail_url = Column(String(1024), nullable=True)
    upload_date = Column(String(50), nullable=True)
    status = Column(Enum(ProfileVideoStatus), default=ProfileVideoStatus.NEW, nullable=False)
    download_id = Column(String(36), ForeignKey("downloads.id"), nullable=True)
    discovered_at = Column(DateTime, nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    profile = relationship("Profile", back_populates="videos")
    download = relationship("Download")
    owner = relationship("User")
    tenant = relationship("Tenant")
