from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter

from app.core.config import settings
from app.db.pool import check_ready as db_ready

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe: fast and dependency-free."""
    return {"status": "ok"}


def _is_cache_writable() -> bool:
    """Check cache dir writability by creating a temp file and removing it."""
    p = Path(settings.IMAGE_CACHE_DIR)
    try:
        p.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=p, prefix="readyz-", delete=True):
            pass
        return True
    except Exception:
        return False


@router.get("/readyz")
async def readyz() -> dict[str, str | bool]:
    cache_ok = _is_cache_writable()
    db_ok = await db_ready()
    status = "ok" if (cache_ok and db_ok) else "degraded"
    return {"status": status, "cache_writable": cache_ok, "db_ready": db_ok}
