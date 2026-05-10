"""
Lesson 12 — Status Codes & HTTP Exceptions
-------------------------------------------
Demonstrates:
  - HTTPException with status module constants
  - Structured detail (string, dict, list)
  - Custom exception classes
  - Global @app.exception_handler for HTTPException
  - RequestValidationError handler (custom 422 format)
  - Generic Exception handler (catch-all 500)

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 12 - Status Codes & HTTP Exceptions")


# ============================================================
# Global exception handlers — defined first so they cover
# every endpoint below
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """All HTTPExceptions return the same shape."""
    detail = exc.detail
    # Normalise plain strings to a dict so the shape is always consistent
    if isinstance(detail, str):
        detail = {"message": detail, "type": "ERROR"}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {"code": exc.status_code, **detail},
        },
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom 422 format — cleaner field paths for frontend teams."""
    errors = []
    for err in exc.errors():
        errors.append({
            "field": " → ".join(str(part) for part in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "errors": errors},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all — prevents raw Python tracebacks reaching clients."""
    print(f"[ERROR] Unhandled exception: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {"code": 500, "message": "Internal server error", "type": "SERVER_ERROR"},
        },
    )


# ============================================================
# Custom exception classes
# ============================================================

class NotFoundException(HTTPException):
    def __init__(self, resource: str, resource_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"{resource} with id {resource_id} not found",
                "type": "NOT_FOUND",
            },
        )


class ConflictException(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": message, "type": "CONFLICT"},
        )


class ForbiddenException(HTTPException):
    def __init__(self, action: str = "perform this action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": f"You are not allowed to {action}", "type": "FORBIDDEN"},
        )


# ============================================================
# Models
# ============================================================

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)


class ItemOut(BaseModel):
    id: int
    name: str
    price: float


# Fake DB
items_db: dict[int, dict] = {}


# ============================================================
# 1. Standard CRUD — clean HTTPException usage
# ============================================================

@app.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate):
    """409 if duplicate name, else 201."""
    if any(i["name"] == item.name for i in items_db.values()):
        raise ConflictException(f"Item named '{item.name}' already exists")
    new_id = len(items_db) + 1
    record = {"id": new_id, **item.model_dump()}
    items_db[new_id] = record
    return record


@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int):
    item = items_db.get(item_id)
    if not item:
        raise NotFoundException("Item", item_id)
    return item


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    if item_id not in items_db:
        raise NotFoundException("Item", item_id)
    del items_db[item_id]


# ============================================================
# 2. Structured detail — dict and list forms
# ============================================================

@app.get("/structured-error")
def structured_error():
    """Shows a dict detail — useful for frontend error parsing."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": "Validation failed",
            "type": "VALIDATION_ERROR",
            "fields": [
                {"field": "email", "issue": "Domain not allowed"},
                {"field": "age",   "issue": "Must be 18+"},
            ],
        },
    )


# ============================================================
# 3. 401 with WWW-Authenticate header
# ============================================================

@app.get("/protected")
def protected_route(token: str | None = None):
    """Requires a token query param (simplified auth demo)."""
    if token != "secret":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid or missing token", "type": "UNAUTHORIZED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"message": "Welcome to the protected route"}


# ============================================================
# 4. 403 Forbidden — permission check
# ============================================================

@app.delete("/admin/items/{item_id}")
def admin_delete(item_id: int, is_admin: bool = False):
    """Only admin can delete via this route."""
    if not is_admin:
        raise ForbiddenException("delete items via the admin route")
    if item_id not in items_db:
        raise NotFoundException("Item", item_id)
    del items_db[item_id]


# ============================================================
# 5. Intentional crash — tests the generic 500 handler
# ============================================================

@app.get("/crash")
def crash():
    """Raises a raw Python exception — caught by generic handler."""
    raise RuntimeError("Something exploded internally")
