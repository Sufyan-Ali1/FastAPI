"""
Lesson 46 - Logging
-------------------
A dependency-free structured-logging demo using stdlib `logging`:

    - JSON log formatter (structured logs a log platform can search)
    - a request_id stored in a ContextVar, injected into EVERY log line
    - middleware that assigns a request id and logs request start/end + timing
    - the response carries an X-Request-ID header
    - log levels (INFO vs DEBUG) and error logging with a stack trace

structlog / loguru (see theory.md) automate all of this; the concepts are the
same, so we teach them with the standard library here.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Then watch the console as you hit the endpoints.
"""

import contextvars
import json
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request

# A ContextVar holds the current request's id (safe across async tasks).
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


# ---------------------------------------------------------------------------
# JSON formatter - renders each log record as a structured JSON object and
# injects the current request_id from the ContextVar.
# ---------------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),   # correlate lines of one request
            "event": record.getMessage(),
        }
        # Merge any structured fields passed via `extra={...}`.
        for key, value in getattr(record, "context", {}).items():
            entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def log(logger: logging.Logger, level: int, event: str, **fields) -> None:
    """Helper: log an event with structured key/value fields."""
    logger.log(level, event, extra={"context": fields})


# Configure logging ONCE at startup.
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger("app")


app = FastAPI(title="Lesson 46 - Logging")


# ---------------------------------------------------------------------------
# Middleware: assign a request id, log start/end with timing, return the id.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    # Reuse an incoming X-Request-ID (e.g. from a gateway) or generate one.
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    request_id_var.set(rid)

    start = time.perf_counter()
    log(logger, logging.INFO, "request.start",
        method=request.method, path=request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        log(logger, logging.ERROR, "request.failed", path=request.url.path)
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    log(logger, logging.INFO, "request.end",
        status=response.status_code, duration_ms=duration_ms)
    response.headers["X-Request-ID"] = rid
    return response


@app.get("/")
def root():
    log(logger, logging.INFO, "root.accessed")
    return {"message": "See the JSON logs in the console; note the request_id."}


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    # A structured business event with fields - searchable in a log platform.
    log(logger, logging.INFO, "order.fetched", order_id=order_id, user_id=42)
    return {"order_id": order_id, "status": "shipped"}


@app.get("/debug-only")
def debug_only():
    # Hidden at INFO level; appears only if the level is lowered to DEBUG.
    log(logger, logging.DEBUG, "debug.detail", note="only visible at DEBUG level")
    return {"message": "logged a DEBUG line (hidden at INFO)"}


@app.get("/error")
def cause_error():
    try:
        1 / 0
    except ZeroDivisionError:
        # ERROR with a stack trace, tied to this request's id.
        logger.error("computation.failed", exc_info=True,
                     extra={"context": {"operation": "divide"}})
        raise HTTPException(500, "Something went wrong")
