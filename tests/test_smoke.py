from fastapi.testclient import TestClient

from app.main import create_app

app = create_app()
client = TestClient(app)


def test_smoke():
    r = client.get("/")
    assert r.status_code == 200
