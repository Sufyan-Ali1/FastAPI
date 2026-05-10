"""
Lesson 15 — Middleware
-----------------------
Demonstrates:
  - @app.middleware("http") decorator style
  - Request/response timing + X-Process-Time header
  - Request ID generation + logging
  - Security headers middleware
  - API key protection (whitelist public paths)
  - CORS middleware (built-in)
  - GZip middleware (built-in)
  - BaseHTTPMiddleware (class-based, configurable)
  - Execution order — last added = outermost

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
    Check response headers: X-Request-ID, X-Process-Time, X-Frame-Options, etc.
    Check console for request log lines.
"""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ── Logging setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lesson15")

app = FastAPI(title="Lesson 15 - Middleware")


# ============================================================
# Built-in middleware (registered with add_middleware)
# These run OUTERMOST because they're added first.
# ============================================================

# CORS — allows browsers from other origins to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# GZip — compress large responses automatically
app.add_middleware(GZipMiddleware, minimum_size=500)


# ============================================================
# Class-based middleware — API key protection
# ============================================================

PUBLIC_PATHS = {"/docs", "/openapi.json", "/redoc", "/health", "/public"}
VALID_API_KEYS = {"dev-key-123", "prod-key-xyz"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Requires X-API-Key header on all non-public paths."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if api_key not in VALID_API_KEYS:
            return JSONResponse(
                {"success": False, "detail": "Invalid or missing X-API-Key header"},
                status_code=401,
            )
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)


# ============================================================
# Decorator-style middleware — runs innermost (added last via decorator)
# ============================================================

@app.middleware("http")
async def request_logger(request: Request, call_next):
    """Logs every request with a unique ID and response time."""
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    logger.info("[%s] → %s %s", request_id, request.method, request.url.path)

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "[%s] ← %s %s | %d | %.1fms",
        request_id, request.method, request.url.path,
        response.status_code, duration_ms,
    )

    # Attach metadata headers to every response
    response.headers["X-Request-ID"]    = request_id
    response.headers["X-Process-Time"]  = f"{duration_ms:.2f}ms"
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Adds standard security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"]    = "nosniff"
    response.headers["X-Frame-Options"]            = "DENY"
    response.headers["X-XSS-Protection"]           = "1; mode=block"
    response.headers["Referrer-Policy"]            = "strict-origin-when-cross-origin"
    return response


# ============================================================
# Endpoints
# ============================================================

@app.get("/health")
def health():
    """Public — no API key required (in PUBLIC_PATHS)."""
    return {"status": "ok"}


@app.get("/public")
def public_info():
    """Another public endpoint."""
    return {"message": "No API key needed here"}


@app.get("/items")
def list_items():
    """
    Protected — requires X-API-Key header.
    Try with: X-API-Key: dev-key-123
    """
    return {
        "items": [
            {"id": 1, "name": "Laptop"},
            {"id": 2, "name": "Monitor"},
        ]
    }


@app.get("/slow")
async def slow_endpoint():
    """
    Simulates a slow response.
    Check X-Process-Time header to see the measured duration.
    """
    import asyncio
    await asyncio.sleep(0.2)
    return {"message": "That took a moment"}


@app.get("/large-response")
def large_response():
    """
    Returns a large payload — GZipMiddleware will compress it
    if the client sends 'Accept-Encoding: gzip'.
    """
    return {"data": ["item"] * 500}
