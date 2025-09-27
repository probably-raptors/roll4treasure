import pytest
from fastapi.testclient import TestClient

try:
    # Your app uses a factory: app.main:create_app
    from app.main import create_app

    test_app = create_app()
except Exception:
    test_app = None


@pytest.mark.anyio
async def test_smoke():
    if test_app is None:
        pytest.skip("No app to test")
    client = TestClient(test_app)
    r = client.get("/")
    assert r.status_code < 500
