"""Multi-tenant management endpoints.

Provides:
- CRUD for tenants (super_admin only)
- Member management within a tenant (tenant_owner only)
- Impersonation endpoint for super_admin
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import (
    get_current_user,
    get_tenant_from_header,
    require_role,
    OwnerFilter,
)
from app.core.config import settings
from app.core.security import create_access_token, hash_password, validate_password_strength
from app.db.database import get_db
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole, TenantRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["Tenants"])


# ------------------------------------------------------------------ #
# Schemas
# ------------------------------------------------------------------ #

class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Display name for the tenant")
    slug: str = Field(..., min_length=1, max_length=100, description="Unique URL-safe slug")
    plan: TenantPlan = Field(TenantPlan.TRIAL, description="Subscription plan")
    owner_user_id: str | None = Field(None, description="User ID to assign as tenant owner")


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=255, description="New display name")
    settings_json: dict | None = Field(None, description="Arbitrary tenant settings")
    plan: TenantPlan | None = Field(None, description="New subscription plan")
    status: TenantStatus | None = Field(None, description="New account status")


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    owner_user_id: str | None
    settings_json: dict | None
    created_at: str | None
    suspended_at: str | None
    plan_started_at: str | None
    plan_expires_at: str | None
    auto_renew: bool
    trial_used: bool
    quota_override_until: str | None


class MemberInviteRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username for the new member")
    email: str | None = Field(None, description="Optional email address")
    password: str | None = Field(None, description="Optional initial password (auto-generated when omitted)")


class MemberResponse(BaseModel):
    id: str
    username: str
    email: str | None
    tenant_role: str
    tenant_id: str | None
    is_active: bool
    created_at: str | None


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    tenant_name: str


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _tenant_to_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan.value if isinstance(tenant.plan, TenantPlan) else tenant.plan,
        status=tenant.status.value if isinstance(tenant.status, TenantStatus) else tenant.status,
        owner_user_id=tenant.owner_user_id,
        settings_json=tenant.settings_json,
        created_at=tenant.created_at.isoformat() if tenant.created_at else None,
        suspended_at=tenant.suspended_at.isoformat() if tenant.suspended_at else None,
        plan_started_at=tenant.plan_started_at.isoformat() if tenant.plan_started_at else None,
        plan_expires_at=tenant.plan_expires_at.isoformat() if tenant.plan_expires_at else None,
        auto_renew=bool(tenant.auto_renew),
        trial_used=bool(tenant.trial_used),
        quota_override_until=tenant.quota_override_until.isoformat() if tenant.quota_override_until else None,
    )


def _member_to_response(user: User) -> MemberResponse:
    return MemberResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        tenant_role=user.tenant_role.value if isinstance(user.tenant_role, TenantRole) else user.tenant_role,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


def _assert_super_admin(current_user: User) -> None:
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )


def _assert_tenant_owner(current_user: User, tenant: Tenant) -> None:
    if current_user.is_super_admin:
        return
    if current_user.tenant_id != tenant.id or current_user.tenant_role != TenantRole.TENANT_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant owner access required",
        )


def _generate_temp_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ------------------------------------------------------------------ #
# Tenant CRUD (super_admin only)
# ------------------------------------------------------------------ #

@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER)),
) -> TenantResponse:
    """Create a new tenant (super_admin only)."""
    _assert_super_admin(current_user)

    existing = await db.execute(select(Tenant).where(Tenant.slug == payload.slug))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant slug already exists")

    owner_user_id = payload.owner_user_id
    if owner_user_id:
        owner_result = await db.execute(select(User).where(User.id == owner_user_id))
        owner_user = owner_result.scalars().first()
        if owner_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner user not found")
        if owner_user.tenant_id is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already belongs to a tenant")

    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        plan=payload.plan,
        status=TenantStatus.ACTIVE,
        owner_user_id=owner_user_id,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    if owner_user_id:
        owner_user.tenant_id = tenant.id
        owner_user.tenant_role = TenantRole.TENANT_OWNER
        await db.commit()
        await db.refresh(tenant)

    logger.info("Tenant created: %s by %s", tenant.slug, current_user.username)
    return _tenant_to_response(tenant)


@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER)),
) -> List[TenantResponse]:
    """List all tenants (super_admin only)."""
    _assert_super_admin(current_user)

    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()
    return [_tenant_to_response(t) for t in tenants]


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantResponse:
    """Get a single tenant by id."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if current_user.is_super_admin or (current_user.tenant_id == tenant.id and current_user.tenant_role == TenantRole.TENANT_OWNER):
        return _tenant_to_response(tenant)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    payload: TenantUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantResponse:
    """Update tenant name, settings, plan, or status."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    _assert_tenant_owner(current_user, tenant)

    if payload.name is not None:
        tenant.name = payload.name
    if payload.settings_json is not None:
        tenant.settings_json = payload.settings_json
    if payload.plan is not None:
        tenant.plan = payload.plan
    if payload.status is not None:
        tenant.status = payload.status
        if payload.status == TenantStatus.SUSPENDED:
            tenant.suspended_at = datetime.now(timezone.utc)
        else:
            tenant.suspended_at = None

    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_response(tenant)


# ------------------------------------------------------------------ #
# Member management (tenant_owner only)
# ------------------------------------------------------------------ #

@router.post("/{tenant_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    tenant_id: str,
    payload: MemberInviteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemberResponse:
    """Invite a new member to the tenant (tenant_owner only)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    _assert_tenant_owner(current_user, tenant)

    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    password = payload.password or _generate_temp_password()
    try:
        validate_password_strength(password)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    member = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(password),
        role=UserRole.USER,
        is_active=True,
        must_change_password=not bool(payload.password),
        tenant_id=tenant.id,
        tenant_role=TenantRole.MEMBER,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    logger.info("Member invited to tenant %s: %s by %s", tenant.slug, member.username, current_user.username)
    return _member_to_response(member)


@router.get("/{tenant_id}/members", response_model=List[MemberResponse])
async def list_members(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[MemberResponse]:
    """List all members of a tenant (tenant_owner or super_admin only)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    _assert_tenant_owner(current_user, tenant)

    members_result = await db.execute(
        select(User).where(User.tenant_id == tenant.id).order_by(User.created_at.desc())
    )
    members = members_result.scalars().all()
    return [_member_to_response(m) for m in members]


@router.delete("/{tenant_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_member(
    tenant_id: str,
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Revoke a member's access to the tenant (tenant_owner only)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    _assert_tenant_owner(current_user, tenant)

    member_result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant.id))
    member = member_result.scalars().first()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if member.tenant_role == TenantRole.TENANT_OWNER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot revoke the tenant owner")

    member.tenant_id = None
    member.tenant_role = None
    await db.commit()

    logger.info("Member revoked from tenant %s: %s by %s", tenant.slug, member.username, current_user.username)


# ------------------------------------------------------------------ #
# Impersonation (super_admin only)
# ------------------------------------------------------------------ #

@router.post("/{tenant_id}/impersonate", response_model=ImpersonateResponse)
async def impersonate_tenant(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImpersonateResponse:
    """Generate a scoped access token for a tenant (super_admin only)."""
    _assert_super_admin(current_user)

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.status == TenantStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot impersonate a suspended tenant")

    # Build a synthetic impersonation token.
    # The token carries the super_admin's id as sub, but adds an "impersonating_tenant_id" claim.
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=getattr(settings, "JWT_ACCESS_TTL_MIN", 30)
    )
    payload = {
        "sub": str(current_user.id),
        "role": current_user.role.value,
        "type": "access",
        "impersonating_tenant_id": str(tenant.id),
        "jti": secrets.token_urlsafe(16),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    from app.core.security import jwt
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    return ImpersonateResponse(
        access_token=token,
        token_type="bearer",
        tenant_id=tenant.id,
        tenant_name=tenant.name,
    )


# ------------------------------------------------------------------ #
# Billing management (super_admin only)
# ------------------------------------------------------------------ #

class PlanChangeRequest(BaseModel):
    plan: TenantPlan = Field(..., description="New plan for the tenant")


class ExpiryRequest(BaseModel):
    plan_expires_at: str | None = Field(None, description="ISO expiry date; null clears it")
    auto_renew: bool | None = Field(None, description="Whether to auto-renew")


class WaiveQuotaRequest(BaseModel):
    hours: int = Field(24, ge=1, le=720, description="Hours to waive quota for")


@router.patch("/{tenant_id}/plan", response_model=TenantResponse)
async def change_plan(
    tenant_id: str,
    payload: PlanChangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantResponse:
    _assert_super_admin(current_user)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    tenant.plan = payload.plan
    tenant.plan_started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tenant)

    from app.models.audit_log import AuditLog, AuditAction
    log = AuditLog(
        user_id=current_user.id,
        action=AuditAction.SETTINGS_CHANGE,
        resource=f"tenant:{tenant_id}",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        success=True,
        meta=f"plan -> {payload.plan.value}",
        tenant_id=tenant_id,
    )
    db.add(log)
    await db.commit()

    return _tenant_to_response(tenant)


@router.patch("/{tenant_id}/expiry", response_model=TenantResponse)
async def set_expiry(
    tenant_id: str,
    payload: ExpiryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantResponse:
    _assert_super_admin(current_user)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if payload.plan_expires_at:
        tenant.plan_expires_at = datetime.fromisoformat(payload.plan_expires_at)
    else:
        tenant.plan_expires_at = None

    if payload.auto_renew is not None:
        tenant.auto_renew = payload.auto_renew

    await db.commit()
    await db.refresh(tenant)

    from app.models.audit_log import AuditLog, AuditAction
    log = AuditLog(
        user_id=current_user.id,
        action=AuditAction.SETTINGS_CHANGE,
        resource=f"tenant:{tenant_id}",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        success=True,
        meta=f"expiry -> {payload.plan_expires_at} auto_renew={payload.auto_renew}",
        tenant_id=tenant_id,
    )
    db.add(log)
    await db.commit()

    return _tenant_to_response(tenant)


@router.post("/{tenant_id}/waive-quota", response_model=TenantResponse)
async def waive_quota(
    tenant_id: str,
    payload: WaiveQuotaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TenantResponse:
    _assert_super_admin(current_user)
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    from datetime import timedelta
    tenant.quota_override_until = datetime.now(timezone.utc) + timedelta(hours=payload.hours)
    await db.commit()
    await db.refresh(tenant)

    from app.models.audit_log import AuditLog, AuditAction
    log = AuditLog(
        user_id=current_user.id,
        action=AuditAction.SETTINGS_CHANGE,
        resource=f"tenant:{tenant_id}",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        success=True,
        meta=f"waive quota {payload.hours}h",
        tenant_id=tenant_id,
    )
    db.add(log)
    await db.commit()

    return _tenant_to_response(tenant)
