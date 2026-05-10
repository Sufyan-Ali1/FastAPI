"""
Lesson 13 — Error Handling
---------------------------
Demonstrates:
  - Anatomy of RequestValidationError — loc, type, msg, input
  - Reformatting validation errors into clean field-level messages
  - Dev vs prod error detail (ENV environment variable)
  - Python logging module for 4xx/5xx errors
  - Business-rule errors vs schema-validation errors
  - raise ... from e (preserving traceback chain)
  - Custom exception class with structured detail

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs

To simulate production mode:
    $env:ENV = "production"
    uvicorn main:app --reload
"""

import logging
import os
import traceback as tb

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Logging setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("lesson13")

# ── Dev / prod toggle ────────────────────────────────────────
IS_DEV = os.getenv("ENV", "development") == "development"

app = FastAPI(title="Lesson 13 - Error Handling")


# ============================================================
# Custom exception classes
# ============================================================

class AppException(HTTPException):
    """Base for all app-level exceptions with structured detail."""
    def __init__(self, status_code: int, error_type: str, message: str, **extra):
        detail = {"type": error_type, "message": message, **extra}
        super().__init__(status_code=status_code, detail=detail)


class NotFoundException(AppException):
    def __init__(self, resource: str, resource_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="NOT_FOUND",
            message=f"{resource} with id {resource_id} not found",
        )


class ConflictException(AppException):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_type="CONFLICT",
            message=message,
            **({"field": field} if field else {}),
        )


# ============================================================
# Global exception handlers
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail

    # Log 4xx as warning, 5xx as error
    if exc.status_code >= 500:
        logger.error("HTTP %s | %s %s | %s", exc.status_code, request.method, request.url, detail)
    else:
        logger.warning("HTTP %s | %s %s | %s", exc.status_code, request.method, request.url, detail)

    # Normalise plain strings
    if isinstance(detail, str):
        detail = {"type": "ERROR", "message": detail}

    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": exc.status_code, **detail}},
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Reformat Pydantic's nested error list into clean field-level messages.
    loc example: ("body", "address", "city") → "address.city"
    """
    logger.warning("422 Validation | %s %s", request.method, request.url)

    formatted = []
    for err in exc.errors():
        loc = err.get("loc", [])
        # Strip the source prefix ("body", "query", "path") — noise for the client
        field_parts = [str(p) for p in loc if p not in ("body", "query", "path")]
        formatted.append({
            "field":   ".".join(field_parts) if field_parts else "root",
            "type":    err["type"],
            "message": err["msg"],
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "errors": formatted},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all: log fully, expose minimally (nothing in prod)."""
    logger.error(
        "500 Unhandled | %s %s | %s: %s",
        request.method, request.url,
        type(exc).__name__, exc,
        exc_info=True,
    )

    if IS_DEV:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(exc),
                "traceback": tb.format_exc(),
            },
        )

    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )


# ============================================================
# Models
# ============================================================

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0, description="Price in USD")
    stock: int = Field(0, ge=0)


class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    stock: int


class StockUpdate(BaseModel):
    quantity: int = Field(..., ge=1, description="Amount to deduct from stock")


# Fake DB
products_db: dict[int, dict] = {}


# ============================================================
# Endpoints
# ============================================================

@app.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate):
    """
    Pydantic handles: name length, price > 0, stock >= 0.
    We handle business rule: duplicate name → 409.
    """
    if any(p["name"] == product.name for p in products_db.values()):
        raise ConflictException(
            message=f"A product named '{product.name}' already exists",
            field="name",
        )
    new_id = len(products_db) + 1
    record = {"id": new_id, **product.model_dump()}
    products_db[new_id] = record
    return record


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    product = products_db.get(product_id)
    if not product:
        raise NotFoundException("Product", product_id)
    return product


@app.post("/products/{product_id}/deduct", response_model=ProductOut)
def deduct_stock(product_id: int, body: StockUpdate):
    """
    Business rule: can't deduct more than available stock.
    Uses raise ... from e pattern to preserve traceback context.
    """
    product = products_db.get(product_id)
    if not product:
        raise NotFoundException("Product", product_id)

    try:
        if body.quantity > product["stock"]:
            raise ValueError(
                f"Requested {body.quantity}, only {product['stock']} in stock"
            )
        product["stock"] -= body.quantity
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "type": "INSUFFICIENT_STOCK",
                "message": "Not enough stock to fulfil this request",
                "available": product["stock"],
                "requested": body.quantity,
            },
        ) from e

    return product


# ── Dev-only: intentional 500 to test generic handler ────────
@app.get("/crash")
def crash():
    """Triggers a raw RuntimeError — caught by the generic handler."""
    raise RuntimeError("Something broke internally")
