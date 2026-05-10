# Lesson 13 — Error Handling

> **Goal of this lesson:** Go beyond basic `HTTPException`. Understand **validation error internals**, write **structured error responses**, handle errors differently in **dev vs prod**, and log errors properly so debugging is fast.

---

## 1. What Lesson 12 Didn't Cover

Lesson 12 taught the basics — `HTTPException`, `@app.exception_handler`, custom classes.

This lesson covers the *hard* parts that bite you in real apps:

1. **Validation errors are complex** — Pydantic produces deeply nested error objects. You need to understand them to reformat them.
2. **Dev vs prod error detail** — In dev, you want the full traceback. In prod, you never expose it.
3. **Logging** — Your error handler should log before responding.
4. **Context in errors** — Telling the client *exactly* which field failed and *why*.
5. **Errors from dependencies** — Errors raised inside `Depends()` chains behave slightly differently.

---

## 2. Anatomy of a Pydantic Validation Error

When a `RequestValidationError` fires, each error in `exc.errors()` is a dict with:

```python
{
    "type":  "missing",          # Pydantic error type (string key)
    "loc":   ("body", "email"),  # tuple: where in the input the error is
    "msg":   "Field required",   # human-readable message
    "input": {},                 # the actual input that failed
    "url":   "https://..."       # link to Pydantic docs for this error type
}
```

### The `loc` tuple explained

```
("body", "email")              → body → field "email"
("body", "address", "city")    → body → nested model → field "city"
("path", "user_id")            → path parameter "user_id"
("query", "page")              → query parameter "page"
("body", "tags", 2)            → body → list field "tags" → index 2
```

### Common Pydantic error types

| `type` string | Meaning |
|---------------|---------|
| `missing` | Required field not provided |
| `string_too_short` | `min_length` violated |
| `string_too_long` | `max_length` violated |
| `greater_than_equal` | `ge` violated |
| `less_than_equal` | `le` violated |
| `string_pattern_mismatch` | `pattern` regex failed |
| `int_parsing` | Value couldn't be parsed as int |
| `value_error` | Custom `@field_validator` raised `ValueError` |

---

## 3. Reformatting Validation Errors

```python
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    formatted = []
    for err in exc.errors():
        loc = err.get("loc", [])
        # Skip the first element if it's "body", "query", or "path" — that's noise
        field_parts = [str(p) for p in loc if p not in ("body", "query", "path")]
        formatted.append({
            "field":   ".".join(field_parts) if field_parts else "root",
            "message": err["msg"],
            "type":    err["type"],
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "errors": formatted},
    )
```

Input:
```json
{ "name": "", "price": -5, "address": {} }
```

Output:
```json
{
  "success": false,
  "errors": [
    { "field": "name",          "message": "String should have at least 1 character", "type": "string_too_short" },
    { "field": "price",         "message": "Input should be greater than 0",           "type": "greater_than" },
    { "field": "address.city",  "message": "Field required",                           "type": "missing" }
  ]
}
```

The frontend can now highlight exactly which fields failed.

---

## 4. Dev vs Prod Error Detail

In development, full error detail helps you debug. In production, raw detail can leak internal logic or sensitive paths.

```python
import os

IS_DEV = os.getenv("ENV", "development") == "development"

@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    import traceback
    
    # Always log the full detail internally
    print(f"[500] {request.method} {request.url}")
    traceback.print_exc()
    
    if IS_DEV:
        # In dev: expose the traceback so you can debug instantly
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
    else:
        # In prod: give nothing away
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"},
        )
```

Set `ENV=production` in your `.env` for production deployments.

---

## 5. Logging Errors Properly

`print()` is fine for learning, but real apps use Python's `logging` module:

```python
import logging

logger = logging.getLogger(__name__)

@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        logger.error(
            "HTTP %s on %s %s",
            exc.status_code, request.method, request.url,
            exc_info=True,
        )
    elif exc.status_code >= 400:
        logger.warning(
            "HTTP %s on %s %s — %s",
            exc.status_code, request.method, request.url, exc.detail,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )
```

**Log levels:**
- `logger.debug()` — dev-only detail
- `logger.info()` — normal operations
- `logger.warning()` — 4xx client errors (their fault, but worth tracking)
- `logger.error()` — 5xx server errors (your fault, needs attention)
- `logger.critical()` — system is down

---

## 6. Logging Configuration

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("myapp")
```

Sample output:
```
2024-05-09 14:23:01 | WARNING  | myapp | HTTP 404 on GET /users/999 — User not found
2024-05-09 14:23:05 | ERROR    | myapp | HTTP 500 on POST /orders
```

In Lesson 46 (Logging) we'll use `structlog` or `loguru` for structured JSON logs — better for production log aggregators.

---

## 7. Raising Errors from Dependencies

When you use `Depends()` (Lesson 14), errors raised inside the dependency propagate cleanly:

```python
from fastapi import Depends, HTTPException, status

def get_current_user(token: str = Query(...)):
    user = verify_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user

@app.get("/profile")
def profile(user = Depends(get_current_user)):
    return user  # only reached if get_current_user didn't raise
```

The global `HTTPException` handler catches it the same way — no special treatment needed.

---

## 8. Re-raising Errors with Extra Context

Sometimes you want to catch an exception, add context, then re-raise:

```python
@app.post("/orders")
def create_order(order: OrderCreate):
    try:
        result = payment_service.charge(order.amount)
    except PaymentDeclinedError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Payment declined",
                "type": "PAYMENT_DECLINED",
                "reason": str(e),
            },
        ) from e  # `from e` preserves the original traceback in logs
    return result
```

`raise ... from e` keeps the original error in the traceback chain — vital for debugging.

---

## 9. Validating Business Rules (Not Just Schema)

Pydantic validates **shape**. Business rules (email uniqueness, stock availability, etc.) live in your endpoint and raise `HTTPException`:

```python
@app.post("/users", response_model=UserOut, status_code=201)
def create_user(user: UserCreate):
    # Pydantic already validated: email format, password length, etc.
    # Now we check business rules:
    if db.email_exists(user.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Email '{user.email}' is already registered",
                "type": "EMAIL_TAKEN",
                "field": "email",
            },
        )
    # Create user...
```

**Never** put database lookups inside `@field_validator` — that mixes validation and I/O in the wrong layer.

---

## 10. Real-World Use Case — Unified Error Contract

A frontend team agrees on this error contract for your API:

```json
// Single error
{
  "success": false,
  "error": {
    "code": 404,
    "type": "NOT_FOUND",
    "message": "Product with id 5 not found"
  }
}

// Validation errors (multiple)
{
  "success": false,
  "errors": [
    { "field": "price",   "type": "greater_than", "message": "Must be > 0" },
    { "field": "name",    "type": "missing",       "message": "Field required" }
  ]
}
```

You implement this once in `main.py` — all 50 endpoints automatically conform.

---

## 11. Mini Task

Open `main.py`:

1. Run: `uvicorn main:app --reload`
2. In `/docs`:
   - **POST `/products`** with missing `name` and negative `price` → see multi-field error format
   - **GET `/products/999`** → 404 in unified format
   - **POST `/products`** with a duplicate name → 409 in unified format
   - **GET `/crash`** → 500 (check the console for the logged traceback)
3. Set `ENV=production` in your shell and restart — crash endpoint should hide detail.
4. **Bonus:** Add a `POST /checkout` endpoint that tries to deduct stock. If stock would go below 0, raise a custom `InsufficientStockException` (422) with `{ "type": "INSUFFICIENT_STOCK", "available": n, "requested": m }`.

---

## 12. Key Takeaways

- `exc.errors()` gives you a list of dicts — each has `type`, `loc`, `msg`, `input`.
- `loc` tuple tells you exactly where (body, query, path, nested field, list index).
- Dev vs prod: log everything internally, expose nothing sensitive externally.
- Use `logging` not `print()` — different levels for 4xx vs 5xx.
- Business rule errors live in the endpoint, not in `@field_validator`.
- `raise HTTPException(...) from original_exc` preserves traceback chains.

---

## ➡️ Next Lesson

**Lesson 14 — Dependency Injection**
- `Depends()` — the most important FastAPI feature you haven't used yet
- Sub-dependencies
- Class-based dependencies
- Dependency caching
- `yield` dependencies for cleanup
