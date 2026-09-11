"""asyncpg connection pool for Heroku Postgres with native RLS support."""

import asyncpg
from app.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # Heroku Postgres uses self-signed SSL — require SSL but don't verify cert
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=settings.DATABASE_POOL_MIN,
            max_size=settings.DATABASE_POOL_MAX,
            ssl="require",
            command_timeout=30,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def set_rls_user(conn: asyncpg.Connection, user_id: str) -> None:
    """Set the session variable used by native Postgres RLS policies.

    All RLS policies filter on current_setting('app.user_id', true).
    This must be called on every connection before any query that touches
    user-scoped tables.
    """
    await conn.execute(
        "SELECT set_config('app.user_id', $1, true)", user_id
    )
