"""
Lesson 8 — Response Basics
--------------------------
Demonstrates:
  - Auto JSON conversion (dicts, lists, Pydantic models)
  - Setting status codes with `status_code=`
  - HTTPException for clean error responses
  - JSONResponse for custom headers / dynamic status
  - Mutating the injected Response object
  - 204 No Content (empty body)

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 8 - Response Basics")


# ----------------------------------------------------
# Fake in-memory DB
# ----------------------------------------------------
db: dict[int, dict] = {}


# ----------------------------------------------------
# Pydantic models
# ----------------------------------------------------
class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)


class ItemOut(BaseModel):
    id: int
    name: str
    price: float


# ----------------------------------------------------
# 1. POST returning 201 Created
# ----------------------------------------------------
@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate) -> ItemOut:
    """Standard create pattern: 201 on success, 409 on duplicate."""
    if any(i["name"] == item.name for i in db.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item with that name already exists",
        )
    new_id = len(db) + 1
    saved = {"id": new_id, **item.model_dump()}
    db[new_id] = saved
    return saved


# ----------------------------------------------------
# 2. GET — clean 404 with HTTPException
# ----------------------------------------------------
@app.get("/items/{item_id}")
def get_item(item_id: int) -> ItemOut:
    item = db.get(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )
    return item


# ----------------------------------------------------
# 3. DELETE — 204 No Content (empty body)
# ----------------------------------------------------
@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    if item_id not in db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )
    del db[item_id]
    # return nothing — FastAPI sends an empty 204 body


# ----------------------------------------------------
# 4. Custom header via injected Response
# ----------------------------------------------------
@app.get("/with-headers")
def with_headers(response: Response):
    response.headers["X-Powered-By"] = "FastAPI"
    response.headers["X-Lesson"] = "8"
    return {"message": "Check the response headers!"}


# ----------------------------------------------------
# 5. Dynamic status code based on logic
# ----------------------------------------------------
@app.get("/conditional")
def conditional(lucky: bool = False):
    if lucky:
        return {"message": "You got 200 OK"}
    # Return a non-standard, fun status to show JSONResponse
    return JSONResponse(
        content={"message": "I'm a teapot"},
        status_code=418,
        headers={"X-Tea": "Earl Grey"},
    )


# ----------------------------------------------------
# 6. Returning a list of Pydantic models
# ----------------------------------------------------
@app.get("/items")
def list_items() -> list[ItemOut]:
    return list(db.values())
