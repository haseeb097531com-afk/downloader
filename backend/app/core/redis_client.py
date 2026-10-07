"""Redis access helpers shared by the API, the queue orchestrator and the workers.

This module owns the single Redis key convention used across MediaVault Pro so the
API process and the Celery workers never disagree on where a pause flag or a
progress snapshot lives.

Key layout (all prefixed with ``settings.REDIS_KEY_PREFIX``)::

    mediavault:pause:{download_id}          -> "1"        pause request for a task
    mediavault:progress:{download_id}        -> JSON hash  latest progress snapshot
    mediavault:progress:channel:{download_id} -> pubsub    live progress channel
    mediavault:progress:channel:all           -> pubsub    fan-out channel
    mediavault:pause_all                      -> "1"       global pause switch

Two client flavours are exposed on purpose:

* :func:`get_redis` - synchronous client for Celery tasks and other blocking code.
* :func:`get_async_redis` - asyncio client for FastAPI request handlers and the
  WebSocket progress endpoint.

Both are lazily created singletons keyed off ``settings.REDIS_URL`` so importing
this module never opens a socket (important for the test suite, which patches the
factories instead).
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

import redis
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "RedisUnavailable",
    "get_redis",
    "get_async_redis",
    "close_redis",
    "close_async_redis",
    "reset_redis_clients",
    "pause_key",
    "progress_key",
    "progress_channel",
    "progress_channel_all",
    "pause_all_key",
    "throttle_key",
    "is_paused",
    "request_pause",
    "clear_pause",
    "set_pause_all",
    "clear_pause_all",
    "is_pause_all_active",
    "set_throttle",
    "clear_throttle",
    "is_throttled",
    "write_progress",
    "read_progress",
    "publish_progress",
    "listen_progress",
]

# Clients are cached at module level so connection pools are shared across requests.
_sync_client: Optional[redis.Redis] = None
_async_client: Optional[aioredis.Redis] = None


class RedisUnavailable(RuntimeError):
    """Raised when a Redis backed feature is used while Redis is unreachable.

    Callers that can degrade gracefully (the queue snapshot, for example) catch
    this and fall back to the database; callers that cannot (the pause flag on a
    live download) let it bubble up so the user sees an explicit failure instead
    of a download that silently ignores their pause request.
    """


# --------------------------------------------------------------------------- #
# Client factories
# --------------------------------------------------------------------------- #
def get_redis() -> redis.Redis:
    """Return the process-wide synchronous Redis client, creating it on demand.

    Returns:
        A ``redis.Redis`` bound to ``settings.REDIS_URL`` with string decoding
        enabled so values round-trip as ``str`` instead of ``bytes``.

    Raises:
        RedisUnavailable: If a connection attempt fails.  Probing with ``PING``
            keeps the failure mode explicit instead of deferring it to the first
            real command, which would otherwise fail mid-transaction.
    """
    global _sync_client
    if _sync_client is None:
        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            client.ping()
        except Exception as exc:  # pragma: no cover - depends on deployment
            logger.warning("Redis unavailable at %s: %s", settings.REDIS_URL, exc)
            raise RedisUnavailable(f"Redis is unavailable: {exc}") from exc
        _sync_client = client
    return _sync_client


def get_async_redis() -> aioredis.Redis:
    """Return the process-wide asyncio Redis client, creating it on demand.

    No connection is opened eagerly - redis-py connects lazily, so this is safe to
    call at import time from request handlers.
    """
    global _async_client
    if _async_client is None:
        _async_client = aioredis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _async_client


async def close_redis() -> None:
    """Close and forget the synchronous client, if one was created."""
    global _sync_client
    if _sync_client is not None:
        try:
            _sync_client.close()
        finally:
            _sync_client = None


async def close_async_redis() -> None:
    """Close and forget the asyncio client, if one was created."""
    global _async_client
    if _async_client is not None:
        try:
            await _async_client.aclose()
        finally:
            _async_client = None


def reset_redis_clients() -> None:
    """Drop cached clients without connecting or closing.

    Used by the test suite between cases so each test can install its own fake.
    """
    global _sync_client, _async_client
    _sync_client = None
    _async_client = None


# --------------------------------------------------------------------------- #
# Key helpers
# --------------------------------------------------------------------------- #
def _prefixed(suffix: str) -> str:
    return f"{settings.REDIS_KEY_PREFIX}:{suffix}"


def pause_key(download_id: str) -> str:
    """Return the pause flag key for ``download_id``."""
    return _prefixed(f"pause:{download_id}")


def pause_all_key() -> str:
    """Return the global pause switch key used by ``POST /queue/pause-all``."""
    return _prefixed("pause_all")


def progress_key(download_id: str) -> str:
    """Return the durable progress snapshot key for ``download_id``."""
    return _prefixed(f"progress:{download_id}")


def progress_channel(download_id: str) -> str:
    """Return the pub/sub channel carrying live progress for ``download_id``."""
    return _prefixed(f"progress:channel:{download_id}")


def progress_channel_all() -> str:
    """Return the fan-out channel carrying live progress for every download."""
    return _prefixed("progress:channel:all")


# --------------------------------------------------------------------------- #
# Pause / resume flags
# --------------------------------------------------------------------------- #
def is_paused(download_id: str, client: Optional[redis.Redis] = None) -> bool:
    """Return whether a pause has been requested for ``download_id``.

    This is called from the yt-dlp progress hook on every chunk, so it degrades to
    ``False`` when Redis is down: a Redis outage must not abort in-flight
    downloads, and the database status remains the source of truth for the UI.
    """
    try:
        redis_client = client or get_redis()
        return bool(redis_client.exists(pause_key(download_id)))
    except RedisUnavailable:
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed reading pause flag for %s: %s", download_id, exc)
        return False


def request_pause(download_id: str, client: Optional[redis.Redis] = None) -> bool:
    """Set the pause flag for ``download_id`` so the worker suspends at the next chunk.

    Returns:
        ``True`` if the flag was written, ``False`` if Redis was unreachable.

    The flag carries a TTL as a safety net: if a worker dies while paused the flag
    expires and a later retry of the same download is not stuck forever.
    """
    try:
        redis_client = client or get_redis()
        redis_client.set(pause_key(download_id), "1", ex=settings.REDIS_PAUSE_FLAG_TTL)
        return True
    except RedisUnavailable as exc:
        logger.warning("Cannot set pause flag for %s: %s", download_id, exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Cannot set pause flag for %s: %s", download_id, exc)
        return False


def clear_pause(download_id: str, client: Optional[redis.Redis] = None) -> bool:
    """Remove the pause flag for ``download_id`` (used when resuming or finishing)."""
    try:
        redis_client = client or get_redis()
        redis_client.delete(pause_key(download_id))
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Cannot clear pause flag for %s: %s", download_id, exc)
        return False


def set_pause_all(client: Optional[redis.Redis] = None) -> bool:
    """Raise the global pause switch honoured by :func:`is_paused` semantics."""
    try:
        redis_client = client or get_redis()
        redis_client.set(pause_all_key(), "1")
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Cannot set pause_all flag: %s", exc)
        return False


def clear_pause_all(client: Optional[redis.Redis] = None) -> bool:
    """Lower the global pause switch."""
    try:
        redis_client = client or get_redis()
        redis_client.delete(pause_all_key())
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Cannot clear pause_all flag: %s", exc)
        return False


def is_pause_all_active(client: Optional[redis.Redis] = None) -> bool:
    """Return whether the global pause switch is currently raised."""
    try:
        redis_client = client or get_redis()
        return bool(redis_client.exists(pause_all_key()))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Cannot read pause_all flag: %s", exc)
        return False


def throttle_key() -> str:
    return _prefixed("system_throttle")


def set_throttle(client: Optional[redis.Redis] = None) -> bool:
    try:
        redis_client = client or get_redis()
        redis_client.set(throttle_key(), "1")
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Cannot set throttle flag: %s", exc)
        return False


def clear_throttle(client: Optional[redis.Redis] = None) -> bool:
    try:
        redis_client = client or get_redis()
        redis_client.delete(throttle_key())
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Cannot clear throttle flag: %s", exc)
        return False


def is_throttled(client: Optional[redis.Redis] = None) -> bool:
    try:
        redis_client = client or get_redis()
        return bool(redis_client.exists(throttle_key()))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Cannot read throttle flag: %s", exc)
        return False


# --------------------------------------------------------------------------- #
# Progress snapshots
# --------------------------------------------------------------------------- #
def write_progress(
    download_id: str,
    payload: Dict[str, Any],
    client: Optional[redis.Redis] = None,
) -> None:
    """Persist and broadcast the latest progress snapshot for ``download_id``.

    The value is stored under :func:`progress_key` so the queue snapshot can show
    live speed/eta for a download whose worker is not in the API process, and
    published on both :func:`progress_channel` and :func:`progress_channel_all`
    so WebSocket clients can subscribe to one download or to everything.

    Progress is presentation-only, so Redis failures are logged and swallowed -
    the download must not die because progress could not be reported.
    """
    try:
        redis_client = client or get_redis()
    except RedisUnavailable:
        return

    enriched = {"download_id": download_id, **payload}
    body = json.dumps(enriched, default=str)

    try:
        pipe = redis_client.pipeline()
        pipe.set(progress_key(download_id), body, ex=settings.REDIS_PROGRESS_TTL)
        pipe.publish(progress_channel(download_id), body)
        pipe.publish(progress_channel_all(), body)
        pipe.execute()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed publishing progress for %s: %s", download_id, exc)


def read_progress(download_id: str, client: Optional[redis.Redis] = None) -> Optional[Dict[str, Any]]:
    """Return the last persisted progress snapshot, or ``None`` when unavailable."""
    try:
        redis_client = client or get_redis()
        raw = redis_client.get(progress_key(download_id))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed reading progress for %s: %s", download_id, exc)
        return None

    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Corrupt progress snapshot for %s, ignoring", download_id)
        return None


async def publish_progress(download_id: str, payload: Dict[str, Any]) -> None:
    """Asynchronously persist and broadcast a progress snapshot.

    Used by the async API paths; falls back to logging on failure.
    """
    try:
        client = get_async_redis()
        enriched = {"download_id": download_id, **payload}
        body = json.dumps(enriched, default=str)
        pipe = client.pipeline()
        pipe.set(progress_key(download_id), body, ex=settings.REDIS_PROGRESS_TTL)
        pipe.publish(progress_channel(download_id), body)
        pipe.publish(progress_channel_all(), body)
        await pipe.execute()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed publishing progress for %s: %s", download_id, exc)


async def listen_progress(
    download_id: Optional[str] = None,
    stop: Optional[Any] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Yield progress snapshots from Redis pub/sub until ``stop`` is set.

    Args:
        download_id: Subscribe to a single download, or ``None`` to subscribe to
            the fan-out channel and receive every download's progress.
        stop: Optional ``asyncio.Event`` used to break out of the loop cleanly when
            the WebSocket client disconnects.

    Yields:
        Decoded progress payloads. Malformed messages are skipped rather than
        killing the stream.
    """
    client = get_async_redis()
    pubsub = client.pubsub()
    channel = progress_channel(download_id) if download_id else progress_channel_all()
    await pubsub.subscribe(channel)
    try:
        while stop is None or not stop.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                if stop is not None and stop.is_set():
                    break
                continue
            try:
                yield json.loads(message["data"])
            except (TypeError, ValueError, KeyError):
                logger.warning("Dropping malformed progress message on %s", channel)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error closing pubsub for %s: %s", channel, exc)