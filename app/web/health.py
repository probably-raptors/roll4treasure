from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe: fast and dependency-free."""
    return {"status": "ok"}


def _is_cache_writable() -> bool:
    """Check cache dir writability by creating a temp file and removing it.

    Cache dir priority:
      1) IMAGE_CACHE_DIR env var
      2) ./img-cache fallback
    """
    cache_dir = os.environ.get("IMAGE_CACHE_DIR", "img-cache")
    p = Path(cache_dir)
    try:
        p.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=p, prefix="readyz-", delete=True):
            pass
        return True
    except Exception:
        return False


async def _is_db_ready() -> bool:
    """Best-effort DB readiness.

    We haven't refactored DI yet (Milestone 2), so we try to import the current
    store module and acquire a connection if the global pool exists.
    """

    try:
        from app.features.treasure import store  # type: ignore  # noqa: PLC0415
    except Exception:
        store = None  # type: ignore[assignment]

    pool = getattr(store, "_pool", None)
    if pool is None:
        return False

    try:
        async with pool.connection() as _conn:
            return True
    except Exception:
        return False


@router.get("/readyz")
async def readyz() -> dict[str, str | bool]:
    cache_ok = _is_cache_writable()
    db_ok = await _is_db_ready()
    status = "ok" if (cache_ok and db_ok) else "degraded"
    return {"status": status, "cache_writable": cache_ok, "db_ready": db_ok}
