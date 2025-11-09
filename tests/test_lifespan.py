# tests/test_lifespan.py
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_request_id_header_and_boot():
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/healthz")
        # If /healthz is guaranteed, use == 200; otherwise allow 404.
        assert r.status_code in (200, 404)
        assert "X-Request-ID" in r.headers
        assert r.headers["X-Request-ID"]
