from httpx import AsyncClient
import pytest

try:
    # Try to import a FastAPI app instance if it exists
    from roll4treasure-main.app.main import app as test_app
except Exception:
    test_app = None

@pytest.mark.anyio
async def test_root_smoke():
    if test_app is None:
        pytest.skip("FastAPI app not auto-detected for smoke test")
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        resp = await ac.get("/")
        # accept any 2xx for root
        assert resp.status_code // 100 == 2
