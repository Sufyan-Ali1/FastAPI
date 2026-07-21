# Lesson 53 — Monitoring & Observability

> **Goal of this lesson:** Know what your running app is doing. Learn **health check endpoints** (liveness vs readiness), **metrics** with **Prometheus + Grafana**, **error tracking** with **Sentry**, and distributed **tracing** with **OpenTelemetry** — the tools that turn a black-box production app into an observable one.
>
> `main.py` is dependency-free: liveness/readiness health checks and a real Prometheus-format **`/metrics`** endpoint. Sentry and OpenTelemetry are covered as the tools you add for errors and traces.

---

## 1. The Problem — Is It Even Working?

Your app is deployed. Now: Is it up? Is it *healthy* (can it reach its database)? Which endpoints are slow? How many errors, and why? Under load, is it about to fall over?

Without **observability**, production is a black box — you find out it's broken when a customer complains. Observability is the practice of making a running system's internal state **visible from the outside**, so you can answer those questions in seconds.

> 🔑 **Observability = understanding a running system from its outputs.** You can't fix — or even notice — what you can't see. It's the difference between "a customer told us it's down" and "we were paged before anyone noticed."

---

## 2. The Three Pillars (+ Errors)

Observability rests on three complementary signal types, plus error tracking:

| Pillar | Answers | Tool | Lesson |
|---|---|---|---|
| **Logs** | *What happened* in this request? | structured logging | 46 |
| **Metrics** | *How is the system doing* overall? (rates, latencies) | Prometheus + Grafana | this lesson |
| **Traces** | *Where did the time go* across services? | OpenTelemetry | this lesson |
| **Errors** | *What's crashing, and with what context?* | Sentry | this lesson |

Each answers a different question; you need all of them for a full picture. Logs you already have (Lesson 46) — this lesson adds the rest.

> 🔑 **Logs** (events), **metrics** (aggregate numbers), and **traces** (request paths) are complementary, not redundant. Metrics tell you *something* is slow; traces tell you *where*; logs tell you *why*.

---

## 3. Health Check Endpoints

The most basic observability: an endpoint that answers "are you alive and ready?" Orchestrators (Kubernetes, Cloud Run, load balancers) poll it to decide whether to send traffic or restart the app. There are **two distinct** checks:

| Check | Question | If it fails |
|---|---|---|
| **Liveness** | Is the process alive (not hung/deadlocked)? | Restart the container |
| **Readiness** | Can it serve traffic *right now* (DB reachable, deps ready)? | Stop routing traffic (but don't restart) |

```python
@app.get("/health/live")     # LIVENESS: is the process up? (cheap, no deps)
def live():
    return {"status": "alive"}

@app.get("/health/ready")    # READINESS: can it actually serve? (checks deps)
def ready():
    if not database_is_reachable():
        raise HTTPException(503, "database unavailable")   # -> stop routing traffic
    return {"status": "ready"}
```

The distinction matters: a **liveness** failure means "restart me"; a **readiness** failure means "I'm alive but can't serve yet — don't send me traffic" (e.g. the database is briefly down). Restarting wouldn't help the latter.

> 🔑 **Liveness** = "am I alive?" (restart if not). **Readiness** = "can I serve traffic?" (checks dependencies; stop routing if not). Keep liveness cheap; put dependency checks in readiness.

---

## 4. Metrics — Numbers Over Time

**Metrics** are numeric measurements sampled over time — request rate, error rate, latency, active connections, memory. They answer "how is the system doing?" at a glance and power dashboards and alerts.

The three core metric types:

| Type | Represents | Example |
|---|---|---|
| **Counter** | A value that only goes up | total requests, total errors |
| **Gauge** | A value that goes up and down | in-flight requests, memory usage |
| **Histogram** | Distribution of values | request latency (p50/p95/p99) |

A widely-used framing for API metrics is the **RED method**: **R**ate (requests/sec), **E**rrors (error rate), **D**uration (latency). Track those three per endpoint and you can spot most problems.

> 🔑 Track **Rate, Errors, Duration** (the RED method) per endpoint with **counters** and **histograms**. These three numbers reveal traffic spikes, error surges, and slowdowns instantly.

---

## 5. Prometheus — Scraping Metrics

**Prometheus** is the standard open-source metrics system. Its model is **pull-based**: your app exposes a **`/metrics`** endpoint in a simple text format, and Prometheus **scrapes** it periodically (e.g. every 15s), storing the values as time series.

The **exposition format** is plain text — one metric per line:

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/items",status="200"} 1027
http_requests_total{method="POST",path="/items",status="201"} 88

# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1"} 950
http_request_duration_seconds_sum 42.7
http_request_duration_seconds_count 1115
```

- Each metric has a **name**, optional **labels** (`method`, `path`, `status`) for slicing, and a **value**.
- In Python, the **`prometheus_client`** library (or `prometheus-fastapi-instrumentator`) generates this for you; `main.py` builds a minimal version by hand to show the format.

> 🔑 **Prometheus scrapes** a `/metrics` endpoint your app exposes (pull model), storing metrics as time series you can query. Labels let you slice by endpoint, method, and status.

---

## 6. Grafana — Dashboards & Alerts

Prometheus stores and queries metrics; **Grafana** visualizes them. You build **dashboards** — graphs of request rate, error rate, and latency over time — and configure **alerts** ("page me if the error rate exceeds 5% for 5 minutes").

```
your app  --exposes-->  /metrics  --scraped by-->  Prometheus  --queried by-->  Grafana
                                                        │                          │
                                                        └── alerting ──► notify ◄──┘
```

Grafana + Prometheus is the de-facto open-source monitoring stack: your app exposes metrics, Prometheus collects them, Grafana shows them and alerts on them.

> 💡 **Prometheus collects, Grafana displays and alerts.** Together they turn your `/metrics` endpoint into live dashboards and pages-when-things-break.

---

## 7. Error Tracking — Sentry

Metrics tell you the error *rate*; **Sentry** tells you the error *details*. It captures every exception with full context — stack trace, request data, user, release version — groups duplicates, and alerts you. Integration is a few lines:

```python
import sentry_sdk
sentry_sdk.init(dsn="https://...@sentry.io/...", traces_sample_rate=0.1)
# FastAPI/Starlette integration auto-captures unhandled exceptions
```

Now every unhandled exception is reported to Sentry with the traceback, the request that caused it, and how many users it affected — far better than grepping logs. It's the fastest way to know **what's crashing and why**.

> 🔑 **Sentry** captures exceptions with full context (stack trace, request, release), groups them, and alerts you — turning "errors are happening somewhere" into "this exact bug hit 47 users on line 88." Add it early; it pays for itself the first incident.

---

## 8. Distributed Tracing — OpenTelemetry

In a system of **multiple services** (an API calling other services, a database, a cache), a slow request could be slow *anywhere*. A **trace** follows one request across all of them, recording a **span** (a timed operation) at each hop, so you see exactly where the time went.

**OpenTelemetry (OTel)** is the vendor-neutral standard for generating traces (and metrics/logs). You instrument your app; it emits spans to a backend (Jaeger, Tempo, Datadog, Honeycomb):

```
Trace of one request (total 820ms):
├─ API handler                     [ 820ms ]
│  ├─ auth check                   [  10ms ]
│  ├─ DB query (orders)            [ 120ms ]
│  └─ call pricing service         [ 680ms ] ◄── the bottleneck is HERE
│     └─ pricing DB query          [ 650ms ]
```

That waterfall instantly shows the pricing service (and its DB query) is the culprit — impossible to see from logs alone. Tracing matters most in **microservices**; for a single service, metrics + logs often suffice.

> 🔑 **Tracing** (OpenTelemetry) follows one request across services as a tree of timed **spans**, pinpointing *where* the latency is. Essential for microservices; often optional for a single app.

---

## 9. Alerting — Signals to Notifications

Observability is only useful if someone **acts** on it. **Alerting** turns metrics/errors into notifications (Slack, PagerDuty, email) when thresholds are crossed:

- Error rate > 5% for 5 minutes → page on-call.
- p99 latency > 1s → warn.
- Readiness check failing → alert.
- A new Sentry error affecting many users → notify.

Good alerts are **actionable and rare** — alert on symptoms users feel (errors, latency), not every minor blip, or people learn to ignore them (**alert fatigue**).

> 🔑 Alert on **user-facing symptoms** (errors, latency, downtime), keep alerts **actionable and rare**, and avoid alert fatigue. An ignored alert is worse than no alert.

---

## 10. Real-World Use Case — Catching an Incident Early

Your auction API is live. At 2:47pm a database connection pool starts exhausting:

- **Metrics** (Prometheus/Grafana): p99 latency graph spikes and the error-rate line crosses 5% → an **alert** pages on-call *before* most users notice.
- **Health checks**: the **readiness** endpoint starts returning 503 (DB unreachable) → the load balancer stops routing to the affected instances, and the orchestrator holds off restarting (liveness is still fine).
- **Sentry**: floods with `OperationalError: connection pool exhausted`, grouped, showing the exact query and 200 affected users.
- **Traces** (OTel): a slow request's waterfall shows the time stuck waiting on a DB connection → confirms the pool is the cause.
- **Logs** (Lesson 46): filtered by the request ID, they show the full story of an affected request.

Five signals, one coherent diagnosis, minutes after it started — instead of a customer email an hour later. That's what observability buys.

---

## 11. Mini Task

`main.py` is a dependency-free observability demo.

1. Run: `uvicorn main:app --reload`
2. Check the health endpoints:
   - `GET /health/live` → always `alive` (liveness).
   - `GET /health/ready` → `ready`, or `503` when a dependency is marked down (toggle it via `/toggle-db`).
3. Make several requests, then hit **`GET /metrics`** → see real Prometheus exposition format: `http_requests_total` counters labeled by method/path/status, and latency stats.
4. Cause some 404s and confirm the metrics count them by status label.
5. **Experiment:**
   - Add a gauge for in-flight requests.
   - Reason about liveness vs readiness: which should a hung process fail? Which should a brief DB outage fail?
6. **Bonus (conceptual):** Sketch adding Sentry (`sentry_sdk.init`) and OpenTelemetry instrumentation, and which questions each would answer that metrics alone can't.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| One health check for everything | Separate **liveness** (restart) from **readiness** (route traffic). |
| Readiness check that's expensive/slow | Keep it fast; check only critical dependencies. |
| Metrics without labels | Label by method/path/status to slice by endpoint. |
| Relying only on logs | Add metrics (aggregate view) and error tracking (grouped errors). |
| No alerting | Metrics you don't alert on won't wake you when it breaks. |
| Too many noisy alerts | Alert on user-facing symptoms; avoid alert fatigue. |
| Tracing a single app you don't need | Traces shine in microservices; don't over-invest early. |

---

## 13. Key Takeaways

- **Observability** makes a running system's state visible so you can answer "is it healthy / slow / erroring?" fast.
- The pillars: **logs** (46, events), **metrics** (aggregate numbers), **traces** (request paths), plus **error tracking** — complementary, not redundant.
- **Health checks**: **liveness** ("am I alive?" → restart) vs **readiness** ("can I serve?" → route traffic); keep liveness cheap, put dependency checks in readiness.
- **Metrics**: counters/gauges/histograms; track **Rate, Errors, Duration** (RED) per endpoint.
- **Prometheus** scrapes a `/metrics` endpoint (pull model, text exposition format); **Grafana** dashboards and alerts on it.
- **Sentry** captures exceptions with full context and groups/alerts on them.
- **OpenTelemetry** traces a request across services as timed **spans** — essential for microservices.
- **Alert** on user-facing symptoms; keep alerts actionable and rare.

---

## ➡️ Next Lesson

**Lesson 54 — API Versioning**
- Why and when to version an API
- `/api/v1`, `/api/v2` strategies
- Evolving an API without breaking clients
