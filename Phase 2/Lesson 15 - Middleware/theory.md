# Lesson 15 — Middleware

> **Goal of this lesson:** Understand what middleware is, how it differs from dependencies, and how to write custom middleware that wraps every request — for logging, timing, headers, rate limiting, and more.

---

## 1. What Is Middleware?

Middleware sits **between** the client and your endpoint. Every request passes through it *before* reaching the endpoint, and every response passes through it *after* leaving the endpoint.

```
Client
  ↓ request
Middleware 1  ← outermost
  ↓
Middleware 2
  ↓
Middleware 3  ← innermost
  ↓
Your endpoint function
  ↑
Middleware 3  ← runs again on the way back
  ↑
Middleware 2
  ↑
Middleware 1
  ↑ response
Client
```

This "wrapping" shape is called the **onion model**.

---

## 2. Middleware vs Dependency Injection

They look similar but serve different purposes:

| | Middleware | `Depends()` |
|---|---|---|
| Scope | **Every** request | Only the route it's declared on |
| Access to response | ✅ Yes (can modify headers, status) | ❌ No (runs before response exists) |
| Can short-circuit | ✅ Yes (return early without calling endpoint) | ✅ Yes (raise HTTPException) |
| Runs for 404/422 errors | ✅ Yes | ❌ No |
| Ideal for | Logging, CORS, auth headers, rate limiting | Business logic, auth, DB sessions |

**Rule of thumb:**
- Needs to run on **every request** (including errors and unknown routes)? → Middleware
- Needs to run on **specific routes** and inject a value? → Dependency

---

## 3. The `@app.middleware("http")` Decorator

The simplest way to write custom middleware:

```python
import time
from fastapi import Request

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)    # call the next middleware / endpoint
    duration = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}s"
    return response
```

**The pattern every middleware follows:**
1. Do something **before** the request (inspect, log, block, modify)
2. `response = await call_next(request)` — pass through to the endpoint
3. Do something **after** the response (add headers, log duration)
4. `return response`

To **short-circuit** (block the request before it reaches the endpoint):

```python
@app.middleware("http")
async def block_banned_ips(request: Request, call_next):
    if request.client.host in BANNED_IPS:
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    # never calls call_next — endpoint never runs
    return await call_next(request)
```

---

## 4. `BaseHTTPMiddleware` — Class-Based

For configurable middleware, subclass `BaseHTTPMiddleware`:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_calls: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_calls = max_calls
        self.window = window_seconds
        self.call_counts: dict[str, int] = {}

    async def dispatch(self, request: Request, call_next) -> Response:
        ip = request.client.host
        self.call_counts[ip] = self.call_counts.get(ip, 0) + 1
        if self.call_counts[ip] > self.max_calls:
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(self.window)},
            )
        return await call_next(request)

# Register it
app.add_middleware(RateLimitMiddleware, max_calls=50, window_seconds=60)
```

---

## 5. Execution Order

Middleware stacks in **reverse registration order** — the last one added is the outermost:

```python
app.add_middleware(LoggingMiddleware)   # added first → runs last (innermost)
app.add_middleware(AuthMiddleware)      # added second → runs second
app.add_middleware(CORSMiddleware)      # added last → runs first (outermost)
```

Request flow: `CORSMiddleware → AuthMiddleware → LoggingMiddleware → endpoint`

Think of it like a stack of pancakes — the last one you placed is on top.

---

## 6. Built-in Middleware

FastAPI/Starlette ships several ready-made middleware:

### CORS (Cross-Origin Resource Sharing)
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://myapp.com"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    allow_credentials=True,
)
```

Without this, browsers block API calls from a different origin (e.g. React frontend at `localhost:3000` calling FastAPI at `localhost:8000`).

### GZip
```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
# Compresses responses larger than 1000 bytes if client accepts gzip
```

### TrustedHost
```python
from starlette.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["myapi.com", "*.myapi.com", "localhost"],
)
# Returns 400 for requests with unexpected Host headers
```

---

## 7. Request Logging Middleware

A production-useful middleware that logs every request:

```python
import logging
import time
import uuid

logger = logging.getLogger("api")

@app.middleware("http")
async def request_logger(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    logger.info(
        "[%s] → %s %s",
        request_id, request.method, request.url.path,
    )

    response = await call_next(request)

    duration = (time.perf_counter() - start) * 1000
    logger.info(
        "[%s] ← %s %s | %d | %.1fms",
        request_id, request.method, request.url.path,
        response.status_code, duration,
    )

    response.headers["X-Request-ID"] = request_id
    return response
```

Sample console output:
```
[a3f1b2c4] → GET /users/5
[a3f1b2c4] ← GET /users/5 | 200 | 4.2ms
```

---

## 8. Reading the Request Body in Middleware

`call_next` consumes the body. If you need to read it in middleware (e.g. for logging), you must buffer it:

```python
@app.middleware("http")
async def log_body(request: Request, call_next):
    body = await request.body()   # read and buffer
    
    # Re-inject the body so the endpoint can also read it
    async def receive():
        return {"type": "http.request", "body": body}
    request._receive = receive

    response = await call_next(request)
    return response
```

> ⚠️ Reading the body in middleware adds latency. Only do it when necessary (e.g. audit logging).

---

## 9. Adding Security Headers via Middleware

A common production pattern — add security headers to every response:

```python
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

These four headers cover the most common web security hygiene requirements.

---

## 10. Middleware vs Exception Handlers

Exception handlers (from Lesson 12) run **inside** the middleware stack. If middleware wraps the call in a `try/except`, it catches errors before the exception handler:

```python
@app.middleware("http")
async def catch_everything(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.critical("Unhandled in middleware: %s", exc)
        return JSONResponse({"detail": "Server error"}, status_code=500)
```

Usually let `@app.exception_handler` do this work. Middleware-level catching is rare.

---

## 11. Real-World Use Case — API Key Middleware

```python
API_KEYS = {"key-abc-123", "key-xyz-789"}
PUBLIC_PATHS = {"/docs", "/openapi.json", "/redoc", "/health"}

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    # Skip public paths
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    if api_key not in API_KEYS:
        return JSONResponse(
            {"detail": "Invalid or missing API key"},
            status_code=401,
        )

    return await call_next(request)
```

Every endpoint is protected with zero per-route boilerplate. `/docs` stays accessible for development.

---

## 12. Mini Task

Open `main.py`:

1. Run: `uvicorn main:app --reload`
2. In `/docs`:
   - Hit any endpoint → check response headers for `X-Request-ID` and `X-Process-Time`
   - Check the console for request log lines
3. Try calling from a browser (or Swagger UI acts as the origin) — notice CORS headers in the response
4. Hit `GET /items` — observe the security headers (`X-Frame-Options`, etc.)
5. **Bonus:** Write a middleware that rejects requests whose `Content-Type` is not `application/json` for POST/PUT/PATCH routes (skip GET and DELETE).

---

## 13. Key Takeaways

- Middleware wraps **every** request — including 404s and unmatched routes.
- Use `@app.middleware("http")` for simple cases; `BaseHTTPMiddleware` for configurable ones.
- **Stack order:** last `add_middleware` call runs first (outermost layer).
- Built-ins: `CORSMiddleware`, `GZipMiddleware`, `TrustedHostMiddleware`.
- Add security headers (`X-Frame-Options`, `HSTS`, etc.) in one place, apply everywhere.
- Middleware sees **both** request and response; `Depends()` only sees the request.

---

## ➡️ Next Lesson

**Lesson 16 — Routers (APIRouter)**
- Splitting one big `main.py` into multiple files
- `APIRouter` with prefixes and tags
- Including routers in the main app
- Nested routers
