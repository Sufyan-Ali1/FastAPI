"""
Lesson 53 - Monitoring & Observability
--------------------------------------
A dependency-free demo of:

    - liveness vs readiness health checks (what orchestrators poll)
    - a /metrics endpoint in REAL Prometheus exposition format, populated by a
      middleware that counts requests (by method/path/status) and times them

In production you'd use `prometheus_client` (or prometheus-fastapi-instrumentator)
to generate /metrics, plus Sentry for errors and OpenTelemetry for traces (see
theory.md). This builds a minimal version by hand to show the format.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload
"""

import time
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Lesson 53 - Observability")

# --- in-memory metric stores (a real app uses prometheus_client) -----------
# Counter: total requests, keyed by (method, path, status).
request_counter: dict[tuple, int] = defaultdict(int)
# Histogram-ish: total request time + count, keyed by (method, path).
latency_sum: dict[tuple, float] = defaultdict(float)
latency_count: dict[tuple, int] = defaultdict(int)

# A togglable dependency-health flag for the readiness demo.
_deps = {"database_up": True}


# ---------------------------------------------------------------------------
# Metrics middleware: count every request and record its duration.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    # Use the route template (e.g. /items/{id}) not the raw path, so /items/1
    # and /items/2 aggregate together (low cardinality).
    route = request.scope.get("route")
    path = route.path if route else request.url.path
    if path != "/metrics":  # don't count scrapes of the metrics endpoint itself
        key = (request.method, path)
        request_counter[(request.method, path, response.status_code)] += 1
        latency_sum[key] += duration
        latency_count[key] += 1
    return response


# ---------------------------------------------------------------------------
# HEALTH CHECKS - liveness vs readiness
# ---------------------------------------------------------------------------
@app.get("/health/live")
def liveness():
    # Cheap: is the process up at all? (Failing this -> restart the container.)
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    # Checks dependencies: can we actually serve traffic right now?
    # (Failing this -> stop routing traffic, but do NOT restart.)
    if not _deps["database_up"]:
        raise HTTPException(503, "database unavailable")
    return {"status": "ready"}


@app.post("/toggle-db")
def toggle_db():
    # Demo helper: flip the simulated database health to see readiness change.
    _deps["database_up"] = not _deps["database_up"]
    return {"database_up": _deps["database_up"]}


# ---------------------------------------------------------------------------
# Some ordinary endpoints to generate metrics.
# ---------------------------------------------------------------------------
ITEMS = {1: {"id": 1, "name": "Widget"}}


@app.get("/items/{item_id}")
def get_item(item_id: int):
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    return item


# ---------------------------------------------------------------------------
# /metrics - Prometheus exposition format (text). Prometheus scrapes this.
# ---------------------------------------------------------------------------
@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    lines = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
    ]
    for (method, path, status), count in sorted(request_counter.items(), key=str):
        lines.append(
            f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
        )
    lines += [
        "# HELP http_request_duration_seconds Request duration",
        "# TYPE http_request_duration_seconds summary",
    ]
    for (method, path), total in sorted(latency_sum.items(), key=str):
        n = latency_count[(method, path)]
        lines.append(
            f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total:.6f}'
        )
        lines.append(
            f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {n}'
        )
    return "\n".join(lines) + "\n"
