# Lesson 46 — Logging

> **Goal of this lesson:** Replace `print()` debugging with real **logging**. Learn Python's logging levels, **structured (JSON) logging** so machines can parse your logs, **request-ID tracing** to correlate every log line of a single request, and what you must **never** log. Meet the production tools **`structlog`** and **`loguru`**.
>
> `main.py` is dependency-free: stdlib `logging` with a JSON formatter and a request-ID middleware, so it runs anywhere. `structlog`/`loguru` are covered as the tools that automate this.

---

## 1. The Problem — `print()` Doesn't Scale

You've probably debugged with `print()`. In production it falls apart:

- **No levels** — you can't separate "routine info" from "critical error."
- **No control** — you can't turn it down in prod and up when debugging.
- **No structure** — plain text is hard for log systems to search or filter.
- **No context** — which request produced this line? Impossible to tell under load.
- **Wrong destination** — `print` goes to stdout only; logs may need files, aggregators, alerting.

**Logging** is the disciplined replacement: leveled, configurable, structured, and routable.

> 🔑 `print()` is for scripts; **logging** is for applications. The moment code runs unattended in production, you need levels, structure, and context — not `print`.

---

## 2. Python's `logging` Basics

The standard library `logging` module has four concepts:

| Concept | Role |
|---|---|
| **Logger** | What you call: `logger.info(...)`. Named (usually per module). |
| **Level** | The severity of a message (DEBUG … CRITICAL). |
| **Handler** | *Where* logs go (console, file, network). |
| **Formatter** | *How* logs look (plain text, JSON). |

```python
import logging

logger = logging.getLogger("myapp")     # get a named logger
logger.info("User logged in")           # emit at INFO level
logger.warning("Cache miss for key %s", key)
logger.error("Payment failed", exc_info=True)   # include the traceback
```

You configure handlers/formatters **once** at startup; then every module just does `logging.getLogger(__name__)` and logs.

---

## 3. Log Levels — Say How Important It Is

Every message has a **level**. You set a threshold; anything below it is dropped. This lets you run **INFO** in production and **DEBUG** while investigating — no code changes.

| Level | Use for | Example |
|---|---|---|
| **DEBUG** | Detailed diagnostics (dev only) | "Query returned 42 rows" |
| **INFO** | Normal, noteworthy events | "Order 123 created" |
| **WARNING** | Something unexpected but handled | "Retrying after timeout" |
| **ERROR** | A failure in the current operation | "Payment gateway rejected charge" |
| **CRITICAL** | The app/service is in danger | "Database unreachable" |

```python
logging.basicConfig(level=logging.INFO)   # INFO and above are shown; DEBUG hidden
```

> 🔑 Pick the **right level** for each message. Production usually runs at **INFO**; drop to **DEBUG** temporarily to investigate. Logging everything at one level defeats the purpose.

---

## 4. Structured (JSON) Logging

A human reads `"User alice logged in from 1.2.3.4"`. A **log system** (Elasticsearch, Datadog, CloudWatch, Loki) needs to **search and filter** — "show all ERRORs for user alice in the last hour." That requires **structured** logs: each entry is a JSON object with fields, not a sentence.

```
Plain:   2026-07-21 10:00:00 INFO User alice logged in from 1.2.3.4

JSON:    {"timestamp":"2026-07-21T10:00:00Z","level":"INFO",
          "event":"user.login","user":"alice","ip":"1.2.3.4"}
```

Now a log platform can query `level=ERROR AND user=alice` instantly. You produce JSON by attaching a **JSON formatter** to your handler (stdlib can do this with a custom formatter; `structlog`/`loguru` do it out of the box).

| | Plain text logs | Structured (JSON) logs |
|---|---|---|
| Human reading one line | Easy | Slightly noisier |
| Machine search/filter/aggregate | Hard (regex parsing) | **Easy** (query by field) |
| Production log platforms | Poor fit | **Standard** |

> 🔑 In production, log **structured JSON** with fields, not sentences — so your log aggregator can search, filter, and alert on them. Human-readable text is fine for local dev.

---

## 5. `structlog` and `loguru` — The Production Tools

Stdlib `logging` can do structured logs, but it's verbose to set up. Two libraries make it pleasant:

**`structlog`** — the standard for structured logging. You log with **key/value context**, and it renders JSON (or pretty console output in dev):

```python
import structlog
log = structlog.get_logger()
log.info("user.login", user="alice", ip="1.2.3.4")   # -> JSON with those fields
```

**`loguru`** — an ergonomic, batteries-included logger (one import, great defaults, easy file rotation, colored dev output):

```python
from loguru import logger
logger.info("Order {id} created", id=123)
logger.add("app.log", rotation="10 MB", serialize=True)   # JSON to a rotating file
```

| | `structlog` | `loguru` |
|---|---|---|
| Focus | First-class **structured** logging | Ease of use, great defaults |
| Style | Key/value context, processor pipeline | Simple, print-like API |
| Setup | Some configuration | Almost none |
| Best for | Serious structured logging at scale | Quick, pleasant logging |

> 💡 Use **`structlog`** when structured logging is central (most production APIs). Use **`loguru`** when you want great logging with near-zero setup. Both beat raw stdlib for ergonomics — but the *concepts* (levels, JSON, context) are identical, which is why this lesson teaches them with stdlib.

---

## 6. Request-ID Tracing — Correlating a Request's Logs

Under load, hundreds of requests interleave their log lines. When one fails, you need **every log line for that one request** — not the whole haystack. The solution: give each request a unique **request ID**, attach it to every log line produced during that request, and (optionally) return it in a response header.

```
Request A (id=abc):  abc  INFO  request.start   GET /orders
                     abc  INFO  db.query        orders table
                     abc  ERROR payment.failed  gateway timeout
Request B (id=xyz):  xyz  INFO  request.start   GET /items
```

Filtering logs by `request_id=abc` shows the complete story of that one request, in order — the single most useful debugging tool in a busy service.

### How: `contextvars` + middleware

A **`ContextVar`** holds the current request's ID, safe across async tasks. Middleware (Lesson 15) generates an ID per request, stores it in the context var, and the log formatter reads it into every record:

```python
import contextvars, uuid
request_id_var = contextvars.ContextVar("request_id", default="-")

@app.middleware("http")
async def add_request_id(request, call_next):
    request_id_var.set(str(uuid.uuid4())[:8])   # unique per request
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id_var.get()
    return response
```

The formatter then injects `request_id_var.get()` into each log record — so **every** log line during that request carries the same ID automatically.

> 🔑 A **request ID** stored in a `ContextVar` and injected by the log formatter ties together all logs of one request. Accept an incoming `X-Request-ID` (from a gateway) or generate one, and return it so clients/support can quote it.

---

## 7. A Logging Middleware

Beyond the ID, a request-logging middleware records the **lifecycle** of each request — a start line, and an end line with **status code and duration**:

```python
@app.middleware("http")
async def log_requests(request, call_next):
    start = time.perf_counter()
    logger.info("request.start", extra={"method": request.method, "path": request.url.path})
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("request.end", extra={"status": response.status_code,
                                      "duration_ms": round(duration_ms, 1)})
    return response
```

Now every request produces a consistent, structured start/end pair with timing — invaluable for spotting slow endpoints and error spikes.

---

## 8. What to Log — and What NEVER to Log

Logs often end up in systems many people can read, and they persist. **Never log secrets or sensitive data:**

| ✅ Log | ❌ NEVER log |
|---|---|
| Events (login, order created), IDs | **Passwords** (even hashed) |
| Method, path, status, duration | **Tokens / API keys / session ids** |
| Error types and stack traces | Full **credit-card / bank** numbers |
| User **id** (not full PII) | **Personal data** (SSNs, health, addresses) beyond need |
| Request ID for correlation | Raw request bodies containing the above |

Leaking a token or password into logs is a real breach — logs are backed up, shipped to third-party platforms, and read widely.

> ⚠️ Treat logs as **semi-public and permanent.** Log enough to debug (events, ids, timings, errors) and **nothing sensitive** (passwords, tokens, card numbers, PII). Redact or omit — a logged secret is a leaked secret.

---

## 9. Logging vs Observability

Logging is one pillar of **observability** (understanding a running system). The others — **metrics** (numbers over time: request rate, error rate, latency) and **traces** (a request's path across services) — are Lesson 53. Logs answer "**what happened** in this request?"; metrics answer "how is the system doing overall?"; traces answer "where did the time go across services?"

> 💡 Good logs are the foundation; add metrics and tracing (Lesson 53) as the system grows. Don't try to replace metrics with log-counting — each tool has its job.

---

## 10. Real-World Use Case — Debugging a Production Error

A customer reports "my order failed at 2:47pm." With good logging:

- Support asks for (or looks up) the **request ID** — returned in the `X-Request-ID` header the customer's client received.
- You filter your log platform to `request_id=abc123` and instantly see **that request's** full story: `request.start` → auth ok → `db.query` → `payment.failed: gateway timeout` → `request.end status=502 duration_ms=8100`.
- The structured fields let you also query "how many `payment.failed` events in the last hour, by gateway?" to see if it's systemic.
- No secrets appear in any of it, so the logs were safe to ship to your aggregator.

That five-minute diagnosis — impossible with `print` — is what production logging buys you.

---

## 11. Mini Task

`main.py` is a dependency-free structured-logging app.

1. Run: `uvicorn main:app --reload` (watch the console) or hit it with `curl`.
2. Make a few requests and observe each log line is **JSON** with a **`request_id`**, `level`, `event`, and timing.
3. Note that all log lines for one request share the **same `request_id`**, and the response carries an **`X-Request-ID`** header.
4. Hit `/error` and see an **ERROR**-level log with a stack trace — tied to its request ID.
5. Hit `/debug-only` and confirm its DEBUG line is hidden at INFO level; then lower the level and see it appear.
6. **Experiment:**
   - Add a field (e.g. `user_id`) to a log call and see it in the JSON.
   - Accept an incoming `X-Request-ID` header and reuse it instead of generating one.
   - Try to log a "password" field, then **remove it** — practice the never-log rule.
7. **Bonus:** Swap the stdlib setup for `structlog` (or `loguru`) and confirm the concepts (levels, JSON, request-id context) are identical.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Using `print()` in application code | Use `logging` with levels and structure. |
| Logging everything at one level | Use DEBUG/INFO/WARNING/ERROR appropriately. |
| Plain-text logs in production | Emit structured JSON for your log platform. |
| No request correlation | Add a request ID via `ContextVar` + middleware. |
| Logging secrets / tokens / PII | Never log them; redact or omit. |
| Configuring logging per-module | Configure once at startup; get named loggers everywhere. |
| Swallowing exceptions without logging | Log errors with `exc_info=True` (stack trace). |

---

## 13. Key Takeaways

- Replace `print()` with **logging**: leveled, configurable, structured, routable.
- **Levels** (DEBUG→CRITICAL) let you run INFO in prod and DEBUG when debugging — no code change.
- **Structured (JSON) logs** with fields let log platforms **search, filter, and alert**; plain text is dev-only.
- **`structlog`** (structured-first) and **`loguru`** (ergonomic) are the production tools; the concepts are the same as stdlib.
- **Request-ID tracing** via a `ContextVar` + middleware ties all of one request's log lines together; return it as `X-Request-ID`.
- A **request-logging middleware** records method/path/status/duration per request.
- **Never log secrets, tokens, card numbers, or PII** — treat logs as semi-public and permanent.
- Logging is one pillar of **observability** (with metrics and traces — Lesson 53).

---

## ➡️ Next Lesson

**Lesson 47 — Security Best Practices**
- HTTPS, secure headers, input sanitization
- SQL injection prevention
- Secret management in production
