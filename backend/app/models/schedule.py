import enum
from datetime import datetime, time
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Time
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ScheduleTriggerType(str, enum.Enum):
    CRON = "cron"
    RUN_TIME = "run_time"


class DownloadSchedule(BaseModel):
    __tablename__ = "download_schedules"

    profile_id = Column(String(36), ForeignKey("profiles.id"), nullable=True, index=True)
    url = Column(String(1024), nullable=True, index=True)
    trigger_type = Column(String(20), nullable=False, default=ScheduleTriggerType.CRON)
    cron_expression = Column(String(128), nullable=True)
    run_time = Column(Time, nullable=True)
    days_of_week = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    quality_preference = Column(String(50), nullable=False, default="best")
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)

    profile = relationship("Profile", backref="download_schedules")
    tenant = relationship("Tenant")
