"""
test_main.py - TestClient (sync) tests.

Each test is a `test_*` function using plain `assert`. Run with:

    pytest -v

TestClient calls the app IN-PROCESS (no running server, no network).
"""

from fastapi.testclient import TestClient

from main import app

# A module-level client is fine for simple, stateless checks.
client = TestClient(app)


# --- Happy paths -----------------------------------------------------------
def test_read_root_returns_greeting():
    # Arrange / Act
    response = client.get("/")
    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Testing!"}


def test_create_item_returns_201_with_generated_id():
    response = client.post("/items", json={"name": "Widget", "price": 9.99})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Widget"
    assert body["price"] == 9.99
    assert "id" in body  # the server generates the id


def test_create_then_get_item_roundtrip():
    created = client.post("/items", json={"name": "Gadget", "price": 3.5}).json()
    fetched = client.get(f"/items/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Gadget"


def test_delete_item_returns_204_then_404():
    created = client.post("/items", json={"name": "Temp", "price": 1.0}).json()
    assert client.delete(f"/items/{created['id']}").status_code == 204
    assert client.get(f"/items/{created['id']}").status_code == 404


# --- Failure paths (just as important) -------------------------------------
def test_get_missing_item_returns_404():
    response = client.get("/items/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


def test_create_item_with_empty_name_returns_422():
    response = client.post("/items", json={"name": "", "price": 9.99})
    assert response.status_code == 422  # Pydantic validation error


def test_create_item_with_negative_price_returns_422():
    response = client.post("/items", json={"name": "Bad", "price": -5})
    assert response.status_code == 422


# --- Lifespan test: startup seeds one item ---------------------------------
def test_lifespan_seeds_an_item():
    # Using the context manager runs the lifespan startup, which seeds an item.
    with TestClient(app) as c:
        response = c.get("/items")
        names = [i["name"] for i in response.json()["items"]]
        assert "Seed Item" in names
