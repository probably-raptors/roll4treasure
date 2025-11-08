from __future__ import annotations

import logging

import psycopg

from app.core.config import settings

logger = logging.getLogger("app.db.pool")

# Try to use psycopg-pool if available; otherwise allow fallback checks
try:  # psycopg-pool is a separate package
    from psycopg_pool import AsyncConnectionPool  # type: ignore
except Exception:  # pragma: no cover - optional dep
    AsyncConnectionPool = None  # type: ignore[misc,assignment]

_pool: AsyncConnectionPool | None = None  # type: ignore[name-defined]


async def init_pool() -> None:
    """
    Initialize a global async connection pool from central settings.
    Skips pooling (without crashing) if DATABASE_URL missing or psycopg-pool unavailable.
    """
    global _pool
    if _pool is not None:
        return

    dsn = settings.DATABASE_URL
    if not dsn:
        logger.warning("DATABASE_URL not set; DB pool not initialized")
        return

    if AsyncConnectionPool is None:
        logger.warning("psycopg-pool not installed; skipping pool initialization")
        return

    _pool = AsyncConnectionPool(
        dsn,
        min_size=settings.DB_MIN_SIZE,
        max_size=settings.DB_MAX_SIZE,
        timeout=settings.DB_CONNECT_TIMEOUT,  # connect timeout
    )
    await _pool.open()
    logger.info(
        "DB pool initialized (min=%s, max=%s, timeout=%ss)",
        settings.DB_MIN_SIZE,
        settings.DB_MAX_SIZE,
        settings.DB_CONNECT_TIMEOUT,
    )


def get_pool() -> AsyncConnectionPool | None:  # type: ignore[name-defined]
    """Return the pool if initialized (or None)."""
    return _pool


async def check_ready() -> bool:
    """
    True if we can get a connection.
    - With pool: try pool.connection()
    - Without pool: try a one-off async connection (best-effort) using settings
    """
    dsn = settings.DATABASE_URL

    if _pool is not None:
        try:
            async with _pool.connection() as _:
                return True
        except Exception:
            return False

    if dsn:
        try:
            async with await psycopg.AsyncConnection.connect(
                dsn=dsn, connect_timeout=settings.DB_CONNECT_TIMEOUT
            ):
                return True
        except Exception:
            return False

    return False


async def close_pool() -> None:
    """Close the pool if it exists."""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        finally:
            _pool = None
            logger.info("DB pool closed")
