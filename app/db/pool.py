from __future__ import annotations

import logging
import os

import psycopg

logger = logging.getLogger("app.db.pool")

# Try to use psycopg-pool if available; otherwise we still allow /readyz to work
try:  # psycopg-pool is a separate package
    from psycopg_pool import AsyncConnectionPool  # type: ignore
except Exception:  # pragma: no cover - optional dep
    AsyncConnectionPool = None  # type: ignore[misc,assignment]

_pool: AsyncConnectionPool | None = None  # type: ignore[name-defined]


async def init_pool() -> None:
    """
    Initialize a global async connection pool.
    - DSN comes from DATABASE_URL.
    - If psycopg-pool isn't installed or DSN missing, we skip pooling (readyz will degrade).
    """
    global _pool
    if _pool is not None:
        return

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.warning("DATABASE_URL not set; DB pool not initialized")
        return

    # If pool package isn't present, log and don't crash.
    if AsyncConnectionPool is None:
        logger.warning("psycopg-pool not installed; skipping pool initialization")
        return

    # Sane defaults; adjust later if needed via env vars
    min_size = int(os.environ.get("DB_MIN_SIZE", "1"))
    max_size = int(os.environ.get("DB_MAX_SIZE", "5"))
    connect_timeout = float(os.environ.get("DB_CONNECT_TIMEOUT", "5"))

    _pool = AsyncConnectionPool(
        dsn,
        min_size=min_size,
        max_size=max_size,
        timeout=connect_timeout,  # connect timeout
    )
    # Explicitly open the pool once, so failures are logged at startup
    await _pool.open()
    logger.info(
        "DB pool initialized (min=%s, max=%s, timeout=%ss)", min_size, max_size, connect_timeout
    )


def get_pool() -> AsyncConnectionPool | None:  # type: ignore[name-defined]
    """Return the pool if initialized (or None)."""
    return _pool


async def check_ready() -> bool:
    """
    True if we can get a connection.
    - With pool: try pool.connection().
    - Without pool (or missing package): try a one-off AsyncConnection (best-effort).
    """
    dsn = os.environ.get("DATABASE_URL")

    # If we have a pool, prefer that.
    if _pool is not None:
        try:
            async with _pool.connection() as _:
                return True
        except Exception:
            return False

    # No pool? Try a direct async connection if we have a DSN.
    if dsn:
        try:
            async with await psycopg.AsyncConnection.connect(
                dsn=dsn, connect_timeout=float(os.environ.get("DB_CONNECT_TIMEOUT", "5"))
            ):
                return True
        except Exception:
            return False

    # No DSN at all.
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
