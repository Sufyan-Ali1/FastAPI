"""tests/test_items.py

Two kinds of tests, enabled by the layering:
  - SERVICE tests: exercise business logic directly, NO HTTP/TestClient needed.
  - ENDPOINT tests: exercise the full HTTP path through the router.
"""

import pytest

from app.schemas.item import ItemCreate
from app.services import item_service
from app.services.exceptions import DuplicateSKUError, ItemNotFoundError


# === SERVICE-layer tests (no HTTP - this is the payoff of a services layer) ===
def test_service_create_item(db_session):
    item = item_service.create_item(
        db_session, ItemCreate(name="Widget", sku="WID-001", price=9.99)
    )
    assert item.id is not None
    assert item.sku == "WID-001"


def test_service_duplicate_sku_raises_domain_error(db_session):
    item_service.create_item(
        db_session, ItemCreate(name="A", sku="DUP-001", price=1.0)
    )
    with pytest.raises(DuplicateSKUError):        # a DOMAIN error, not HTTPException
        item_service.create_item(
            db_session, ItemCreate(name="B", sku="DUP-001", price=2.0)
        )


def test_service_get_missing_raises_domain_error(db_session):
    with pytest.raises(ItemNotFoundError):
        item_service.get_item(db_session, 999)


# === ENDPOINT tests (full HTTP path; domain errors -> HTTP status codes) ======
def test_endpoint_create_and_get(client):
    created = client.post(
        "/items", json={"name": "Gadget", "sku": "GAD-001", "price": 3.5}
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert client.get(f"/items/{item_id}").json()["sku"] == "GAD-001"


def test_endpoint_duplicate_sku_returns_409(client):
    client.post("/items", json={"name": "A", "sku": "X-1", "price": 1.0})
    dup = client.post("/items", json={"name": "B", "sku": "X-1", "price": 2.0})
    assert dup.status_code == 409          # DuplicateSKUError -> 409 via handler


def test_endpoint_missing_item_returns_404(client):
    assert client.get("/items/424242").status_code == 404   # ItemNotFoundError -> 404


def test_endpoint_delete(client):
    created = client.post(
        "/items", json={"name": "Temp", "sku": "TMP-1", "price": 1.0}
    ).json()
    assert client.delete(f"/items/{created['id']}").status_code == 204
    assert client.get(f"/items/{created['id']}").status_code == 404
