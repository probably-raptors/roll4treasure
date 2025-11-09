# /opt/r4t/app/main.py
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import configure_root_logger, settings
from app.db.pool import close_pool, init_pool
from app.features.treasure.store import periodic_cleanup
from app.web.router import make_root_router

# -------- JSON logging (preserve existing behavior) --------


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for k in ("request_id", "path", "method", "status_code", "latency_ms"):
            if hasattr(record, k):
                payload[k] = getattr(record, k)
        return json.dumps(payload, ensure_ascii=False)


def setup_json_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)


# -------- Middleware (preserve header casing) --------


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()
        request.state.request_id = req_id  # type: ignore[attr-defined]
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        logger = logging.getLogger("app.access")
        latency = (time.perf_counter() - start) * 1000.0
        extra = {
            "request_id": req_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "latency_ms": round(latency, 2),
        }
        logger.info("request", extra=extra)
        return response


# -------- Lifespan: startup/shutdown orchestration --------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Logging first, then root logger level from settings
    setup_json_logging()
    configure_root_logger()

    # DB pool
    await init_pool()

    # Periodic TTL cleanup (sessions)
    app.state.cleanup_stop = asyncio.Event()
    app.state.cleanup_task = asyncio.create_task(
        periodic_cleanup(ttl_hours=72, interval_seconds=900, stop_event=app.state.cleanup_stop)
    )

    try:
        yield
    finally:
        # Stop periodic task gracefully
        stop = getattr(app.state, "cleanup_stop", None)
        task = getattr(app.state, "cleanup_task", None)
        try:
            if stop:
                stop.set()
            if task:
                await task
        except Exception:
            logging.getLogger("r4t.app").exception("Error stopping periodic cleanup task")

        # Close DB pool
        try:
            await close_pool()
        except Exception:
            logging.getLogger("r4t.app").exception("Error closing DB pool")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

    # Middleware
    app.add_middleware(RequestIdMiddleware)

    # Static
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

    # Routers
    app.include_router(make_root_router())

    return app


# Run locally:
# python -m uvicorn app.main:create_app --factory --reload --port 8001
