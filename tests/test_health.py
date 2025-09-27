from fastapi.testclient import TestClient

from app.main import create_app

app = create_app()
client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_readyz_shape():
    r = client.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "cache_writable" in body
    assert "db_ready" in body
