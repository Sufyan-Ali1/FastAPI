"""
Lesson 14 — Dependency Injection
----------------------------------
Demonstrates:
  - Basic Depends() with query parameters
  - Auth dependency (header-based token)
  - Sub-dependencies (auth → admin check)
  - Class-based dependency (Paginator with max_limit)
  - yield dependency (simulated DB session with setup/teardown)
  - dependencies=[...] for side-effect-only deps
  - Dependency caching (same instance within one request)

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs

Quick auth tokens used in this demo:
    token=user    → regular user
    token=admin   → admin user
    anything else → 401
"""

import time
from fastapi import Depends, FastAPI, HTTPException, Query, Header, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 14 - Dependency Injection")


# ============================================================
# Fake database and user store
# ============================================================

fake_users = {
    "user":  {"id": 1, "name": "Sufyan", "is_admin": False, "is_active": True},
    "admin": {"id": 2, "name": "Admin",  "is_admin": True,  "is_active": True},
}

items_db: dict[int, dict] = {
    1: {"id": 1, "name": "Laptop",  "price": 999.99, "owner_token": "user"},
    2: {"id": 2, "name": "Monitor", "price": 299.99, "owner_token": "user"},
}


# ============================================================
# 1. Simple dependency — pagination
# ============================================================

class Paginator:
    """
    Class-based dependency. max_limit is set at construction time,
    page and limit come from query params on each request.
    """
    def __init__(self, max_limit: int = 100):
        self.max_limit = max_limit

    def __call__(
        self,
        page: int  = Query(1,  ge=1,            description="Page number"),
        limit: int = Query(10, ge=1, le=10_000, description="Items per page"),
    ) -> dict:
        if limit > self.max_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Limit cannot exceed {self.max_limit}",
            )
        return {"page": page, "limit": limit, "offset": (page - 1) * limit}


standard_pagination = Paginator(max_limit=100)
admin_pagination    = Paginator(max_limit=1000)


# ============================================================
# 2. Auth dependency — reads token from query (simplified)
#    Real auth uses JWT + Authorization header (Lesson 29)
# ============================================================

def get_current_user(token: str = Query(..., description="Use 'user' or 'admin'")):
    """Returns the user dict, or raises 401 if token is invalid."""
    user = fake_users.get(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    return user


def require_active_user(user: dict = Depends(get_current_user)):
    """Sub-dependency: builds on get_current_user, checks account is active."""
    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended",
        )
    return user


def require_admin(user: dict = Depends(require_active_user)):
    """Sub-dependency: builds on require_active_user, checks admin flag."""
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ============================================================
# 3. yield dependency — simulated DB session
# ============================================================

class FakeDB:
    """Simulates a DB session with setup/teardown lifecycle."""
    def __init__(self):
        self.opened_at = time.time()
        print(f"[DB] Session opened at {self.opened_at:.3f}")

    def close(self):
        print(f"[DB] Session closed after {time.time() - self.opened_at:.3f}s")


def get_db():
    """yield dependency — close() is guaranteed even if the endpoint raises."""
    db = FakeDB()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Endpoints
# ============================================================

# -- Items: public list with pagination ----------------------
@app.get("/items")
def list_items(
    pagination: dict = Depends(standard_pagination),
    user: dict       = Depends(require_active_user),
    db: FakeDB       = Depends(get_db),
):
    """
    Three dependencies injected:
    1. pagination  → validates page/limit
    2. user        → validates auth
    3. db          → opens/closes a DB session
    """
    all_items = list(items_db.values())
    start = pagination["offset"]
    end   = start + pagination["limit"]
    return {
        "page":       pagination["page"],
        "limit":      pagination["limit"],
        "total":      len(all_items),
        "items":      all_items[start:end],
        "fetched_by": user["name"],
    }


# -- Single item ---------------------------------------------
@app.get("/items/{item_id}")
def get_item(
    item_id: int,
    user: dict   = Depends(require_active_user),
):
    item = items_db.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


# -- Admin-only: delete any item ----------------------------
@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    admin: dict  = Depends(require_admin),   # 403 if not admin
    db: FakeDB   = Depends(get_db),
):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    del items_db[item_id]


# -- Admin list with higher pagination limit ----------------
@app.get("/admin/items")
def admin_list_items(
    pagination: dict = Depends(admin_pagination),   # max 1000
    admin: dict      = Depends(require_admin),
):
    return {
        "items": list(items_db.values()),
        **pagination,
    }


# -- dependencies=[...] for side-effects only ---------------
def log_request(request: Request):
    """Runs for its side-effect (logging). Return value is discarded."""
    print(f"[LOG] {request.method} {request.url.path}")


@app.get("/public", dependencies=[Depends(log_request)])
def public_endpoint():
    """log_request runs on every call but its value isn't injected."""
    return {"message": "This endpoint is public but all requests are logged"}


# ============================================================
# Models and extra endpoint showing yield + business logic
# ============================================================

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)


@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(
    item: ItemCreate,
    user: dict   = Depends(require_active_user),
    db: FakeDB   = Depends(get_db),
):
    """
    yield dependency: db is opened before this runs,
    closed in finally block after response is sent.
    """
    new_id = max(items_db.keys(), default=0) + 1
    record = {"id": new_id, **item.model_dump(), "owner_token": None}
    items_db[new_id] = record
    return record
