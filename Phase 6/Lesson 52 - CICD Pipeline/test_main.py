"""
test_main.py - the tests the pipeline's `test` stage runs.

If any of these fail in CI, the `build` and `deploy` jobs never run (they
`need` this job). This is the gate that stops broken code from shipping.
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_get_item():
    assert client.get("/items/1").json()["name"] == "Widget"


def test_get_missing_item_returns_404():
    assert client.get("/items/999").status_code == 404
