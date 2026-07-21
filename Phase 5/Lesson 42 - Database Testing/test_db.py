"""
test_db.py - database-backed endpoint tests with per-test isolation.

Demonstrates:
  - CRUD through the API against a test database
  - asserting BOTH the API response and the database state
  - proof of isolation: tests pass in any order because each gets a fresh DB
  - seeding with a fixture
"""

from main import Item


# --- CRUD through the API --------------------------------------------------
def test_create_item_persists(client, db_session):
    response = client.post("/items", json={"name": "Widget", "price": 9.99})
    assert response.status_code == 201
    # Assert via the API response...
    assert response.json()["name"] == "Widget"
    # ...AND directly in the database (proves it actually persisted).
    assert db_session.query(Item).count() == 1
    assert db_session.query(Item).first().name == "Widget"


def test_get_missing_item_returns_404(client):
    assert client.get("/items/999").status_code == 404


def test_delete_removes_row_from_db(client, db_session):
    created = client.post("/items", json={"name": "Temp", "price": 1.0}).json()
    assert client.delete(f"/items/{created['id']}").status_code == 204
    assert client.get(f"/items/{created['id']}").status_code == 404      # via API
    assert db_session.get(Item, created["id"]) is None                   # via DB


# --- PROOF OF ISOLATION ----------------------------------------------------
# These two tests would clash if the database leaked between tests. They pass
# in ANY order because each test gets a fresh, empty database.
def test_a_creates_two_items(client):
    client.post("/items", json={"name": "X", "price": 1})
    client.post("/items", json={"name": "Y", "price": 2})
    assert client.get("/items").json()["total"] == 2


def test_b_starts_with_empty_database(client):
    # test_a created 2 items - but this is a FRESH database, so total is 0.
    assert client.get("/items").json()["total"] == 0


# --- Seeding with a fixture ------------------------------------------------
def test_list_shows_seeded_items(client, sample_items):
    body = client.get("/items").json()
    assert body["total"] == 2
    names = [i["name"] for i in body["items"]]
    assert names == ["Seed A", "Seed B"]
