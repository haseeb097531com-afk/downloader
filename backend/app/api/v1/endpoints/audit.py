"""Audit log endpoints for Phase 17B."""

from __future__ import annotations

import logging
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user, require_role, require_hierarchy
from app.core.config import settings
from app.db.database import get_db
from app.models.audit_log import AuditLog, AuditAction
from app.models.user import User, UserRole

router = APIRouter(prefix="/auth", tags=["Auth"])


class AuditLogEntry(BaseModel):
    id: str
    action: str
    resource: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    created_at: Optional[str] = None
    username: Optional[str] = None

    @classmethod
    def from_model(cls, log: AuditLog) -> "AuditLogEntry":
        return cls(
            id=log.id,
            action=log.action.value if isinstance(log.action, AuditAction) else log.action,
            resource=log.resource,
            ip=log.ip,
            user_agent=log.user_agent,
            success=log.success,
            created_at=log.created_at.isoformat() if log.created_at else None,
            username=log.actor.username if log.actor else None,
        )


@router.get("/audit", response_model=List[AuditLogEntry])
async def get_audit_log(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.OWNER)),
) -> List[AuditLogEntry]:
    """Return recent audit log entries (owner only)."""
    query = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)

    if action:
        try:
            query = query.where(AuditLog.action == AuditAction(action))
        except ValueError:
            pass
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    result = await db.execute(query)
    logs = result.scalars().all()
    return [AuditLogEntry.from_model(log) for log in logs]
