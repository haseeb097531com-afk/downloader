"""Admin panel endpoints for super_admin only.

Provides aggregated stats and management endpoints for the admin control room.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user, require_role
from app.core import redis_client
from app.core.config import settings
from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole, TenantRole
from app.services.storage.storage_guard import get_disk_status as get_disk
from app.services.network.network_monitor import get_current_speed
from app.services.extractor.ytdlp_engine import YTDLPEngine
from app.services.processor.resource_guard import ResourceGuard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ------------------------------------------------------------------ #
# Schemas
# ------------------------------------------------------------------ #

class AdminStatsResponse(BaseModel):
    # KPIs
    total_tenants: int
    active_tenants: int
    pending_payments: int  # always 0 for stub; placeholder for future
    total_members: int
    downloads_today: int
    downloads_this_month: int
    approved_revenue_this_month: float

    # Health strip
    backend_ok: bool
    redis_ok: bool
    celery_ok: bool
    disk_free_gb: float

    # Chart data (downloads/day, last 7 days)
    downloads_last_7_days: List[dict]


class HealthResponse(BaseModel):
    backend_ok: bool
    redis_ok: bool
    celery_ok: bool
    disk_free_gb: float


class UserAdminResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    role: str
    tenant_id: Optional[str]
    tenant_name: Optional[str]
    is_active: bool
    created_at: Optional[str]
    last_login_at: Optional[str]


class TenantAdminResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    owner_user_id: Optional[str]
    created_at: Optional[str]
    member_count: int


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _require_super_admin(current_user: User) -> User:
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user


async def _check_redis() -> bool:
    try:
        return await redis_client.ping()
    except Exception:
        return False


async def _check_celery() -> bool:
    try:
        from app.core.celery_app import celery_app
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        return stats is not None and len(stats) > 0
    except Exception:
        return False


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminStatsResponse:
    """Return aggregated KPIs, health strip, and chart data (super_admin only)."""
    _require_super_admin(current_user)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Total tenants
    total_tenants_result = await db.execute(select(func.count(Tenant.id)))
    total_tenants = total_tenants_result.scalar() or 0

    # Active tenants
    active_tenants_result = await db.execute(
        select(func.count(Tenant.id)).where(Tenant.status == TenantStatus.ACTIVE)
    )
    active_tenants = active_tenants_result.scalar() or 0

    # Total members (users)
    total_members_result = await db.execute(select(func.count(User.id)))
    total_members = total_members_result.scalar() or 0

    # Downloads today
    from app.models.download import Download
    downloads_today_result = await db.execute(
        select(func.count(Download.id)).where(Download.created_at >= today_start)
    )
    downloads_today = downloads_today_result.scalar() or 0

    # Downloads this month
    downloads_month_result = await db.execute(
        select(func.count(Download.id)).where(Download.created_at >= month_start)
    )
    downloads_this_month = downloads_month_result.scalar() or 0

    # Approved revenue this month (sum of tenant plan values - stub)
    # For stub billing, we approximate by counting non-trial tenants
    tenants_result = await db.execute(
        select(Tenant).where(Tenant.plan != TenantPlan.TRIAL)
    )
    non_trial_tenants = tenants_result.scalars().all()
    plan_values = {
        TenantPlan.STARTER: 29.0,
        TenantPlan.PRO: 79.0,
        TenantPlan.ENTERPRISE: 199.0,
    }
    approved_revenue = sum(plan_values.get(t.plan, 0) for t in non_trial_tenants)

    # Health checks
    redis_ok = await _check_redis()
    celery_ok = await _check_celery()
    disk = get_disk()
    disk_free_gb = round(disk.free_gb, 1) if disk else 0.0
    backend_ok = True  # if we're here, backend is up

    # Chart: downloads per day for last 7 days
    downloads_last_7_days = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_count_result = await db.execute(
            select(func.count(Download.id)).where(
                Download.created_at >= day_start,
                Download.created_at < day_end,
            )
        )
        count = day_count_result.scalar() or 0
        downloads_last_7_days.append({
            "date": day_start.date().isoformat(),
            "count": count,
        })

    return AdminStatsResponse(
        total_tenants=total_tenants,
        active_tenants=active_tenants,
        pending_payments=0,  # stub billing
        total_members=total_members,
        downloads_today=downloads_today,
        downloads_this_month=downloads_this_month,
        approved_revenue_this_month=round(approved_revenue, 2),
        backend_ok=backend_ok,
        redis_ok=redis_ok,
        celery_ok=celery_ok,
        disk_free_gb=disk_free_gb,
        downloads_last_7_days=downloads_last_7_days,
    )


@router.get("/health", response_model=HealthResponse)
async def get_admin_health(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> HealthResponse:
    """Return health strip data (super_admin only)."""
    _require_super_admin(current_user)

    redis_ok = await _check_redis()
    celery_ok = await _check_celery()
    disk = get_disk()
    disk_free_gb = round(disk.free_gb, 1) if disk else 0.0
    backend_ok = True

    return HealthResponse(
        backend_ok=backend_ok,
        redis_ok=redis_ok,
        celery_ok=celery_ok,
        disk_free_gb=disk_free_gb,
    )


@router.get("/users", response_model=List[UserAdminResponse])
async def list_admin_users(
    request: Request,
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    search: Optional[str] = Query(None, description="Search username/email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[UserAdminResponse]:
    """List all users with optional tenant filter and search (super_admin only)."""
    _require_super_admin(current_user)

    query = select(User).order_by(desc(User.created_at))

    if tenant_id:
        query = query.where(User.tenant_id == tenant_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (User.username.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    users = result.scalars().all()

    # Fetch tenant names for display
    tenant_ids = [u.tenant_id for u in users if u.tenant_id]
    tenant_names = {}
    if tenant_ids:
        from app.models.tenant import Tenant as TenantModel
        t_result = await db.execute(
            select(TenantModel.id, TenantModel.name).where(TenantModel.id.in_(tenant_ids))
        )
        tenant_names = {str(t.id): t.name for t in t_result.all()}

    return [
        UserAdminResponse(
            id=str(u.id),
            username=u.username,
            email=u.email,
            role=u.role.value if isinstance(u.role, UserRole) else str(u.role),
            tenant_id=str(u.tenant_id) if u.tenant_id else None,
            tenant_name=tenant_names.get(str(u.tenant_id)) if u.tenant_id else None,
            is_active=u.is_active,
            created_at=u.created_at.isoformat() if u.created_at else None,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
        )
        for u in users
    ]


@router.get("/tenants", response_model=List[TenantAdminResponse])
async def list_admin_tenants(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TenantAdminResponse]:
    """List all tenants with member counts (super_admin only)."""
    _require_super_admin(current_user)

    result = await db.execute(
        select(Tenant).order_by(desc(Tenant.created_at))
    )
    tenants = result.scalars().all()

    # Count members per tenant
    tenant_ids = [str(t.id) for t in tenants]
    member_counts = {}
    if tenant_ids:
        from app.models.user import User as UserModel
        m_result = await db.execute(
            select(UserModel.tenant_id, func.count(UserModel.id))
            .where(UserModel.tenant_id.in_(tenant_ids))
            .group_by(UserModel.tenant_id)
        )
        for tid, count in m_result.all():
            member_counts[str(tid)] = count

    return [
        TenantAdminResponse(
            id=str(t.id),
            name=t.name,
            slug=t.slug,
            plan=t.plan.value if isinstance(t.plan, TenantPlan) else str(t.plan),
            status=t.status.value if isinstance(t.status, TenantStatus) else str(t.status),
            owner_user_id=str(t.owner_user_id) if t.owner_user_id else None,
            created_at=t.created_at.isoformat() if t.created_at else None,
            member_count=member_counts.get(str(t.id), 0),
        )
        for t in tenants
    ]

# ------------------------------------------------------------------ #
# Payments (stub billing — minimal admin queue)
# ------------------------------------------------------------------ #

class PaymentAdminResponse(BaseModel):
    id: str
    tenant_id: str
    tenant_name: str
    plan: str
    amount: float
    reference: str
    status: str  # pending, approved, rejected
    created_at: str
    screenshot_url: Optional[str] = None


class PaymentActionRequest(BaseModel):
    reason: Optional[str] = None


@router.get("/payments", response_model=List[PaymentAdminResponse])
async def list_admin_payments(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PaymentAdminResponse]:
    """List payments (stub billing shows tenant plan changes as payments)."""
    _require_super_admin(current_user)

    # For stub billing, we don't have a PaymentRecord model.
    # Return tenant plan changes as "payments" for admin visibility.
    # In a real implementation, this would query a PaymentRecord table.
    from app.models.tenant import Tenant as TenantModel

    result = await db.execute(
        select(TenantModel).order_by(desc(TenantModel.created_at))
    )
    tenants = result.scalars().all()

    payments = []
    for t in tenants:
        if t.plan != TenantPlan.TRIAL:
            plan_values = {
                TenantPlan.STARTER: 29.0,
                TenantPlan.PRO: 79.0,
                TenantPlan.ENTERPRISE: 199.0,
            }
            payments.append(PaymentAdminResponse(
                id=f"plan_{t.id}",
                tenant_id=str(t.id),
                tenant_name=t.name,
                plan=t.plan.value if isinstance(t.plan, TenantPlan) else str(t.plan),
                amount=plan_values.get(t.plan, 0),
                reference=f"plan_change_{t.id}",
                status="approved",
                created_at=t.plan_started_at.isoformat() if t.plan_started_at else t.created_at.isoformat() if t.created_at else "",
                screenshot_url=None,
            ))

    if status:
        payments = [p for p in payments if p.status == status]

    return payments[offset:offset + limit]


@router.post("/payments/{payment_id}/approve", response_model=PaymentAdminResponse)
async def approve_admin_payment(
    payment_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentAdminResponse:
    """Approve a payment (stub - no-op for stub billing)."""
    _require_super_admin(current_user)
    # For stub billing, just return the payment as approved
    return PaymentAdminResponse(
        id=payment_id,
        tenant_id="",
        tenant_name="",
        plan="",
        amount=0,
        reference="",
        status="approved",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/payments/{payment_id}/reject", response_model=PaymentAdminResponse)
async def reject_admin_payment(
    payment_id: str,
    payload: PaymentActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentAdminResponse:
    """Reject a payment (stub - no-op for stub billing)."""
    _require_super_admin(current_user)
    return PaymentAdminResponse(
        id=payment_id,
        tenant_id="",
        tenant_name="",
        plan="",
        amount=0,
        reference="",
        status="rejected",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


__all__ = ["router"]