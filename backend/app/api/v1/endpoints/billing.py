"""Billing endpoints for subscription management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import get_current_user, require_role
from app.core.config import settings
from app.db.database import get_db
from app.models.tenant import Tenant, TenantPlan, TenantStatus
from app.models.user import User, UserRole, TenantRole
from app.services.billing.payment_provider import PaymentProvider, StubProvider
from app.services.billing.plans import PLANS
from app.services.billing.quota_service import QuotaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


# ------------------------------------------------------------------ #
# Schemas
# ------------------------------------------------------------------ #

class CheckoutRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant to bill")
    plan: str = Field(..., description="Target plan slug")


class CheckoutResponse(BaseModel):
    session_id: str
    url: str


class WebhookResponse(BaseModel):
    accepted: bool


class PlansResponse(BaseModel):
    plans: dict[str, dict[str, int | float]]


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _provider() -> PaymentProvider:
    provider_name = getattr(settings, "PAYMENT_PROVIDER", "stub")
    if provider_name == "stripe":
        try:
            from app.services.billing.stripe_provider import StripeProvider
            return StripeProvider()
        except Exception:
            pass
    return StubProvider()


def _assert_tenant_owner(current_user: User, tenant: Tenant) -> None:
    if current_user.is_super_admin:
        return
    if current_user.tenant_id != tenant.id or current_user.tenant_role != TenantRole.TENANT_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant owner access required",
        )


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    if not getattr(settings, "BILLING_ENABLED", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured",
        )

    result = await db.execute(select(Tenant).where(Tenant.id == payload.tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    _assert_tenant_owner(current_user, tenant)

    if payload.plan not in PLANS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

    provider = _provider()
    session = await provider.create_checkout_session(tenant, payload.plan)
    return CheckoutResponse(session_id=session["session_id"], url=session["url"])


@router.post("/webhook", response_model=WebhookResponse)
async def billing_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    if not getattr(settings, "BILLING_ENABLED", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured",
        )

    payload = await request.body()
    signature = request.headers.get("stripe-signature") or request.headers.get("x-signature")

    provider = _provider()
    result = await provider.handle_webhook(payload, signature)
    if not result.get("accepted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook rejected")

    event = result.get("event") or {}
    tenant_id = event.get("tenant_id")
    plan = event.get("plan")
    expires_at = event.get("plan_expires_at")
    auto_renew = event.get("auto_renew", False)

    if tenant_id and plan:
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalars().first()
        if tenant and plan in [tp.value for tp in TenantPlan]:
            tenant.plan = TenantPlan(plan)
            if expires_at:
                tenant.plan_expires_at = datetime.fromisoformat(expires_at)
            tenant.auto_renew = bool(auto_renew)
            await db.commit()
            logger.info("Billing webhook updated tenant %s -> plan=%s", tenant_id, plan)

    return WebhookResponse(accepted=True)


@router.get("/plans", response_model=PlansResponse)
async def list_plans() -> PlansResponse:
    return PlansResponse(plans=PLANS)


@router.post("/{tenant_id}/cancel")
async def cancel_subscription(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    _assert_tenant_owner(current_user, tenant)

    provider = _provider()
    await provider.cancel(tenant)
    tenant.auto_renew = False
    await db.commit()
    return {"cancelled": True}
