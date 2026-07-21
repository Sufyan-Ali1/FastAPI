"""
test_main.py - covers most of the app, but NOT the /stats endpoint.

Run coverage to see the gap:

    pytest --cov=main --cov-report=term-missing

The `Missing` column will point at the /stats lines. Adding a test for /stats
(see the Mini Task) closes the gap and raises the coverage percentage.
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_read_root():
    assert client.get("/").status_code == 200


def test_create_item():
    r = client.post("/items", json={"name": "Widget", "price": 9.99})
    assert r.status_code == 201
    assert r.json()["name"] == "Widget"


def test_get_item_roundtrip():
    created = client.post("/items", json={"name": "Gadget", "price": 2.5}).json()
    r = client.get(f"/items/{created['id']}")
    assert r.status_code == 200
    assert r.json()["price"] == 2.5


def test_get_missing_item_returns_404():
    assert client.get("/items/999999").status_code == 404


def test_create_item_invalid_returns_422():
    assert client.post("/items", json={"name": "", "price": -1}).status_code == 422

# NOTE: no test calls /stats -> those lines show up as MISSING in coverage.
