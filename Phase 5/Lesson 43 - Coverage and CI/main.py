"""
Lesson 43 - Coverage & CI (the app under test)
----------------------------------------------
A small app with a DELIBERATE coverage gap: /stats is not tested by
test_main.py, so the coverage report shows it as missing. The Mini Task is to
close that gap.

Measure coverage with:

    pip install fastapi uvicorn httpx pytest pytest-cov
    pytest --cov=main --cov-report=term-missing
"""

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 43 - Coverage & CI")

ITEMS: dict[int, dict] = {}
_next_id = {"value": 1}


class ItemIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    price: float = Field(..., gt=0)


@app.get("/")
def read_root():
    return {"message": "Coverage demo"}


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


# --- This endpoint is intentionally NOT covered by test_main.py, so the
#     coverage report flags its lines as missing. Add a test to close the gap.
@app.get("/stats")
def stats():
    total = len(ITEMS)
    avg_price = sum(i["price"] for i in ITEMS.values()) / total if total else 0
    return {"count": total, "average_price": round(avg_price, 2)}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app)
