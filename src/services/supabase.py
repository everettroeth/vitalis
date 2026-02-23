"""Supabase client with RLS context.

Every request gets a connection where ``app.current_user_id`` and
``app.current_account_id`` are set via ``SET LOCAL``, ensuring that
Postgres Row-Level Security policies see the correct identity.

Uses ``asyncpg`` for direct database access with RLS context — the
Supabase Python client doesn't support SET LOCAL session variables.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import asyncpg

from src.config import Settings, get_settings

logger = logging.getLogger("vitalis.db")

# Module-level connection pool — initialized once at app startup
_pool: asyncpg.Pool | None = None


async def init_pool(settings: Settings | None = None) -> asyncpg.Pool:
    """Create the asyncpg connection pool. Call once at app startup."""
    global _pool
    s = settings or get_settings()
    _pool = await asyncpg.create_pool(
        s.supabase_db_url,
        min_size=2,
        max_size=20,
        command_timeout=30,
    )
    logger.info("Database pool initialized (min=2, max=20)")
    return _pool


async def close_pool() -> None:
    """Drain the pool. Call at app shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized — call init_pool() first")
    return _pool


@asynccontextmanager
async def get_connection(
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    request_id: uuid.UUID | None = None,
    audit_skip: bool = False,
) -> AsyncGenerator[asyncpg.Connection, None]:
    """Acquire a connection with RLS session variables set.

    Usage::

        async with get_connection(user_id=ctx.vitalis_user_id) as conn:
            rows = await conn.fetch("SELECT * FROM wearable_daily WHERE date = $1", today)

    The ``SET LOCAL`` calls are scoped to the current transaction so they
    disappear automatically when the connection is returned to the pool.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if user_id:
                await conn.execute(
                    "SET LOCAL app.current_user_id = $1", str(user_id)
                )
            if account_id:
                await conn.execute(
                    "SET LOCAL app.current_account_id = $1", str(account_id)
                )
            if request_id:
                await conn.execute(
                    "SET LOCAL app.request_id = $1", str(request_id)
                )
            if audit_skip:
                await conn.execute("SET LOCAL app.audit_skip = '1'")

            yield conn


async def execute(
    query: str,
    *args: Any,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> str:
    """Execute a single statement with RLS context and return status."""
    async with get_connection(user_id=user_id, account_id=account_id) as conn:
        return await conn.execute(query, *args)


async def fetch(
    query: str,
    *args: Any,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> list[asyncpg.Record]:
    """Fetch rows with RLS context."""
    async with get_connection(user_id=user_id, account_id=account_id) as conn:
        return await conn.fetch(query, *args)


async def fetchrow(
    query: str,
    *args: Any,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> asyncpg.Record | None:
    """Fetch a single row with RLS context."""
    async with get_connection(user_id=user_id, account_id=account_id) as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(
    query: str,
    *args: Any,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> Any:
    """Fetch a single value with RLS context."""
    async with get_connection(user_id=user_id, account_id=account_id) as conn:
        return await conn.fetchval(query, *args)
