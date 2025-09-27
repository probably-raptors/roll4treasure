# /opt/r4t/app/main.py
import contextlib
import json
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db.pool import close_pool, init_pool
from app.web.router import make_root_router


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


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
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


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    # Logging
    setup_json_logging()
    app.add_middleware(RequestIdMiddleware)

    # Static
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

    # Routers
    app.include_router(make_root_router())

    # ---- lifecycle ----
    @app.on_event("startup")
    async def _startup() -> None:
        await init_pool()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        task = getattr(app.state, "_cleanup_task", None)
        if task:
            with contextlib.suppress(Exception):
                await task
        await close_pool()

    return app


# Run locally:
# python -m uvicorn app.main:create_app --factory --reload --port 8001
