"""Redis-backed sliding-window rate limiter for Phase 17A."""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import HTTPException, status
from starlette.requests import Request
from starlette.responses import Response

from app.core import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)

__all__ = ["RateLimiter", "rate_limit", "RateLimitExceeded"]


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")
        self.retry_after = retry_after


class RateLimiter:
    """Sliding-window rate limiter backed by Redis."""

    def __init__(self, requests: int, window_seconds: int) -> None:
        self.requests = requests
        self.window_seconds = window_seconds

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check whether a request is allowed under the rate limit.

        Args:
            key: Redis key for this rate limit bucket.

        Returns:
            Tuple of (allowed, retry_after_seconds). When allowed is False,
            retry_after is the number of seconds until the next request is
            permitted.
        """
        client = redis_client.get_redis()
        now = time.time()
        window_start = now - self.window_seconds

        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window_seconds)
        results = pipe.execute()

        count = results[2]
        if count > self.requests:
            # Find the oldest entry to calculate retry-after.
            oldest = client.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1] + self.window_seconds - now) + 1
            else:
                retry_after = self.window_seconds
            return False, max(retry_after, 1)

        return True, 0


def rate_limit(requests: int, window_seconds: int, key_builder: Optional[callable] = None):
    """FastAPI dependency that applies rate limiting.

    Args:
        requests: Maximum number of requests allowed in the window.
        window_seconds: Duration of the sliding window in seconds.
        key_builder: Optional callable that receives the Request and returns
            the Redis key to use. Defaults to ``ratelimit:{ip}:{path}``.

    Returns:
        A FastAPI dependency function.

    Raises:
        HTTPException 429: When the rate limit is exceeded.
    """
    limiter = RateLimiter(requests, window_seconds)

    async def _dependency(request: Request) -> None:
        if key_builder:
            key = key_builder(request)
        else:
            client_ip = request.client.host if request.client else "unknown"
            key = f"ratelimit:{client_ip}:{request.url.path}"

        allowed, retry_after = limiter.is_allowed(key)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

    return _dependency


# ------------------------------------------------------------------ #
# Middleware
# ------------------------------------------------------------------ #

class RateLimitMiddleware:
    """Global rate-limiting middleware for all requests.

    Applies a per-IP sliding window with ``settings.GLOBAL_RATE_LIMIT``
    requests per 60 seconds (default 120).
    """

    def __init__(self, app) -> None:
        self.app = app
        self.limiter = RateLimiter(
            requests=getattr(settings, "GLOBAL_RATE_LIMIT", 120),
            window_seconds=60,
        )

    async def __call__(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:global:{client_ip}"
        allowed, retry_after = self.limiter.is_allowed(key)

        if not allowed:
            return Response(
                content='{"detail":"Too many requests. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        return response
