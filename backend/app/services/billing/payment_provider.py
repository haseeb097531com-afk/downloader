"""Payment provider abstraction (stub only — no real money).

Swap ``StubProvider`` for a real implementation when keys are configured.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.models.tenant import Tenant, TenantPlan

logger = logging.getLogger(__name__)


class PaymentProvider(ABC):
    @abstractmethod
    async def create_checkout_session(self, tenant: Tenant, plan: str) -> dict:
        """Return a checkout session payload."""

    @abstractmethod
    async def handle_webhook(self, payload: bytes, signature: Optional[str]) -> dict:
        """Verify and apply a provider webhook."""

    @abstractmethod
    async def cancel(self, tenant: Tenant) -> dict:
        """Cancel the active subscription for a tenant."""


class StubProvider(PaymentProvider):
    """Stub provider for local/dev. Logs and returns a fake session."""

    async def create_checkout_session(self, tenant: Tenant, plan: str) -> dict:
        logger.info("STUB checkout tenant=%s plan=%s", tenant.id, plan)
        return {
            "session_id": f"stub_{plan}_{tenant.id}",
            "url": "https://example.com/contact-sales",
        }

    async def handle_webhook(self, payload: bytes, signature: Optional[str]) -> dict:
        logger.info("STUB webhook received len=%s sig=%s", len(payload), signature)
        return {"accepted": True}

    async def cancel(self, tenant: Tenant) -> dict:
        logger.info("STUB cancel tenant=%s", tenant.id)
        return {"cancelled": True}


__all__ = ["PaymentProvider", "StubProvider"]
