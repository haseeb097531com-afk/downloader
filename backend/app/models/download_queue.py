from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.user import User

class QueueItem(BaseModel):
    """
    SQLAlchemy model representing the ordered queue for processing downloads.
    """
    __tablename__ = "download_queue"

    download_id = Column(String(36), ForeignKey("downloads.id"), nullable=False, unique=True)
    priority = Column(Integer, default=0, nullable=False)
    position = Column(Integer, nullable=False, index=True)
    status = Column(String(50), default="queued", nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    download = relationship("Download", backref="queue_item", uselist=False)
    owner = relationship("User", back_populates="queue_items")
    tenant = relationship("Tenant")
