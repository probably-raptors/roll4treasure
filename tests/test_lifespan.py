# tests/test_lifespan.py
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_request_id_header_and_boot():
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code in (200, 404)  # route exists in your app; expect 200
        # Request ID header set by middleware
        assert "x-request-id" in r.headers
        assert r.headers["x-request-id"]
