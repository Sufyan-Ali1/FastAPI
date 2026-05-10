# Lesson 12 — Status Codes & HTTP Exceptions

> **Goal of this lesson:** Master how FastAPI handles errors — from simple `HTTPException` to custom exception classes with global handlers — so your API always returns **structured, predictable error responses**.

---

## 1. The Problem with Manual Error Returns

Without proper exception handling, developers write things like:

```python
@app.get("/users/{id}")
def get_user(id: int):
    user = db.get(id)
    if not user:
        return {"error": "not found"}          # ❌ status is still 200!
    if not current_user.is_admin:
        return {"error": "forbidden"}, 403     # ❌ FastAPI ignores the tuple
    return user
```

Both are wrong. The client gets a `200 OK` with an error message — or a raw tuple that FastAPI doesn't know how to serialize.

The correct tool is `HTTPException`.

---

## 2. `HTTPException` — The Standard

```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="User not found",
)
```

FastAPI catches this and returns:
```
HTTP/1.1 404 Not Found
Content-Type: application/json

{"detail": "User not found"}
```

**Always use `raise`, never `return`.** An exception interrupts execution — a return doesn't.

---

## 3. The `status` Module

Never hardcode numbers. Use named constants:

```python
from fastapi import status

status.HTTP_200_OK               # 200
status.HTTP_201_CREATED          # 201
status.HTTP_204_NO_CONTENT       # 204
status.HTTP_400_BAD_REQUEST      # 400
status.HTTP_401_UNAUTHORIZED     # 401
status.HTTP_403_FORBIDDEN        # 403
status.HTTP_404_NOT_FOUND        # 404
status.HTTP_409_CONFLICT         # 409
status.HTTP_422_UNPROCESSABLE_ENTITY  # 422
status.HTTP_500_INTERNAL_SERVER_ERROR # 500
```

They're self-documenting and your editor autocompletes them.

---

## 4. Adding Custom Headers to Errors

Sometimes error responses need headers — for example, a `401` must include a `WWW-Authenticate` header per the HTTP spec:

```python
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)
```

The `headers` parameter is optional but occasionally required by HTTP standards.

---

## 5. The `detail` Field — More Than a String

`detail` can be any JSON-serializable value — a string, dict, or list:

```python
# String (most common)
raise HTTPException(status_code=404, detail="User not found")

# Dict — structured error
raise HTTPException(
    status_code=422,
    detail={
        "code": "EMAIL_TAKEN",
        "message": "This email is already registered",
        "field": "email",
    }
)

# List — multiple errors
raise HTTPException(
    status_code=400,
    detail=[
        {"field": "email", "message": "Invalid format"},
        {"field": "age",   "message": "Must be 18+"},
    ]
)
```

Using structured `detail` makes it easy for frontend code to parse and display errors consistently.

---

## 6. Custom Exception Classes

For larger apps, `HTTPException` everywhere becomes repetitive and hard to maintain. Create your own exception classes:

```python
class NotFoundException(HTTPException):
    def __init__(self, resource: str, id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} with id {id} not found",
        )

class ForbiddenException(HTTPException):
    def __init__(self, action: str = "perform this action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not allowed to {action}",
        )
```

Now your endpoint reads cleanly:

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = db.get(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    return user
```

---

## 7. Global Exception Handlers with `@app.exception_handler`

For complete control over error formatting, register a **global handler**. It intercepts any matching exception across the entire app:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "detail": exc.detail,
            },
        },
    )
```

Now **every** `HTTPException` in the app returns this shape — consistent across all endpoints.

---

## 8. Handling Pydantic Validation Errors Globally

By default, when Pydantic validation fails, FastAPI returns a `422` with this format:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

You can override this completely:

```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " → ".join(str(e) for e in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, "errors": errors},
    )
```

Now validation errors use YOUR format, not Pydantic's default.

---

## 9. Handling Unexpected Errors (500s)

Catch all unhandled exceptions so the client never sees a raw Python traceback:

```python
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log the real error internally (don't expose it to clients)
    print(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {"code": 500, "detail": "Internal server error"},
        },
    )
```

In production, replace `print()` with a real logger (Lesson 46).

---

## 10. Complete Error Handling Pattern

A production-quality error strategy has four layers:

```
Layer 1 — Pydantic validation        → automatic 422, can be overridden
Layer 2 — HTTPException              → raise for expected errors (404, 403, 409…)
Layer 3 — Custom exception classes   → cleaner code, reusable errors
Layer 4 — Global exception_handler   → unified response format, catch-all 500
```

```python
# Layer 2 — endpoint-level
@app.get("/items/{item_id}")
def get_item(item_id: int):
    item = db.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

# Layer 3 — custom class
class ItemNotFound(HTTPException):
    def __init__(self, item_id: int):
        super().__init__(status_code=404, detail=f"Item {item_id} not found")

# Layer 4 — global handler shapes the response
@app.exception_handler(HTTPException)
async def http_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": exc.detail},
    )
```

---

## 11. Real-World Use Case — A Consistent Error Contract

A frontend team needs all errors in one predictable shape:

```json
{
  "success": false,
  "error": {
    "code": 404,
    "message": "User with id 42 not found",
    "type": "NOT_FOUND"
  }
}
```

You implement this once via a global handler. Every `HTTPException` across all 50 endpoints automatically uses this shape — no per-endpoint formatting needed.

```python
class AppError(HTTPException):
    def __init__(self, status_code: int, message: str, error_type: str):
        super().__init__(
            status_code=status_code,
            detail={"message": message, "type": error_type},
        )

@app.exception_handler(HTTPException)
async def unified_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, str):
        detail = {"message": detail, "type": "ERROR"}
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": exc.status_code, **detail}},
    )
```

---

## 12. Mini Task

Open `main.py`:

1. Run: `uvicorn main:app --reload`
2. In `/docs`:
   - **GET `/items/999`** → consistent 404 from global handler
   - **POST `/items`** with missing fields → 422 in custom format
   - **POST `/items`** with duplicate name → 409 from `ConflictException`
   - **GET `/crash`** → 500 caught by global handler (no raw traceback)
3. Check the shape of every error — all should follow the same `{"success": false, "error": {...}}` structure.
4. **Bonus:** Add a custom `RateLimitException` (429 Too Many Requests) and register a handler for it with a `Retry-After: 60` header.

---

## 13. Key Takeaways

- Always `raise HTTPException`, never return an error dict manually.
- `detail` can be a string, dict, or list — use structured dicts for frontend parsing.
- Custom exception classes reduce boilerplate and make endpoints readable.
- `@app.exception_handler` gives you a unified error shape across the whole API.
- Override `RequestValidationError` to control the 422 format.
- Handle bare `Exception` globally so 500s never leak tracebacks to clients.

---

## ➡️ Next Lesson

**Lesson 13 — Error Handling**
- Validation error deep dive
- Custom error responses with more structure
- Global exception handlers in real apps
- Logging errors properly
