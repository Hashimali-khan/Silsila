import asyncio
import logging
import asyncpg
from app.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                # Heroku Postgres uses self-signed SSL — require SSL but don't verify cert
                _pool = await asyncpg.create_pool(
                    dsn=settings.DATABASE_URL,
                    min_size=settings.DATABASE_POOL_MIN,
                    max_size=settings.DATABASE_POOL_MAX,
                    ssl="require",
                    command_timeout=30,
                )
                break
            except Exception as e:
                logger.warning(
                    "Database connection attempt %d/%d failed: %s",
                    attempt,
                    max_retries,
                    e,
                )
                if attempt == max_retries:
                    raise
                await asyncio.sleep(2)
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
