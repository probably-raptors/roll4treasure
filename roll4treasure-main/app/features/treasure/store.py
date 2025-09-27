# app/features/treasure/store.py
from __future__ import annotations
from typing import Optional, Callable, Awaitable, Any
import os, json, asyncio, logging
import psycopg
from psycopg_pool import AsyncConnectionPool
from psycopg.types.json import Json

from app.features.treasure.models import Session

log = logging.getLogger("r4t.store")

_pool: Optional[AsyncConnectionPool] = None

def _as_dict(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, (bytes, bytearray, memoryview)):
        val = bytes(val).decode("utf-8", "strict")
    if isinstance(val, str):
        return json.loads(val)
    return json.loads(json.dumps(val))

def _dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    return dsn

async def init_pool() -> None:
    """Create the global async pool on startup and ensure schema."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=_dsn(),
            min_size=1,
            max_size=10,
            kwargs={"autocommit": False},
        )
        # open explicitly to avoid deprecation warning
        await _pool.open()
        await ensure_schema()

async def ensure_schema() -> None:
    assert _pool is not None
    async with _pool.connection() as ac:
        async with ac.transaction():
            await ac.execute("""
                CREATE TABLE IF NOT EXISTS card_assets (
                  oracle_id TEXT PRIMARY KEY,
                  name TEXT,
                  small_url TEXT,
                  local_small_path TEXT,
                  etag TEXT,
                  last_modified TEXT,
                  fetched_at TIMESTAMPTZ DEFAULT now()
                )
            """)

async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

# ---------- sessions CRUD ----------

async def create_session(s: Session) -> None:
    assert _pool is not None, "Pool not initialized"
    async with _pool.connection() as ac:
        async with ac.transaction():
            await ac.execute(
                "INSERT INTO sessions (id, data) VALUES (%s, %s)",
                (s.id, Json(s.model_dump())),
            )

async def load_session(sid: str) -> Optional[Session]:
    assert _pool is not None, "Pool not initialized"
    async with _pool.connection() as ac:
        async with ac.transaction():
            cur = await ac.execute("SELECT data FROM sessions WHERE id=%s", (sid,))
            row = await cur.fetchone()
            if not row:
                return None
            return Session.model_validate(_as_dict(row[0]))

async def _load_for_update(ac: psycopg.AsyncConnection, sid: str) -> Session:
    cur = await ac.execute("SELECT data FROM sessions WHERE id=%s FOR UPDATE", (sid,))
    row = await cur.fetchone()
    if not row:
        raise KeyError("session not found")
    return Session.model_validate(_as_dict(row[0]))

async def _save(ac: psycopg.AsyncConnection, s: Session) -> None:
    await ac.execute(
        "UPDATE sessions SET data=%s, updated_at=now() WHERE id=%s",
        (Json(s.model_dump()), s.id),
    )

async def mutate_session(
    sid: str,
    mutator: Callable[[Session], Awaitable[None]] | Callable[[Session], None],
) -> Session:
    """Serialize mutations per session id using row-level lock."""
    assert _pool is not None, "Pool not initialized"
    async with _pool.connection() as ac:
        async with ac.transaction():
            s = await _load_for_update(ac, sid)
            res = mutator(s)
            if asyncio.iscoroutine(res):
                await res
            await _save(ac, s)
            return s

# ---------- card asset helpers ----------

async def get_asset(oracle_id: str) -> Optional[dict]:
    assert _pool is not None
    async with _pool.connection() as ac:
        async with ac.transaction():
            cur = await ac.execute(
                "SELECT oracle_id, name, small_url, local_small_path, etag, last_modified, fetched_at FROM card_assets WHERE oracle_id=%s",
                (oracle_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            keys = ["oracle_id","name","small_url","local_small_path","etag","last_modified","fetched_at"]
            return dict(zip(keys, row))

async def upsert_asset(
    oracle_id: str, name: str, small_url: str,
    local_small_path: Optional[str], etag: Optional[str], last_modified: Optional[str]
) -> None:
    assert _pool is not None
    async with _pool.connection() as ac:
        async with ac.transaction():
            await ac.execute("""
                INSERT INTO card_assets (oracle_id, name, small_url, local_small_path, etag, last_modified, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (oracle_id) DO UPDATE
                SET name = EXCLUDED.name,
                    small_url = EXCLUDED.small_url,
                    local_small_path = EXCLUDED.local_small_path,
                    etag = EXCLUDED.etag,
                    last_modified = EXCLUDED.last_modified,
                    fetched_at = now()
            """, (oracle_id, name, small_url, local_small_path, etag, last_modified))

# ---------- TTL cleanup ----------

async def cleanup_expired_sessions_once(ttl_hours: int = 72) -> int:
    """
    Delete sessions whose updated_at (or created_at if updated_at is null) is older than ttl_hours.
    Assumes a schema with columns: id TEXT PK, data JSONB, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ.
    Returns number of rows deleted.
    """
    assert _pool is not None
    to_interval = f"{int(ttl_hours)} hours"
    async with _pool.connection() as ac:
        async with ac.transaction():
            cur = await ac.execute(
                """
                WITH base AS (
                  SELECT id
                  FROM sessions
                  WHERE COALESCE(updated_at, created_at, now()) < (now() - %s::interval)
                )
                DELETE FROM sessions s USING base b
                WHERE s.id = b.id
                RETURNING s.id
                """,
                (to_interval,),
            )
            rows = await cur.fetchall()
            deleted = len(rows or [])
            if deleted:
                log.info("TTL cleanup removed %d session(s)", deleted)
            return deleted

async def periodic_cleanup(
    ttl_hours: int = 72,
    interval_seconds: int = 900,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Background loop to periodically call cleanup_expired_sessions_once.
    Create a task on startup, cancel on shutdown:
        app.state.cleanup_stop = asyncio.Event()
        app.state.cleanup_task = asyncio.create_task(periodic_cleanup(72, 900, app.state.cleanup_stop))
    """
    log.info("Starting periodic_cleanup loop (ttl=%sh, every=%ss)", ttl_hours, interval_seconds)
    try:
        while True:
            try:
                await cleanup_expired_sessions_once(ttl_hours)
            except Exception as e:
                log.exception("periodic_cleanup iteration failed: %s", e)
            # Wait for next tick or early stop
            try:
                if stop_event:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                    break
                else:
                    await asyncio.sleep(interval_seconds)
            except asyncio.TimeoutError:
                continue
    finally:
        log.info("periodic_cleanup loop stopped")
