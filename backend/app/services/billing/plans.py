"""Plan limits constant for quota enforcement."""

from __future__ import annotations

PLANS: dict[str, dict[str, int | float]] = {
    "trial": {
        "members": 2,
        "downloads_per_month": 50,
        "storage_gb": 5,
        "concurrent": 1,
        "days": 14,
    },
    "starter": {
        "members": 5,
        "downloads_per_month": 500,
        "storage_gb": 50,
        "concurrent": 3,
        "days": 30,
    },
    "pro": {
        "members": 20,
        "downloads_per_month": 5000,
        "storage_gb": 500,
        "concurrent": 8,
        "days": 30,
    },
    "enterprise": {
        "members": -1,
        "downloads_per_month": -1,
        "storage_gb": -1,
        "concurrent": -1,
        "days": -1,
    },
}

__all__ = ["PLANS"]
