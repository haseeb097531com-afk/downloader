"""Fallback extraction engine with API provider support."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import httpx

from app.core import redis_client
from app.core.config import settings
from app.models.extraction_attempt import ProviderName
from app.services.extractor.api_providers import ProviderRegistry
from app.services.extractor.ytdlp_engine import YTDLPEngine, YTDLPEngineError

logger = logging.getLogger(__name__)


@dataclass
class ExtractResult:
    metadata: Dict[str, Any]
    metadata_only: bool = False
    degraded: bool = False
    attempts: Optional[List[Dict[str, Any]]] = None


class FallbackExtractor:
    """Try direct extraction first, then fall back to proxy APIs."""

    def __init__(self, registry: Optional[ProviderRegistry] = None) -> None:
        self.registry = registry or ProviderRegistry()
        self.engine = YTDLPEngine()

    async def extract_with_fallback(self, url: str) -> ExtractResult:
        """Extract metadata, trying direct first then proxy APIs."""
        attempts: List[Dict[str, Any]] = []

        # Attempt 1: direct yt-dlp extraction
        direct = await self._try_direct(url)
        attempts.append(direct)
        if direct["success"]:
            return ExtractResult(
                metadata=direct["metadata"],
                degraded=False,
                attempts=attempts,
            )

        # Attempt 2: proxy scraper
        proxy = await self._try_proxy(url)
        attempts.append(proxy)
        if proxy["success"]:
            return ExtractResult(
                metadata=proxy["metadata"],
                degraded=True,
                attempts=attempts,
            )

        # Attempt 3: RapidAPI metadata-only
        rapid = await self._try_rapidapi(url)
        attempts.append(rapid)
        if rapid["success"]:
            return ExtractResult(
                metadata=rapid["metadata"],
                metadata_only=True,
                degraded=True,
                attempts=attempts,
            )

        raise ValueError(
            f"All extraction attempts failed for {url}: " +
            "; ".join(f"{a['provider']}: {a.get('error', 'unknown')}" for a in attempts)
        )

    async def _try_direct(self, url: str) -> Dict[str, Any]:
        provider = ProviderName.DIRECT.value
        start = time.monotonic()
        try:
            metadata = await asyncio.to_thread(self.engine.extract_info, url, False)
            await self._log_attempt(url, provider, True, None, start)
            return {"provider": provider, "success": True, "metadata": metadata}
        except YTDLPEngineError as exc:
            await self._log_attempt(url, provider, False, str(exc), start)
            return {"provider": provider, "success": False, "error": str(exc)}
        except Exception as exc:
            await self._log_attempt(url, provider, False, str(exc), start)
            return {"provider": provider, "success": False, "error": str(exc)}

    async def _try_proxy(self, url: str) -> Dict[str, Any]:
        provider = settings.SCRAPER_PROVIDER
        if not self.registry.can_use(provider):
            return {"provider": provider, "success": False, "error": "provider not available"}

        start = time.monotonic()
        try:
            html = await self._fetch_via_proxy(url, provider)
            metadata = await self._parse_proxy_html(url, html, provider)
            self.registry.record_usage(provider)
            await self._log_attempt(url, provider, True, None, start)
            return {"provider": provider, "success": True, "metadata": metadata}
        except Exception as exc:
            await self._log_attempt(url, provider, False, str(exc), start)
            return {"provider": provider, "success": False, "error": str(exc)}

    async def _try_rapidapi(self, url: str) -> Dict[str, Any]:
        provider = ProviderName.RAPIDAPI.value
        if not self.registry.can_use(provider):
            return {"provider": provider, "success": False, "error": "provider not available"}

        start = time.monotonic()
        try:
            metadata = await self._fetch_rapidapi_metadata(url)
            self.registry.record_usage(provider)
            await self._log_attempt(url, provider, True, None, start)
            return {"provider": provider, "success": True, "metadata": metadata, "metadata_only": True}
        except Exception as exc:
            await self._log_attempt(url, provider, False, str(exc), start)
            return {"provider": provider, "success": False, "error": str(exc)}

    async def _fetch_via_proxy(self, url: str, provider: str) -> str:
        """Fetch page HTML through a proxy scraper API."""
        api_key = settings.SCRAPER_API_KEY
        if provider == "scraperapi":
            proxy_url = f"https://api.scraperapi.com/?api_key={api_key}&url={url}"
        elif provider == "zenrows":
            proxy_url = f"https://api.zenrows.com/v1/?apikey={api_key}&url={url}"
        else:
            raise ValueError(f"Unknown proxy provider: {provider}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(proxy_url)
            response.raise_for_status()
            return response.text

    async def _parse_proxy_html(self, url: str, html: str, provider: str) -> Dict[str, Any]:
        """Parse proxy HTML with yt-dlp process_ie_key or basic metadata extraction."""
        try:
            options = self.engine.base_options.copy()
            options["quiet"] = True
            options["no_warnings"] = True
            import yt_dlp
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False, ie_key="Generic")
                if info:
                    return self._normalize_metadata(info)
        except Exception as exc:
            logger.debug("yt-dlp Generic extraction failed for proxy HTML: %s", exc)

        return {
            "title": self._extract_title(html),
            "description": self._extract_meta(html, "description"),
            "thumbnail": self._extract_meta(html, "image"),
            "uploader": None,
            "upload_date": None,
            "platform": url.split("/")[2] if len(url.split("/")) > 2 else "unknown",
            "extractor": "proxy",
        }

    async def _fetch_rapidapi_metadata(self, url: str) -> Dict[str, Any]:
        """Fetch basic metadata from a RapidAPI social media endpoint."""
        api_key = settings.RAPID_API_KEY
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "social-media-meta.p.rapidapi.com",
        }
        params = {"url": url}

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://social-media-meta.p.rapidapi.com/",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        return {
            "title": data.get("title") or data.get("description", "")[:200],
            "description": data.get("description"),
            "thumbnail": data.get("thumbnail") or data.get("image"),
            "uploader": data.get("author") or data.get("uploader"),
            "upload_date": data.get("upload_date"),
            "platform": data.get("platform", "unknown"),
            "extractor": "rapidapi",
        }

    def _normalize_metadata(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize yt-dlp info dict into our metadata schema."""
        return {
            "title": info.get("title", "Unknown Title"),
            "description": info.get("description"),
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
            "upload_date": info.get("upload_date"),
            "duration": info.get("duration"),
            "platform": info.get("extractor", "unknown"),
            "extractor": info.get("extractor", "unknown"),
            "formats": info.get("formats", []),
            "raw_data": info,
        }

    @staticmethod
    def _extract_title(html: str) -> str:
        import re
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()[:500]
        return "Unknown Title"

    @staticmethod
    def _extract_meta(html: str, name: str) -> Optional[str]:
        import re
        pattern = rf'<meta[^>]+(?:name|property)=["\'](?:og:)?{name}["\'][^>]+content=["\']([^"\']+)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    async def _log_attempt(
        self,
        url: str,
        provider: str,
        success: bool,
        error_message: Optional[str],
        start: float,
    ) -> None:
        from sqlalchemy import insert
        from app.db.database import AsyncSessionLocal

        latency = int((time.monotonic() - start) * 1000)
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    insert(ExtractionAttempt).values(
                        url=url,
                        provider=provider,
                        success=success,
                        error_message=error_message,
                        latency_ms=latency,
                    )
                )
                await db.commit()
        except Exception as exc:
            logger.warning("Failed to log extraction attempt: %s", exc)
