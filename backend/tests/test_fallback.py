"""Tests for Phase 6A fallback extraction, provider registry, and endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import redis_client
from app.core.config import settings
from app.models.download import Download, DownloadStatus
from app.models.extraction_attempt import ExtractionAttempt, ProviderName
from app.schemas.settings import ProcessingSettings
from app.services.extractor.api_providers import ProviderRegistry, ProviderStatus
from app.services.extractor.fallback_engine import ExtractResult, FallbackExtractor
from app.workers.monitor_tasks import system_monitor_task


# --------------------------------------------------------------------------- #
# Provider registry
# --------------------------------------------------------------------------- #


@pytest.fixture
def registry():
    return ProviderRegistry()


def test_list_providers_returns_all(registry):
    providers = registry.list_providers()
    assert len(providers) == 3
    names = [p.name for p in providers]
    assert "scraperapi" in names
    assert "zenrows" in names
    assert "rapidapi" in names


def test_can_use_disabled_when_fallback_off(monkeypatch):
    monkeypatch.setattr(settings, "FALLBACK_ENABLED", False)
    registry = ProviderRegistry()
    assert registry.can_use("scraperapi") is False
    assert registry.can_use("rapidapi") is False


def test_can_use_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "SCRAPER_API_KEY", "")
    monkeypatch.setattr(settings, "SCRAPER_PROVIDER", "scraperapi")
    registry = ProviderRegistry()
    assert registry.can_use("scraperapi") is False


def test_record_usage_increments_redis(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(redis_client, "get_redis", lambda: MagicMock(
        incr=lambda key: store.__setitem__(key, store.get(key, 0) + 1) or store[key],
        get=lambda key: str(store.get(key, 0)).encode(),
    ))
    registry = ProviderRegistry()
    registry.record_usage("scraperapi")
    assert "api_usage:scraperapi:2026-10" in store or "api_usage:scraperapi:" in str(store)


# --------------------------------------------------------------------------- #
# Fallback extractor
# --------------------------------------------------------------------------- #


@pytest.fixture
def fallback(monkeypatch):
    registry = MagicMock()
    registry.can_use.return_value = True
    registry.record_usage.return_value = None
    monkeypatch.setattr("app.services.extractor.fallback_engine.ProviderRegistry", lambda: registry)
    return FallbackExtractor(), registry


@pytest.mark.asyncio
async def test_fallback_returns_direct_on_success(fallback, monkeypatch):
    engine, registry = fallback
    monkeypatch.setattr(engine, "_try_direct", AsyncMock(return_value={"provider": "direct", "success": True, "metadata": {"title": "T"}}))
    monkeypatch.setattr(engine, "_try_proxy", AsyncMock(return_value={"provider": "scraperapi", "success": False}))
    monkeypatch.setattr(engine, "_try_rapidapi", AsyncMock(return_value={"provider": "rapidapi", "success": False}))

    result = await engine.extract_with_fallback("https://example.com/video")
    assert result.degraded is False
    assert result.metadata["title"] == "T"


@pytest.mark.asyncio
async def test_fallback_uses_proxy_when_direct_fails(fallback, monkeypatch):
    engine, registry = fallback
    monkeypatch.setattr(engine, "_try_direct", AsyncMock(return_value={"provider": "direct", "success": False}))
    monkeypatch.setattr(engine, "_try_proxy", AsyncMock(return_value={"provider": "scraperapi", "success": True, "metadata": {"title": "Proxy"}}))
    monkeypatch.setattr(engine, "_try_rapidapi", AsyncMock(return_value={"provider": "rapidapi", "success": False}))

    result = await engine.extract_with_fallback("https://example.com/video")
    assert result.degraded is True
    assert result.metadata["title"] == "Proxy"
    registry.record_usage.assert_called_once_with("scraperapi")


@pytest.mark.asyncio
async def test_fallback_raises_when_all_fail(fallback, monkeypatch):
    engine, registry = fallback
    monkeypatch.setattr(engine, "_try_direct", AsyncMock(return_value={"provider": "direct", "success": False, "error": "403"}))
    monkeypatch.setattr(engine, "_try_proxy", AsyncMock(return_value={"provider": "scraperapi", "success": False, "error": "403"}))
    monkeypatch.setattr(engine, "_try_rapidapi", AsyncMock(return_value={"provider": "rapidapi", "success": False, "error": "403"}))

    with pytest.raises(ValueError, match="All extraction attempts failed"):
        await engine.extract_with_fallback("https://example.com/video")


# --------------------------------------------------------------------------- #
# Settings endpoints
# --------------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def client(db_session, download_dir, monkeypatch):
    import app.main as main_module
    from app.db.database import get_db

    async def override_get_db():
        yield db_session

    monkeypatch.setattr(settings, "DATA_DIR", str(download_dir))
    app = main_module.app
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_settings_include_fallback_fields(client):
    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert "scraper_api_key" in body
    assert "scraper_provider" in body
    assert "rapid_api_key" in body
    assert "provider_monthly_limit" in body
    assert "fallback_enabled" in body


@pytest.mark.asyncio
async def test_settings_update_fallback_fields(client):
    response = await client.put("/api/v1/settings", json={
        "scraper_api_key": "test_key",
        "scraper_provider": "zenrows",
        "rapid_api_key": "rapid_key",
        "provider_monthly_limit": 500,
        "fallback_enabled": False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["scraper_api_key"] == "test_key"
    assert body["scraper_provider"] == "zenrows"
    assert body["rapid_api_key"] == "rapid_key"
    assert body["provider_monthly_limit"] == 500
    assert body["fallback_enabled"] is False


# --------------------------------------------------------------------------- #
# Providers endpoint
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_providers_status_returns_providers_and_attempts(client, db_session):
    attempt = ExtractionAttempt(
        url="https://example.com/video",
        provider="direct",
        success=True,
        latency_ms=100,
    )
    db_session.add(attempt)
    await db_session.commit()

    response = await client.get("/api/v1/providers/status")
    assert response.status_code == 200
    body = response.json()
    assert "providers" in body
    assert "recent_attempts" in body
    assert len(body["providers"]) == 3
    assert len(body["recent_attempts"]) >= 1
