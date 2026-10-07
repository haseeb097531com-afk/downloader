"""Feature access map and plan tier definitions.

Single source of truth for both backend enforcement and frontend rendering.
"""

from __future__ import annotations

FEATURE_ACCESS: dict[str, str] = {
    "home": "all",
    "library": "all",
    "queue": "all",
    "search": "all",
    "collections": "starter",
    "profiles": "starter",
    "remote": "starter",
    "analytics_basic": "all",
    "analytics_full": "pro",
    "plugins": "pro",
    "safety": "pro",
    "team": "tenant_owner",
    "tenants": "super_admin",
}

PLAN_TIERS: dict[str, int] = {
    "trial": 0,
    "starter": 1,
    "pro": 2,
    "enterprise": 3,
}

__all__ = ["FEATURE_ACCESS", "PLAN_TIERS"]
