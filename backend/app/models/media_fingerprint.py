"""Media fingerprint model for perceptual hash deduplication."""

from sqlalchemy import Column, String, JSON, Index, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.download import Download
from app.models.user import User


class MediaFingerprint(BaseModel):
    """
    SQLAlchemy model storing the perceptual hash of a completed download.

    Used by :class:`~app.services.ai.dedup.DedupEngine` to detect near-duplicate
    media across the library without byte-for-byte comparison.
    """

    __tablename__ = "media_fingerprints"

    download_id = Column(
        String(36),
        ForeignKey("downloads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    phash = Column(String(16), nullable=False, index=True)
    keyframe_paths = Column(JSON, nullable=False, default=list)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    download = relationship("Download", backref="media_fingerprint", uselist=False)
    owner = relationship("User", back_populates="media_fingerprints")
    tenant = relationship("Tenant")


__all__ = ["MediaFingerprint"]
