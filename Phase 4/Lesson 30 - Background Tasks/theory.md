# Lesson 30 — Background Tasks

> **Goal of this lesson:** Learn to do work **after** the response is sent, so slow side-effects don't make the client wait. Use FastAPI's built-in **`BackgroundTasks`**, understand exactly how and when it runs, its real limitations, and — crucially — **when to reach for a real task queue** like Celery / RQ / ARQ instead.
>
> `main.py` is a runnable app whose background tasks record what they did (and when) so you can *see* that they run after the response.

---

## 1. The Problem

Some work triggered by a request doesn't need to finish before you answer the client:

- Sending a welcome/confirmation **email** after signup.
- Writing an **audit log** entry.
- Generating a **thumbnail** or processing an uploaded file.
- Sending a **notification** or webhook to another service.

If you do these *inside* the endpoint, the client waits for all of it before getting a response. Sending an email might take 2 seconds — why make the user's signup request hang for 2 seconds when the account is already created?

The fix: **respond immediately, do the slow work afterward.** That's a background task.

```
Without background task:   create user → send email (2s) → respond   (client waits ~2s)
With background task:      create user → respond           (client waits ~50ms)
                                          └─► send email (2s)  (runs after response)
```

---

## 2. FastAPI's Built-in `BackgroundTasks`

FastAPI gives you this for free — no extra library. You declare a `BackgroundTasks` parameter and call `.add_task(...)`:

```python
from fastapi import BackgroundTasks

def send_welcome_email(email: str):
    # slow work: connect to SMTP, send, etc.
    ...

@app.post("/signup")
def signup(email: str, background_tasks: BackgroundTasks):
    # ... create the user ...
    background_tasks.add_task(send_welcome_email, email)
    return {"message": "Signed up"}      # <-- returned NOW; email sends after
```

- FastAPI **injects** the `BackgroundTasks` object (it's a special parameter, like `Response`).
- **`add_task(func, *args, **kwargs)`** queues a function to run *after* the response is sent.
- The endpoint returns immediately; the queued task runs once the response has gone out.

> 🔑 `add_task` **schedules**, it does not run. The function runs after your endpoint returns and the response is delivered — the client isn't kept waiting for it.

---

## 3. How It Works — The Timing

The order is precise and worth internalizing:

1. Your endpoint function runs and **returns a value**.
2. FastAPI builds and **sends the response** to the client.
3. **Then** the queued background task(s) execute, in the **same process**.

So the client gets its answer first; the task runs slightly after. In `main.py`, each task appends an entry (with a timestamp) to an in-memory log, and the response is sent before those entries appear — you can confirm via `GET /logs`.

> ⚠️ Because tasks run **in the same process** as your web server, a very slow or heavy task still consumes that server's resources — it just doesn't delay *this* response. It can delay *other* work on the same worker. (More in §7.)

---

## 4. Multiple Tasks and Arguments

You can queue several tasks; they run **in the order added**. Each can take arguments:

```python
@app.post("/orders")
def create_order(order: OrderCreate, background_tasks: BackgroundTasks):
    saved = save_order(order)
    background_tasks.add_task(write_audit, action="order.created", order_id=saved.id)
    background_tasks.add_task(send_receipt_email, saved.customer_email, saved.id)
    background_tasks.add_task(notify_warehouse, saved.id)
    return saved      # response goes out, then the 3 tasks run in order
```

Arguments are captured when you call `add_task` and passed to the function when it runs.

---

## 5. Adding Tasks From Dependencies

`BackgroundTasks` also works inside **dependencies** (Lesson 14). A dependency can add a task, and it still runs after the response. This is handy for cross-cutting concerns like request logging:

```python
def audit_dependency(background_tasks: BackgroundTasks):
    background_tasks.add_task(write_request_log, "endpoint accessed")

@app.get("/things", dependencies=[Depends(audit_dependency)])
def list_things():
    return [...]
```

All tasks added across the endpoint **and** its dependencies are collected and run together after the response.

---

## 6. Sync vs Async Task Functions

This ties directly to Lesson 28. A background task function can be `def` or `async def`, and FastAPI treats them the same way it treats endpoints:

| Task function | Runs... |
|---|---|
| `def send_email(...)` | In a **threadpool** thread (blocking is fine) |
| `async def send_email(...)` | On the **event loop** (must not block — `await` its I/O) |

> 🔑 The Lesson 28 rule still applies: if your background task does blocking work, make it a plain `def` (threadpool), or if it's `async def`, only do awaitable work inside it. Don't block the event loop from a background task either.

---

## 7. The Limitations of `BackgroundTasks`

`BackgroundTasks` is simple and great for light work — but be clear about what it is **not**. It runs in your web server process, tied to the request that created it.

| Limitation | Consequence |
|---|---|
| **Same process** as the API | Heavy/long tasks compete for the web server's resources |
| **Not durable** | If the server crashes/restarts before the task runs, the task is **lost** |
| **No retries** | If the task raises, it just fails — no automatic retry |
| **No scheduling** | Can't say "run in 1 hour" or "every night at 2am" |
| **No visibility** | No dashboard, no way to inspect/cancel a queued task |
| **Doesn't scale out** | Can't distribute work across multiple worker machines |
| **Bounded by one request's lifecycle** | Not meant for minutes-long jobs |

> 🔑 `BackgroundTasks` is **fire-and-forget, best-effort, in-process.** Perfect for "send this email, write this log" where an occasional loss is tolerable. Wrong for anything that **must** happen, must retry, must be scheduled, or is heavy.

---

## 8. When to Use a Real Task Queue (Celery / RQ / ARQ)

When background work must be **durable, retryable, scheduled, heavy, or distributed**, you graduate to a dedicated **task queue**. The architecture changes: tasks go into a **broker** (usually Redis or RabbitMQ), and separate **worker** processes pull and run them — independent of your web server.

```
BackgroundTasks (in-process):
   [ FastAPI worker ] ── runs task itself, after the response

Task queue (out-of-process):
   [ FastAPI worker ] ──push job──► [ Broker: Redis/RabbitMQ ] ──► [ Worker 1 ]
                                                                 └► [ Worker 2 ]
   (API and workers are separate processes, scaled independently)
```

The main Python options:

| Tool | Style | Broker | Notes |
|---|---|---|---|
| **Celery** | Sync (mature, heavyweight) | Redis / RabbitMQ | The industry standard; huge feature set, scheduling (Celery Beat), retries, monitoring (Flower) |
| **RQ** (Redis Queue) | Sync (simple) | Redis | Much simpler than Celery; great for straightforward job queues |
| **ARQ** | **Async** | Redis | Async-native, pairs naturally with async FastAPI |
| **Dramatiq** | Sync | Redis / RabbitMQ | A simpler, modern Celery alternative |

What a task queue gives you that `BackgroundTasks` can't:

- **Durability** — jobs persist in the broker; a server restart doesn't lose them.
- **Retries** — automatic retry with backoff on failure.
- **Scheduling** — delayed and periodic jobs (e.g. Celery Beat).
- **Scaling** — add worker machines to process more jobs in parallel.
- **Monitoring** — dashboards to see queued/running/failed jobs.
- **Isolation** — heavy jobs run on workers, never touching web-server resources.

> 🔑 The decision rule: **can you tolerate losing this task if the process dies, and is it quick and lightweight?** Yes → `BackgroundTasks`. No (must run, must retry, must schedule, or is heavy) → a task queue. Setting up Celery/RQ/ARQ is beyond this lesson's scope; the goal here is knowing **which tool the job needs.**

---

## 9. Decision Guide

| Your task is... | Use |
|---|---|
| Quick email / notification / log, loss-tolerant | **`BackgroundTasks`** |
| Writing an audit entry after a request | **`BackgroundTasks`** |
| A job that **must** complete (payment capture, order fulfilment) | **Task queue** |
| Needs **retries** on failure | **Task queue** |
| **Scheduled** or recurring (nightly report, reminders) | **Task queue** (or a scheduler) |
| **Heavy/CPU-bound** or long-running (video encode, ML) | **Task queue** (separate workers) |
| Must **scale across machines** | **Task queue** |

---

## 10. Real-World Use Case — Signup and Order Flows

**Signup** (`main.py`): creating the account is the important part and finishes fast; the welcome email is a nice-to-have. Respond `201` immediately and queue the email as a `BackgroundTasks` — if it occasionally fails, the user is still signed up and you can re-send later. Perfect fit.

**Order payment**: capturing a payment and fulfilling an order **must** happen and must retry if the payment gateway hiccups. This is **not** a `BackgroundTasks` job — a lost task means a paid order that never ships. This belongs in a **task queue** with durability and retries.

Same app, two kinds of "background" work, two different tools — chosen by whether the work is allowed to be lost.

---

## 11. Mini Task

`main.py` demonstrates `BackgroundTasks` with tasks that record what they did.

1. Run: `uvicorn main:app --reload` → open `/docs`.
2. `POST /signup` with an email → you get an **immediate** response.
3. `GET /logs` → see the background entries (welcome email + audit) that ran **after** the signup response.
4. `POST /orders` → then `GET /logs` again → see three ordered task entries (audit, receipt, warehouse).
5. Notice the response returns instantly even though the tasks include a simulated delay.
6. **Experiment:**
   - Make a task `raise` an exception and observe that the response still succeeded but the task silently failed (no retry) — this is the "not durable / no retry" limitation.
   - Add a fourth task to `/orders` and confirm it runs last (order is preserved).
7. **Bonus:** Add a background task inside a dependency (`Depends`) that logs every request to a specific router, and confirm it also runs after the response.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Using `BackgroundTasks` for work that must not be lost | Use a durable task queue (Celery/RQ/ARQ). |
| Putting heavy/CPU-bound jobs in `BackgroundTasks` | They tie up the web server; offload to workers. |
| Expecting retries or scheduling from `BackgroundTasks` | It has neither; use a task queue. |
| Blocking the event loop in an `async def` task | Same Lesson 28 rule: `def` for blocking work. |
| Calling the task function instead of passing it | `add_task(func, arg)` — pass the function and its args, don't call it. |
| Assuming the task ran before the response | It runs **after** the response is sent. |

---

## 13. Key Takeaways

- **Background tasks** let you respond immediately and do slow side-effects afterward.
- FastAPI's **`BackgroundTasks`**: inject it, `add_task(func, *args)`; tasks run **after** the response, **in the same process**, in the order added.
- Tasks can be `def` (threadpool) or `async def` (event loop) — the Lesson 28 blocking rules still apply.
- Tasks can be added from **dependencies**, not just endpoints.
- `BackgroundTasks` is **fire-and-forget, best-effort, in-process**: no durability, retries, scheduling, or scaling.
- Graduate to a **task queue (Celery / RQ / ARQ)** when work must be durable, retryable, scheduled, heavy, or distributed — jobs go to a **broker**, run by separate **worker** processes.
- Decision rule: **loss-tolerant + light → `BackgroundTasks`; must-run / heavy / scheduled → task queue.**

---

## ➡️ Next Lesson

**Lesson 31 — WebSockets**
- Real-time, two-way communication over a persistent connection
- The connection manager pattern
- Broadcasting to many clients
