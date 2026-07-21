"""
Lesson 40 - Testing Fundamentals (the app under test)
-----------------------------------------------------
A tiny in-memory items API. The REAL content of this lesson is the test files:

    test_main.py    - TestClient (sync) endpoint tests
    test_async.py   - httpx.AsyncClient (async) tests

Run everything with:

    pip install fastapi uvicorn httpx pytest pytest-asyncio
    pytest -v

You can still run the app itself:

    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# In-memory store, reset when the app starts (via lifespan).
ITEMS: dict[int, dict] = {}
_next_id = {"value": 1}


class ItemIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    price: float = Field(..., gt=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed one item so a lifespan-dependent test has data.
    ITEMS.clear()
    _next_id["value"] = 1
    ITEMS[_next_id["value"]] = {"id": 1, "name": "Seed Item", "price": 9.99}
    _next_id["value"] = 2
    yield
    ITEMS.clear()


app = FastAPI(title="Lesson 40 - Testing", lifespan=lifespan)


@app.get("/")
def read_root():
    return {"message": "Hello, Testing!"}


@app.get("/items")
def list_items():
    return {"items": list(ITEMS.values())}


@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(item: ItemIn):
    item_id = _next_id["value"]
    _next_id["value"] += 1
    record = {"id": item_id, **item.model_dump()}
    ITEMS[item_id] = record
    return record


@app.get("/items/{item_id}")
def get_item(item_id: int):
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    if item_id not in ITEMS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    del ITEMS[item_id]
