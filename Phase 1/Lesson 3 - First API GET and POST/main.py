"""
Lesson 3 — First API: GET, POST, PUT, DELETE
--------------------------------------------
A tiny "items" API that demonstrates all four main HTTP methods.

Run it from inside this folder:
    uvicorn main:app --reload

Open Swagger UI to test every endpoint:
    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI

app = FastAPI(title="Lesson 3 - HTTP Methods Demo")


# A simple in-memory "database" — just a Python list.
# (We'll replace this with a real DB in Phase 3.)
fake_db: list[dict] = []


# ---------- GET — read data ----------
@app.get("/items")
def list_items():
    """Return all items in our fake database."""
    return fake_db


@app.get("/items/count")
def count_items():
    """Return the total number of items."""
    return {"total": len(fake_db)}


@app.get("/items/{item_id}")
def get_item(item_id: int):
    """Return a single item by its index."""
    if item_id < 0 or item_id >= len(fake_db):
        return {"error": "Item not found"}
    return fake_db[item_id]

# ---------- POST — create data ----------
@app.post("/items")
def create_item(item: dict):
    """
    Create a new item.
    The request body should be JSON, e.g. {"name": "Pen"}.
    """
    fake_db.append(item)
    return {"message": "Item created", "item": item}


# ---------- PUT — update / replace data ----------
@app.put("/items/{item_id}")
def update_item(item_id: int, item: dict):
    """Replace the item at the given index with new data."""
    if item_id < 0 or item_id >= len(fake_db):
        return {"error": "Item not found"}
    fake_db[item_id] = item
    return {"message": "Item updated", "item": item}


# ---------- DELETE — remove data ----------
@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    """Delete the item at the given index."""
    if item_id < 0 or item_id >= len(fake_db):
        return {"error": "Item not found"}
    removed = fake_db.pop(item_id)
    return {"message": "Item deleted", "item": removed}
