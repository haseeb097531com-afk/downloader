"""Quota enforcement service.

Computes usage from existing tables and enforces plan limits at download-create
time. When ``settings.AUTH_ENABLED`` is False the service is a no-op so the
legacy single-user mode never hits a quota.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.download import Download, DownloadStatus
from app.models.tenant import Tenant, TenantPlan
from app.models.user import User
from app.services.billing.plans import PLANS

logger = logging.getLogger(__name__)


@dataclass
class QuotaCheck:
    allowed: bool
    reason: str = ""


@dataclass
class Usage:
    members_count: int
    downloads_this_month: int
    storage_used_gb: float
    concurrent_now: int


class QuotaService:
    """Enforce per-tenant subscription quotas."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_usage(self, tenant_id: str) -> Usage:
        members_result = await self.db.execute(
            select(func.count(User.id)).where(User.tenant_id == tenant_id)
        )
        members_count = members_result.scalar() or 0

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        downloads_result = await self.db.execute(
            select(func.count(Download.id)).where(
                Download.tenant_id == tenant_id,
                Download.created_at >= month_start,
            )
        )
        downloads_this_month = downloads_result.scalar() or 0

        concurrent_result = await self.db.execute(
            select(func.count(Download.id)).where(
                Download.tenant_id == tenant_id,
                Download.status.in_(
                    [DownloadStatus.DOWNLOADING, DownloadStatus.PROCESSING]
                ),
            )
        )
        concurrent_now = concurrent_result.scalar() or 0

        storage_used_gb = 0.0
        try:
            size_result = await self.db.execute(
                select(func.coalesce(func.sum(Download.file_size), 0)).where(
                    Download.tenant_id == tenant_id,
                    Download.file_size.isnot(None),
                )
            )
            storage_used_gb = round((size_result.scalar() or 0) / (1024 ** 3), 2)
        except Exception as exc:
            logger.debug("storage lookup failed for %s: %s", tenant_id, exc)

        return Usage(
            members_count=members_count,
            downloads_this_month=downloads_this_month,
            storage_used_gb=storage_used_gb,
            concurrent_now=concurrent_now,
        )

    async def can_create_download(self, tenant_id: str) -> QuotaCheck:
        if not getattr(settings, "AUTH_ENABLED", False):
            return QuotaCheck(allowed=True)

        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalars().first()
        if tenant is None:
            return QuotaCheck(allowed=False, reason="Tenant not found")

        plan_key = (
            tenant.plan.value if isinstance(tenant.plan, TenantPlan) else str(tenant.plan)
        )
        limits = PLANS.get(plan_key, PLANS["trial"])

        if tenant.status == "suspended":
            return QuotaCheck(allowed=False, reason="Tenant is suspended")

        if tenant.quota_override_until and tenant.quota_override_until > datetime.now(timezone.utc):
            return QuotaCheck(allowed=True)

        usage = await self.get_usage(tenant_id)

        concurrent_limit = limits.get("concurrent", -1)
        if concurrent_limit != -1 and usage.concurrent_now >= concurrent_limit:
            return QuotaCheck(
                allowed=False,
                reason=f"Plan limit reached — upgrade (concurrent {concurrent_limit})",
            )

        downloads_limit = limits.get("downloads_per_month", -1)
        if downloads_limit != -1 and usage.downloads_this_month >= downloads_limit:
            return QuotaCheck(
                allowed=False,
                reason=f"Plan limit reached — upgrade ({downloads_limit}/month)",
            )

        return QuotaCheck(allowed=True)

    async def can_invite_member(self, tenant_id: str) -> QuotaCheck:
        if not getattr(settings, "AUTH_ENABLED", False):
            return QuotaCheck(allowed=True)

        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalars().first()
        if tenant is None:
            return QuotaCheck(allowed=False, reason="Tenant not found")

        plan_key = (
            tenant.plan.value if isinstance(tenant.plan, TenantPlan) else str(tenant.plan)
        )
        limits = PLANS.get(plan_key, PLANS["trial"])

        usage = await self.get_usage(tenant_id)
        member_limit = limits.get("members", -1)
        if member_limit != -1 and usage.members_count >= member_limit:
            return QuotaCheck(
                allowed=False,
                reason=f"Plan limit reached — upgrade ({member_limit} members)",
            )

        return QuotaCheck(allowed=True)


__all__ = ["QuotaService", "QuotaCheck", "Usage"]
