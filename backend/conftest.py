"""Shared test setup for the MediaVault Pro backend.

Two responsibilities:

1. **Import path.** pytest's default "prepend" import mode inserts the directory
   containing the test file (``backend/tests``) onto ``sys.path``, *not* the
   backend root. A bare ``pytest`` run from ``backend/`` would therefore fail on
   ``import app...``. Prepending the backend root here makes ``pytest``,
   ``python -m pytest`` and IDE runners behave identically, which is what the
   ``Makefile`` (``docker-compose run backend pytest``) relies on.

2. **Database isolation.** :func:`database_session_scope` hands out a brand new
   in-memory SQLite database with the full schema applied, so every test starts
   from an empty, isolated state and no test can be affected by another's rows.

   The tests themselves are written as synchronous functions that call
   :func:`run` (``asyncio.run``) around an async scenario. That keeps them working
   under a bare pytest install without depending on an asyncio plugin.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, TypeVar

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models import Base

T = TypeVar("T")

__all__ = ["database_session_scope", "run"]


@asynccontextmanager
async def database_session_scope() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Yield a session factory bound to a fresh in-memory database.

    ``StaticPool`` is required: an in-memory SQLite database lives inside the
    connection, so every pooled connection would otherwise get its own empty,
    private copy of the schema.

    Yields:
        An ``async_sessionmaker`` that produces sessions against the new database.

    The engine is always disposed on exit, so leaving the context never leaves an
    open connection behind (which matters on Windows, where that blocks rmtree of
    a temporary directory).
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


def run(coro: Awaitable[T]) -> T:
    """Run an async scenario to completion from a synchronous test."""
    return asyncio.run(coro)  # type: ignore[arg-type]
