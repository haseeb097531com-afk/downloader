"""Authentication and user management endpoints for Phase 17A."""

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
    require_role,
    require_hierarchy,
    visible_users,
    OwnerFilter,
)
from app.core.config import settings
from app.core.security import (
    AuthError,
    PasswordStrengthError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.core import redis_client
from app.core.rate_limit import RateLimiter
from app.db.database import get_db
from app.models.user import User, UserRole, TenantRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ------------------------------------------------------------------ #
# Schemas (inline, matching existing endpoint convention)
# ------------------------------------------------------------------ #

class LoginRequest(BaseModel):
    username_or_email: str = Field(..., description="Username or email address")
    password: str = Field(..., description="Plaintext password")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="Short-lived JWT access token")
    refresh_token: str = Field(..., description="Long-lived JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    user: UserResponse = Field(..., description="Current user profile")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Valid refresh token")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password meeting strength requirements")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str | None = Field(None, description="Optional email address")
    password: str = Field(..., description="Initial password")
    role: UserRole = Field(UserRole.USER, description="Assigned role")


class UserUpdateRequest(BaseModel):
    role: UserRole | None = Field(None, description="New role")
    is_active: bool | None = Field(None, description="Whether the account is active")


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: str | None
    created_at: str | None
    parent_id: str | None = None
    tenant_role: str | None = None
    tenant_id: str | None = None
    tenant_plan: str | None = None


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _user_to_response(user: User, tenant_plan: str | None = None) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
        parent_id=user.parent_id,
        tenant_role=user.tenant_role.value if isinstance(user.tenant_role, TenantRole) else user.tenant_role,
        tenant_id=user.tenant_id,
        tenant_plan=tenant_plan,
    )


def _generate_temp_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _record_audit(
    db: AsyncSession,
    action: str,
    user_id: str | None,
    request: Request,
    success: bool = True,
    resource: str | None = None,
) -> None:
    from app.models.audit_log import AuditLog, AuditAction

    try:
        log = AuditLog(
            user_id=user_id,
            action=AuditAction(action),
            resource=resource,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=success,
        )
        db.add(log)
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", exc)
        await db.rollback()


def _assert_can_manage(
    current_user: User,
    target_user: User,
) -> None:
    """Raise 403 if the current user cannot manage the target user.

    Rules:
    - owner can manage anyone except themselves (for delete)
    - sub_admin can manage users under their hierarchy, but NOT owner or other sub_admins
    - user cannot manage anyone
    """
    if current_user.role == UserRole.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    if current_user.role == UserRole.SUB_ADMIN:
        # Cannot manage owner
        if target_user.role == UserRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot manage owner account",
            )
        # Cannot manage other sub_admins
        if target_user.role == UserRole.SUB_ADMIN and target_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot manage other sub-admin accounts",
            )
        # Cannot manage users not under their hierarchy
        if target_user.parent_id != current_user.id and target_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot manage users outside your hierarchy",
            )


# ------------------------------------------------------------------ #
# Login
# ------------------------------------------------------------------ #

@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate a user and return JWT tokens.

    Implements account lockout after ``settings.MAX_FAILED_LOGINS`` failed
    attempts within ``settings.LOCK_MINUTES`` minutes.
    """
    if not getattr(settings, "AUTH_ENABLED", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authentication is disabled")

    _login_limiter = RateLimiter(requests=5, window_seconds=60)
    client = redis_client.get_redis()
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"auth:login:{client_ip}"
    allowed, retry_after = _login_limiter.is_allowed(rate_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    result = await db.execute(
        select(User).where(
            (User.username == payload.username_or_email) | (User.email == payload.username_or_email)
        )
    )
    user = result.scalars().first()

    password_valid = False
    if user is not None:
        password_valid = verify_password(payload.password, user.password_hash)

    if not password_valid or user is None:
        if user is not None:
            user.failed_login_count += 1
            max_failed = getattr(settings, "MAX_FAILED_LOGINS", 5)
            lock_minutes = getattr(settings, "LOCK_MINUTES", 15)
            if user.failed_login_count >= max_failed:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
                await db.commit()
                await _record_audit(db, "lockout", user.id if user else None, request, success=False)
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account locked for {lock_minutes} minutes due to too many failed attempts",
                )
            await db.commit()

        target_user_id = user.id if user else None
        await _record_audit(db, "login_failure", target_user_id, request, success=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        await _record_audit(db, "lockout", user.id, request, success=False)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked",
        )

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    access_token, _ = create_access_token(user.id, user.role.value)
    refresh_token, _ = create_refresh_token(user.id, user.token_version)

    await _record_audit(db, "login_success", user.id, request, success=True)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=_user_to_response(user),
    )


# ------------------------------------------------------------------ #
# Refresh
# ------------------------------------------------------------------ #

@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Issue a new access token using a valid refresh token."""
    try:
        token_payload = decode_token(payload.refresh_token)
    except AuthError as exc:
        await _record_audit(db, "login_failure", None, request, success=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message) from exc

    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = token_payload.get("sub")
    token_version = token_payload.get("token_version", 0)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    if user.token_version != token_version:
        await _record_audit(db, "logout", user.id, request, success=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    access_token, _ = create_access_token(user.id, user.role.value)
    new_refresh_token, _ = create_refresh_token(user.id, user.token_version)

    await _record_audit(db, "login_success", user.id, request, success=True)

    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=_user_to_response(user),
    )


# ------------------------------------------------------------------ #
# Logout
# ------------------------------------------------------------------ #

@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke all refresh tokens for the current user."""
    current_user.token_version += 1
    await db.commit()
    await _record_audit(db, "logout", current_user.id, request, success=True)
    return {"message": "Logged out successfully"}


# ------------------------------------------------------------------ #
# Current user profile
# ------------------------------------------------------------------ #

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    tenant_plan = None
    if current_user.tenant_id and not current_user.is_super_admin:
        result = await db.execute(select(Tenant.plan).where(Tenant.id == current_user.tenant_id))
        plan = result.scalar_one_or_none()
        tenant_plan = plan.value if isinstance(plan, TenantPlan) else (plan if plan else None)
    return _user_to_response(current_user, tenant_plan)


# ------------------------------------------------------------------ #
# Change password
# ------------------------------------------------------------------ #

@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change the current user's password."""
    if not verify_password(payload.old_password, current_user.password_hash):
        await _record_audit(db, "password_change", current_user.id, request, success=False)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid old password")

    try:
        validate_password_strength(payload.new_password)
    except PasswordStrengthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    await db.commit()

    await _record_audit(db, "password_change", current_user.id, request, success=True)
    return {"message": "Password changed successfully"}


# ------------------------------------------------------------------ #
# User management (owner + sub_admin only)
# ------------------------------------------------------------------ #

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.SUB_ADMIN)),
) -> UserResponse:
    """Create a new user (owner or sub_admin only).

    Owner can create sub_admin and user.
    Sub_admin can only create user under themselves.
    """
    if current_user.role == UserRole.SUB_ADMIN and payload.role != UserRole.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sub-admin can only create worker accounts",
        )

    existing = await db.execute(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    )
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists")

    try:
        validate_password_strength(payload.password)
    except PasswordStrengthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    parent_id = current_user.id if current_user.role == UserRole.SUB_ADMIN else None
    if payload.role == UserRole.SUB_ADMIN and current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner can create sub-admin accounts",
        )

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        must_change_password=True,
        parent_id=parent_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await _record_audit(db, "user_create", user.id, request, success=True, resource=user.username)
    return _user_to_response(user)


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.SUB_ADMIN)),
) -> List[UserResponse]:
    """List users visible to the current user.

    Owner sees everyone.
    Sub_admin sees only their workers.
    """
    visible = await visible_users(current_user, db)
    result = await db.execute(
        select(User).where(User.id.in_(visible)).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return [_user_to_response(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.SUB_ADMIN)),
) -> UserResponse:
    """Update a user's role, active status, or reset password (owner/sub_admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _assert_can_manage(current_user, user)

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    await db.commit()
    await db.refresh(user)

    await _record_audit(db, "user_update", user.id, request, success=True, resource=user.username)
    return _user_to_response(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.SUB_ADMIN)),
) -> None:
    """Delete a user (owner/sub_admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")

    _assert_can_manage(current_user, user)

    await db.delete(user)
    await db.commit()

    await _record_audit(db, "user_delete", user.id, request, success=True, resource=user.username)
