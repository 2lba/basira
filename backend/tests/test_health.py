from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_should_return_ok_when_healthz_called():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_should_return_version_when_root_called():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "reviewly"
    assert "version" in data
