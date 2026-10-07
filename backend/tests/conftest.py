"""Shared pytest fixtures for the backend test suite.

Provides an isolated in-memory database and a temporary media directory per test,
so filesystem and database state never leak between cases and nothing touches the
developer's real ``downloads/`` folder.
"""

from __future__ import annotations

from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base

# Importing the models module registers every table on Base.metadata, which is what
# create_all below reflects on. Without this import the schema would be empty.
import app.models  # noqa: F401  (imported for the metadata side effect)


@pytest.fixture
def anyio_backend() -> str:
    """Backend used by anyio-based async tests."""
    return "asyncio"


@pytest_asyncio.fixture
async def async_client(async_engine) -> AsyncIterator[AsyncClient]:
    """Create an AsyncClient for testing the FastAPI app.

    Overrides ``get_db`` so the app uses the in-memory test database instead of
    ``settings.DATABASE_URL``.
    """
    import app.main as main_module
    from app.db.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.pool import StaticPool

    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app = main_module.app
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def async_engine() -> AsyncIterator:
    """Create an in-memory SQLite engine with the full schema loaded."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncIterator[AsyncSession]:
    """Provide an :class:`AsyncSession` bound to the in-memory database."""
    factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def download_dir(tmp_path) -> Iterator[str]:
    """Point ``settings.DOWNLOAD_DIR`` at a temporary directory for one test.

    Patched on the settings object rather than the environment because every module
    reads ``settings.DOWNLOAD_DIR`` through the shared singleton.
    """
    from app.core.config import settings

    media_root = tmp_path / "downloads"
    media_root.mkdir(parents=True, exist_ok=True)
    original = settings.DOWNLOAD_DIR
    settings.DOWNLOAD_DIR = str(media_root)
    try:
        yield str(media_root)
    finally:
        settings.DOWNLOAD_DIR = original


@pytest.fixture(autouse=True)
def reset_redis_singletons():
    """Drop cached Redis clients before and after every test.

    The application caches a client per process; without this a test that installs a
    fake client could leak it into the next one.
    """
    from app.core import redis_client

    redis_client.reset_redis_clients()
    yield
    redis_client.reset_redis_clients()


@pytest.fixture
def auth_enabled(monkeypatch):
    """Enable authentication for a single test."""
    from app.core.config import settings

    original = settings.AUTH_ENABLED
    settings.AUTH_ENABLED = True
    yield
    settings.AUTH_ENABLED = original


@pytest.fixture
def client(db_session, download_dir, monkeypatch):
    """Provide a synchronous FastAPI client wired to the in-memory test database."""
    import app.main as main_module
    from fastapi.testclient import TestClient

    from app.db.database import get_db

    async def override_get_db():
        yield db_session

    app = main_module.app
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as http_client:
        yield http_client

    app.dependency_overrides.clear()


@pytest.fixture
def fake_redis(monkeypatch):
    """Install an in-memory stand-in for Redis and expose it to the test.

    Implements only the commands the application uses (``set``, ``get``, ``delete``,
    ``exists``, ``publish``, ``pipeline``), which keeps the fakes honest: an
    unexpected Redis call fails loudly instead of silently passing.

    Returns:
        A :class:`FakeRedis` instance. ``.store`` is the backing dict (so
        ``key in fake_redis.store`` works) and ``.published`` is the list of
        ``(channel, message)`` pairs published during the test.
    """
    from app.core import redis_client

    store: dict = {}
    published: list = []

    class FakePipeline:
        def __init__(self, client: "FakeRedis") -> None:
            self._client = client
            self._queued = []

        def set(self, key, value, ex=None):
            self._queued.append(("set", key, value, ex))
            return self

        def publish(self, channel, message):
            self._queued.append(("publish", channel, message))
            return self

        def zadd(self, key, mapping):
            self._queued.append(("zadd", key, mapping))
            return self

        def zremrangebyscore(self, key, min_score, max_score):
            self._queued.append(("zremrangebyscore", key, min_score, max_score))
            return self

        def zcard(self, key):
            self._queued.append(("zcard", key))
            return self

        def zrange(self, key, start, end, withscores=False):
            self._queued.append(("zrange", key, start, end, withscores))
            return self

        def expire(self, key, ttl):
            self._queued.append(("expire", key, ttl))
            return self

        def execute(self):
            results = []
            for command in self._queued:
                op = command[0]
                if op == "set":
                    _op, key, value, ex = command
                    results.append(self._client.set(key, value, ex=ex))
                elif op == "publish":
                    _op, channel, message = command
                    results.append(self._client.publish(channel, message))
                elif op == "zadd":
                    _op, key, mapping = command
                    results.append(self._client.zadd(key, mapping))
                elif op == "zremrangebyscore":
                    _op, key, min_score, max_score = command
                    results.append(self._client.zremrangebyscore(key, min_score, max_score))
                elif op == "zcard":
                    _op, key = command
                    results.append(self._client.zcard(key))
                elif op == "zrange":
                    _op, key, start, end, withscores = command
                    results.append(self._client.zrange(key, start, end, withscores=withscores))
                elif op == "expire":
                    _op, key, ttl = command
                    results.append(self._client.expire(key, ttl))
            self._queued.clear()
            return results

    class FakeRedis:
        """Minimal in-memory Redis double supporting the commands in use."""

        def __init__(self) -> None:
            self.store = store
            self.published = published

        def ping(self) -> bool:
            return True

        def set(self, key, value, ex=None) -> bool:
            store[key] = str(value)
            if ex is not None:
                store[f"__expire__:{key}"] = ex
            return True

        def get(self, key):
            return store.get(key)

        def incr(self, key, amount=1):
            current = int(store.get(key, 0))
            store[key] = str(current + amount)
            return current + amount

        def expire(self, key, ttl):
            store[f"__expire__:{key}"] = ttl
            return True

        def zadd(self, key, mapping):
            if key not in store or not isinstance(store[key], dict):
                store[key] = {}
            store[key].update(mapping)
            return len(mapping)

        def zremrangebyscore(self, key, min_score, max_score):
            if key in store and isinstance(store[key], dict):
                to_remove = [m for m, s in store[key].items() if min_score <= s <= max_score]
                for m in to_remove:
                    del store[key][m]
                return len(to_remove)
            return 0

        def zcard(self, key):
            if key in store and isinstance(store[key], dict):
                return len(store[key])
            return 0

        def zrange(self, key, start, end, withscores=False):
            if key not in store or not isinstance(store[key], dict):
                if withscores:
                    return []
                return []
            items = sorted(store[key].items(), key=lambda x: x[1])
            if end == -1:
                end = len(items) - 1
            sliced = items[start:end + 1]
            if withscores:
                return [(m, float(s)) for m, s in sliced]
            return [m for m, _ in sliced]

        def delete(self, *keys) -> int:
            removed = 0
            for key in keys:
                if store.pop(key, None) is not None:
                    removed += 1
            return removed

        def exists(self, *keys) -> int:
            return sum(1 for key in keys if key in store)

        def publish(self, channel, message) -> int:
            published.append((channel, message))
            return 1

        def pipeline(self, transaction: bool = True) -> FakePipeline:
            return FakePipeline(self)

        def close(self) -> None:
            return None

    fake = FakeRedis()
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake