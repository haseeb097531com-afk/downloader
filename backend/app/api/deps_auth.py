"""Authentication and authorization dependencies for FastAPI.

Provides:
- get_current_user: Bearer JWT -> User
- require_role(*roles): role-based access control dependency factory
- require_hierarchy(min_role): hierarchy-based access control
- visible_users(current_user): returns a subquery of user IDs the current user can see
- OwnerFilter: SQLAlchemy query modifier for data scoping
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, TypeVar

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.sql.functions import GenericFunction

from app.core.config import settings
from app.core.security import AuthError, decode_token
from app.features import FEATURE_ACCESS, PLAN_TIERS
from app.models.tenant import Tenant, TenantPlan
from app.models.user import User, UserRole, TenantRole
from app.db.database import get_db

logger = logging.getLogger(__name__)

T = TypeVar("T")

__all__ = [
    "get_current_user",
    "require_role",
    "require_hierarchy",
    "visible_users",
    "OwnerFilter",
    "get_optional_user",
    "get_tenant_from_header",
    "require_feature",
]


# ------------------------------------------------------------------ #
# Current user
# ------------------------------------------------------------------ #

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the current authenticated user from the Bearer token.

    When ``settings.AUTH_ENABLED`` is False, returns a synthetic system user
    so legacy single-user mode continues to work without authentication.

    Raises:
        HTTPException 401: When the token is missing, invalid, or the user
            is not found / inactive.
    """
    if not getattr(settings, "AUTH_ENABLED", False):
        system_user = User(
            id="00000000-0000-0000-0000-000000000000",
            username="system",
            role=UserRole.OWNER,
            is_active=True,
        )
        return system_user

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[len("Bearer ") :].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Try to resolve the current user; return None when unauthenticated."""
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


# ------------------------------------------------------------------ #
# Role-based access control
# ------------------------------------------------------------------ #

def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """Return a FastAPI dependency that enforces role-based access.

    Args:
        *allowed_roles: Role strings permitted to access the route.

    Returns:
        A dependency function that returns the current user when authorized,
        or raises 403 when the user's role is not in ``allowed_roles``.
    """
    async def _enforce(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                "Permission denied: user %s with role %s tried to access a route requiring %s",
                current_user.username,
                current_user.role,
                allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _enforce


# ------------------------------------------------------------------ #
# Hierarchy-based access control
# ------------------------------------------------------------------ #

def require_hierarchy(min_role: UserRole) -> Callable[[User], User]:
    """Return a FastAPI dependency that enforces minimum hierarchy level.

    Hierarchy: owner > sub_admin > user

    Args:
        min_role: The minimum role required to access the route.

    Returns:
        A dependency function that returns the current user when authorized,
        or raises 403 when the user's role is below ``min_role`` in the hierarchy.
    """
    _HIERARCHY = {UserRole.OWNER: 0, UserRole.SUB_ADMIN: 1, UserRole.USER: 2}
    min_level = _HIERARCHY.get(min_role, 999)

    async def _enforce(current_user: User = Depends(get_current_user)) -> User:
        user_level = _HIERARCHY.get(current_user.role, 999)
        if user_level > min_level:
            logger.warning(
                "Hierarchy denied: user %s with role %s (level %d) tried to access a route requiring %s (level %d)",
                current_user.username,
                current_user.role,
                user_level,
                min_role,
                min_level,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _enforce


async def visible_users(
    current_user: User,
    db: AsyncSession,
) -> List[str]:
    """Return a list of user IDs visible to the current user.

    Hierarchy rules:
    - owner -> everyone (all user IDs)
    - sub_admin -> himself + users whose parent chain leads to him
    - user -> only himself

    When auth is disabled, returns all user IDs (legacy single-user mode).
    """
    if not getattr(settings, "AUTH_ENABLED", False):
        result = await db.execute(select(User.id))
        return [row[0] for row in result.all()]

    if current_user.role == UserRole.OWNER:
        result = await db.execute(select(User.id))
        return [row[0] for row in result.all()]

    if current_user.role == UserRole.SUB_ADMIN:
        # Self + descendants (recursive CTE)
        cte = (
            select(User.id)
            .where(User.id == current_user.id)
            .cte(recursive=True)
        )
        descendant = select(User.id).join(cte, User.parent_id == cte.c.id)
        cte = cte.union_all(descendant)
        result = await db.execute(select(cte.c.id))
        return [row[0] for row in result.all()]

    # user -> only himself
    return [current_user.id]


# ------------------------------------------------------------------ #
# Owner-based query scoping
# ------------------------------------------------------------------ #

class OwnerFilter:
    """SQLAlchemy query modifier that scopes results to visible users.

    Usage::

        query = OwnerFilter.apply(current_user, select(Download), Download, visible_ids=None)
        result = await db.execute(query)
    """

    @staticmethod
    def apply(
        current_user: User,
        query: Select[T],
        model: type,
        visible_user_ids: Optional[List[str]] = None,
    ) -> Select[T]:
        """Apply owner scoping to ``query`` when auth is enabled.

        When ``settings.AUTH_ENABLED`` is False, the query is returned
        unchanged to preserve legacy single-user behavior.

        Args:
            current_user: Resolved authenticated user.
            query: SQLAlchemy select query to modify.
            model: The SQLAlchemy model class the query targets (must have
                an ``owner_id`` column).
            visible_user_ids: Optional pre-computed list of visible user IDs.
                If not provided, falls back to ``current_user.id`` for non-owner roles.

        Returns:
            The scoped (or unscoped) query.
        """
        if not getattr(settings, "AUTH_ENABLED", False):
            return query
        owner_col = getattr(model, "owner_id", None)
        if owner_col is None:
            return query

        if current_user.role == UserRole.OWNER:
            return query

        if visible_user_ids is not None:
            return query.where(owner_col.in_(visible_user_ids))

        return query.where(owner_col == current_user.id)

    @staticmethod
    def apply_tenant(
        current_user: User,
        query: Select[T],
        model: type,
        request: Optional[Request] = None,
    ) -> Select[T]:
        """Apply tenant scoping to ``query`` when auth is enabled.

        When ``settings.AUTH_ENABLED`` is False, the query is returned
        unchanged to preserve legacy single-user behavior.

        Args:
            current_user: Resolved authenticated user.
            query: SQLAlchemy select query to modify.
            model: The SQLAlchemy model class the query targets (may or may
                not have a ``tenant_id`` column).
            request: Optional FastAPI request; used to read the
                ``X-Tenant-Id`` header for super_admin impersonation.

        Returns:
            The scoped (or unscoped) query.
        """
        if not getattr(settings, "AUTH_ENABLED", False):
            return query

        tenant_col = getattr(model, "tenant_id", None)
        if tenant_col is None:
            # Model does not support multi-tenant scoping; fall back to owner filter.
            return OwnerFilter.apply(current_user, query, model)

        if current_user.is_super_admin:
            # Super_admin can optionally impersonate a tenant via header.
            impersonated_tenant_id = get_tenant_from_header(request)
            if impersonated_tenant_id:
                return query.where(tenant_col == impersonated_tenant_id)
            return query

        if current_user.tenant_id is None:
            return query

        return query.where(tenant_col == current_user.tenant_id)


def get_tenant_from_header(request: Optional[Request]) -> Optional[str]:
    """Extract an optional tenant id from the ``X-Tenant-Id`` request header.

    Returns the header value when present, or ``None`` when absent.
    """
    if request is None:
        return None
    return request.headers.get("X-Tenant-Id")


# ------------------------------------------------------------------ #
# Feature-gated access control
# ------------------------------------------------------------------ #

async def _resolve_tenant_plan(
    request: Request,
    current_user: User,
    db: AsyncSession,
) -> str:
    """Resolve the effective plan tier for the current request.

    Bypasses when auth is disabled or the caller is a super_admin.
    Honors ``X-Tenant-Id`` impersonation for super_admin.
    Falls back to ``trial`` when the tenant record is missing.
    """
    if not getattr(settings, "AUTH_ENABLED", False):
        return "enterprise"

    if current_user.is_super_admin:
        return "enterprise"

    tenant_id = current_user.tenant_id
    if not tenant_id:
        return "trial"

    impersonated = request.headers.get("X-Tenant-Id")
    if impersonated:
        tenant_id = impersonated

    result = await db.execute(select(Tenant.plan).where(Tenant.id == tenant_id))
    plan = result.scalar_one_or_none()
    if plan is None:
        return "trial"
    return plan.value if isinstance(plan, TenantPlan) else str(plan)


def require_feature(feature_key: str):
    """Return a FastAPI dependency that enforces minimum plan tier for a feature.

    Args:
        feature_key: Key into ``FEATURE_ACCESS`` (e.g. ``"plugins"``).

    Returns:
        A dependency that returns the current user when authorized,
        or raises 403 with ``UPGRADE_REQUIRED`` when below tier.
    """
    needed_plan = FEATURE_ACCESS.get(feature_key)
    if needed_plan is None or needed_plan == "all":
        async def _allow(
            request: Request,
            current_user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db),
        ) -> User:
            return current_user
        return _allow

    async def _enforce(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        plan = await _resolve_tenant_plan(request, current_user, db)
        if PLAN_TIERS.get(plan, 0) < PLAN_TIERS.get(needed_plan, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "UPGRADE_REQUIRED",
                    "feature": feature_key,
                    "current_plan": plan,
                    "needed_plan": needed_plan,
                },
            )
        return current_user

    return _enforce
