"""Provider registry and fallback extraction endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.models.extraction_attempt import ExtractionAttempt
from app.services.extractor.api_providers import ProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Providers"])


def get_registry() -> ProviderRegistry:
    return ProviderRegistry()


@router.get("/providers/status")
async def get_providers_status(registry: ProviderRegistry = Depends(get_registry)) -> dict:
    """Return provider status and recent extraction attempts."""
    providers = [p.__dict__ for p in registry.list_providers()]

    try:
        from sqlalchemy import desc
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            cutoff = datetime.utcnow() - timedelta(hours=24)
            result = await db.execute(
                select(ExtractionAttempt)
                .where(ExtractionAttempt.created_at >= cutoff)
                .order_by(ExtractionAttempt.created_at.desc())
                .limit(10)
            )
            recent = [
                {
                    "url": a.url,
                    "provider": a.provider,
                    "success": a.success,
                    "error_message": a.error_message,
                    "latency_ms": a.latency_ms,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in result.scalars().all()
            ]
    except Exception as exc:
        logger.warning("Failed to load recent attempts: %s", exc)
        recent = []

    return {"providers": providers, "recent_attempts": recent}


@router.post("/providers/test/{provider}")
async def test_provider(provider: str, registry: ProviderRegistry = Depends(get_registry)) -> dict:
    """Lightweight test call for the provider's API key."""
    if provider not in ("scraperapi", "zenrows", "rapidapi"):
        raise HTTPException(status_code=400, detail="Unknown provider")

    if not registry.can_use(provider):
        return {"success": False, "message": "Provider is not configured or rate-limited"}

    start = datetime.utcnow()
    try:
        if provider in ("scraperapi", "zenrows"):
            test_url = "https://httpbin.org/get"
            async with httpx.AsyncClient(timeout=15) as client:
                api_key = settings.SCRAPER_API_KEY
                if provider == "scraperapi":
                    target = f"https://api.scraperapi.com/?api_key={api_key}&url={test_url}"
                else:
                    target = f"https://api.zenrows.com/v1/?apikey={api_key}&url={test_url}"
                response = await client.get(target)
                success = response.status_code == 200
                message = "OK" if success else f"HTTP {response.status_code}"
        else:
            return {"success": True, "message": "RapidAPI key is configured"}

        latency = int((datetime.utcnow() - start).total_seconds() * 1000)
        return {"success": success, "message": message, "latency_ms": latency}
    except Exception as exc:
        return {"success": False, "message": str(exc)}
