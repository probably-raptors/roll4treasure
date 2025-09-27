# /opt/r4t/app/main.py
import asyncio

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

# Treasure store (DB + assets)
from app.features.treasure.store import close_pool, init_pool, periodic_cleanup
from app.web.router import make_root_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    # Static
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

    # Routers
    app.include_router(make_root_router())

    # ---- lifecycle ----
    @app.on_event("startup")
    async def _startup() -> None:
        # Initialize DB pool (uses DATABASE_URL from .env via store._dsn())
        await init_pool()
        # Optional: background cleanup loop (stop cleanly on shutdown)
        app.state._cleanup_stop = asyncio.Event()
        app.state._cleanup_task = asyncio.create_task(
            periodic_cleanup(stop_event=app.state._cleanup_stop)
        )

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        # stop cleanup loop
        stop = getattr(app.state, "_cleanup_stop", None)
        if stop:
            stop.set()
        task = getattr(app.state, "_cleanup_task", None)
        if task:
            try:
                await task
            except Exception:
                pass
        # Close DB pool
        await close_pool()

    return app


# Run locally:
# python -m uvicorn app.main:create_app --factory --reload --port 8001
