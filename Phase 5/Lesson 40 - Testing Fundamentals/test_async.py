"""
test_async.py - httpx.AsyncClient (async) tests.

Use this style when you want a genuinely async test (to `await` inside it or
exercise async behavior). It calls the app in-process via ASGITransport.

Requires pytest-asyncio. `asyncio_mode = auto` in pytest.ini means we don't
even need the @pytest.mark.asyncio decorator - async test functions just work.

Run with:

    pytest -v test_async.py
"""

from httpx import ASGITransport, AsyncClient

from main import app


async def test_root_async():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")           # note the await
    assert response.status_code == 200
    assert response.json()["message"] == "Hello, Testing!"


async def test_create_item_async():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/items", json={"name": "AsyncWidget", "price": 12.0})
    assert response.status_code == 201
    assert response.json()["name"] == "AsyncWidget"


async def test_missing_item_async_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/items/424242")
    assert response.status_code == 404
