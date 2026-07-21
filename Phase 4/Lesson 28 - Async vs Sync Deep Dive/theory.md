# Lesson 28 — Async vs Sync Deep Dive

> **Goal of this lesson:** Understand *why* the async choices you've been making since Lesson 25 work the way they do. Learn what the **event loop** actually is, the difference between **`async def`** and **`def`** in FastAPI, the one rule that matters — **never block the event loop** — how **`run_in_threadpool`** rescues you when you must call blocking code, and honestly, **when not to use async at all.**
>
> `main.py` is a runnable experiment: it fires concurrent requests at four endpoints doing the same work and times them, so you can *see* the difference instead of taking it on faith.

---

## 1. First, See It For Yourself

`main.py` runs 10 concurrent requests against four endpoints that each do **0.5 seconds** of identical work. Here are real results from running it:

```
endpoint               total wall time   interpretation
------------------------------------------------------------------------
/sync-blocking                  0.55s   threadpool: overlap
/async-blocking                 5.06s   SERIALIZED (blocked loop)
/async-nonblocking              0.58s   awaited: full overlap
/async-offload                  0.57s   offloaded: overlap
```

Same work, same concurrency — but `/async-blocking` took **~9x longer**. If async were "automatically faster," that couldn't happen. This lesson explains exactly why the slow one is slow.

---

## 2. Concurrency vs Parallelism

Two words people mix up. The distinction is the foundation of everything here.

| | **Concurrency** | **Parallelism** |
|---|---|---|
| Idea | Dealing with many things by **interleaving** them | Doing many things **at literally the same instant** |
| Analogy | One chef juggling 5 dishes, switching whenever one is "waiting" (in the oven) | 5 chefs each cooking one dish |
| Needs | One worker that switches tasks while others wait | Multiple workers (CPU cores) |
| Python tool | `async`/`await` (the event loop) | multiple processes / threads |

**Async gives you concurrency, not parallelism.** A single event-loop thread rapidly switches between tasks whenever one is *waiting on I/O*. It never runs two Python operations at the same instant — it just stops wasting time sitting idle during waits.

> 🔑 Async is about **not waiting idly**, not about doing two things at once. It shines when your work is mostly **waiting** (network, database, disk) rather than **computing**.

---

## 3. The Event Loop

An `async` Python program runs on an **event loop**: a single thread that keeps a queue of tasks and runs them **cooperatively**.

```
        ┌──────────────── Event Loop (one thread) ────────────────┐
        │  ready queue: [task A] [task C] ...                      │
        │                                                          │
        │  run task A ──► A hits `await db.query()` ──► A parks,   │
        │                 loop moves on ──► run task C ──► ...      │
        │  when A's I/O is done, A goes back on the ready queue    │
        └──────────────────────────────────────────────────────────┘
```

- The loop runs one task until that task **`await`s** something that isn't ready (an I/O wait).
- At that `await`, the task **yields control** back to the loop, which runs another ready task.
- When the awaited I/O completes, the parked task becomes ready again and resumes.

This is **cooperative multitasking**: tasks must voluntarily yield (via `await`) for others to get a turn. Nobody preempts them.

> 🔑 The whole model depends on tasks **giving up the thread whenever they wait**. A task that never yields — because it's doing blocking work — starves every other task. That's "blocking the event loop."

---

## 4. `async def` vs `def` in FastAPI

FastAPI accepts both kinds of endpoint and runs them on **two different execution paths**:

```python
@app.get("/a")
def sync_endpoint():        # PATH 1: runs in a THREADPOOL
    ...

@app.get("/b")
async def async_endpoint(): # PATH 2: runs ON the event loop
    ...
```

| | `def` (sync) | `async def` (async) |
|---|---|---|
| Where it runs | A **threadpool** thread (offloaded) | Directly on the **event loop** |
| Safe to block? | **Yes** — blocking only ties up its own thread | **No** — blocking freezes the whole loop |
| Must `await` I/O? | No (it's a normal function) | Yes (that's the point) |
| Good for | Sync libraries, sync DB drivers, quick CPU work | Async I/O: async DB, async HTTP, `asyncio.sleep` |

This is the crucial insight most tutorials skip: **FastAPI runs your `def` endpoints in a threadpool.** That's why a plain sync CRUD app (Lessons 22–24) handles concurrent requests fine — each request gets its own thread, so a blocking DB call only blocks *that* thread, not everyone.

> 🔑 FastAPI gives you a safety net: if you write `def`, blocking is fine because you're in a threadpool. If you write `async def`, **you** are responsible for never blocking the loop. Choosing `async def` is a promise to only do non-blocking work.

---

## 5. The One Rule — Never Block the Event Loop

Inside an `async def` endpoint, **every slow operation must be `await`ed** so the loop stays free. Blocking calls break the model:

```python
@app.get("/async-blocking")
async def bad():
    time.sleep(0.5)          # ❌ synchronous - holds the loop for 0.5s
    return {...}

@app.get("/async-nonblocking")
async def good():
    await asyncio.sleep(0.5) # ✅ awaitable - yields the loop for 0.5s
    return {...}
```

In the experiment, `bad()` under 10 concurrent requests took **5.06s** — because while one request sat in `time.sleep`, the single loop thread could do **nothing else**, so all 10 ran one-after-another (10 × 0.5s). `good()` took **0.58s**, because each request yielded the loop during its wait and all 10 overlapped.

**What counts as "blocking" inside `async def`:**

- `time.sleep(...)` (use `await asyncio.sleep(...)`)
- Synchronous DB drivers / sync SQLAlchemy `Session` (use async SQLAlchemy — Lesson 25)
- `requests.get(...)` and other sync HTTP clients (use `httpx.AsyncClient`)
- Reading a large file synchronously, heavy CPU loops, blocking library calls

> 🔑 A single blocking call in one `async def` endpoint degrades throughput for **every** request the server is handling, not just that endpoint. This is the most common and most damaging async mistake.

---

## 6. How `await` Actually Yields

`await` is the point where a coroutine can pause and hand the thread back:

```python
async def handler():
    user = await db.get_user(1)      # park here until the DB responds
    posts = await db.get_posts(1)    # park here until the DB responds
    return {"user": user, "posts": posts}
```

At each `await`, if the awaited thing isn't ready, the coroutine suspends and the loop runs someone else. The function *looks* sequential and synchronous, but it cooperatively releases the thread during every wait. That's the magic: **synchronous-looking code, non-blocking behaviour** — but only for operations that are actually awaitable.

You cannot `await` a normal blocking function. `await time.sleep(1)` is a `TypeError`, which is Python telling you `time.sleep` doesn't cooperate. That's the signal to either use an async equivalent or offload it.

---

## 7. `run_in_threadpool` — Escaping Blocking Code

Sometimes you're in an `async def` but must call something blocking (a sync-only library, a legacy function). Don't call it directly. **Offload it to the threadpool** so the loop stays free:

```python
from fastapi.concurrency import run_in_threadpool

@app.get("/async-offload")
async def handler():
    result = await run_in_threadpool(blocking_work)  # runs on a worker thread
    return {"result": result}
```

`run_in_threadpool` sends the blocking function to a worker thread and gives you back an awaitable, so your `async def` yields the loop while the blocking work happens elsewhere. In the experiment, `/async-offload` finished in **0.57s** — the same as the correct async version — even though it called the exact same blocking `time.sleep`-style function.

| Situation | Do this |
|---|---|
| Blocking call inside `async def` | `await run_in_threadpool(fn, ...)` |
| Whole endpoint is blocking/sync | Just make the endpoint `def` (FastAPI offloads it) |
| An async equivalent exists | Prefer the async library and `await` it |

> 💡 `run_in_threadpool` is the async-side twin of FastAPI's "`def` endpoints run in a threadpool" behaviour. Both move blocking work off the event loop.

---

## 8. CPU-Bound Work — Async Doesn't Help

Async only helps when a task **waits** (I/O). For **CPU-bound** work — hashing, image processing, big number crunching — there's nothing to `await`; the CPU is busy the whole time. Putting CPU work in `async def` just blocks the loop for the entire computation.

```python
@app.get("/cpu-bound")
def cpu_bound(n: int):                 # def -> threadpool, keeps loop free
    return {"checksum": sum(i*i for i in range(n)) % 1_000_000}
```

- A **`def`** endpoint offloads CPU work to a threadpool thread, so it doesn't freeze the loop.
- But threads don't give true parallelism for pure Python CPU work (the GIL). Real CPU parallelism needs **multiple processes** (a process pool, or scaling with multiple worker processes — Lesson 50). That's beyond this lesson; the point here is: **async is the wrong tool for CPU-bound work.**

> 🔑 Async ≠ speed for CPU work. If the bottleneck is the CPU, async does nothing; you need parallelism (processes), not concurrency.

---

## 9. When NOT to Use Async (the honest part)

Async has real costs: harder debugging, `await` everywhere, async-only libraries, and easy-to-introduce blocking bugs. Reach for it deliberately.

**Prefer plain `def` (sync) when:**
- Your app is simple or low/medium traffic — the threadpool handles it fine.
- Your libraries are sync-only (many are) and have no async version.
- The work is CPU-bound (async won't help anyway).
- You or your team are still building async fluency — sync is easier to get right.

**Reach for `async def` when:**
- You're **I/O-bound with high concurrency** — many requests each waiting on DB/network.
- Your stack is already async (async SQLAlchemy, `httpx.AsyncClient`, WebSockets, streaming).
- You're calling multiple slow I/O operations you'd like to overlap.

> 🔑 **Don't cargo-cult async.** FastAPI's threadpool makes sync `def` endpoints genuinely production-grade. The `/sync-blocking` result (0.55s) proves a sync endpoint handled 10 concurrent requests just as well as the async one. Choose async for a *reason*, not by reflex.

---

## 10. The Golden Rules (cheat sheet)

| If your endpoint... | Write it as | Because |
|---|---|---|
| Uses only **async** libraries (`await`) | `async def` | It cooperates with the loop |
| Uses **sync** libraries / sync DB | `def` | FastAPI offloads it to a threadpool |
| Is **CPU-bound** | `def` (or offload to processes) | Async can't help CPU work |
| Is `async def` but must call blocking code | `async def` + `run_in_threadpool` | Keeps the loop free |
| Mixes both | Split the work; never block inside `async def` | One block hurts everyone |

**The single sentence to remember:** *In `async def`, everything slow must be `await`ed; if it can't be, make the endpoint `def` or offload with `run_in_threadpool`.*

---

## 11. Real-World Use Case — Diagnosing a Slow Service

A team reports their FastAPI service "gets slow under load, and making everything `async def` made it worse." What happened:

- They converted endpoints to `async def` but kept calling a **sync** database driver and `requests.get(...)` for an external API.
- Every request now blocked the single event-loop thread during each DB query and HTTP call — exactly the `/async-blocking` scenario. Requests serialized; latency exploded.
- The fix was either (a) revert to `def` (let the threadpool handle the sync calls), or (b) switch to async SQLAlchemy + `httpx.AsyncClient` and `await` them, or (c) wrap the unavoidable sync calls in `run_in_threadpool`.

This is the single most common FastAPI performance bug in the wild — and now you can both explain it and reproduce it with `main.py`.

---

## 12. Mini Task

`main.py` is the runnable experiment.

1. Install: `pip install fastapi uvicorn httpx`
2. Run the built-in load test:
   ```bash
   python main.py
   ```
   Read the timing table. Confirm `/async-blocking` is dramatically slower than the other three.
3. Explore in `/docs` too: `uvicorn main:app --reload`, then hit each endpoint.
4. **Experiment:**
   - Increase `concurrency` in `main.py` from 10 to 30. Watch `/async-blocking` scale linearly (30 × 0.5s ≈ 15s) while the others stay ~0.5s.
   - Change `/async-blocking` to `await asyncio.sleep(...)` and re-run — it should now match the fast group. You just fixed a blocked event loop.
   - Add a new `async def` endpoint that calls the sync `blocking_work()` directly, then a second version using `run_in_threadpool`, and compare their concurrent timings.
5. **Bonus:** Add an endpoint that `await asyncio.gather(...)`s three `asyncio.sleep(0.5)` calls and confirm it finishes in ~0.5s, not 1.5s — overlapping I/O within a single request.

---

## 13. Common Mistakes

| Mistake | Fix |
|---|---|
| `time.sleep()` inside `async def` | `await asyncio.sleep()`; never block the loop. |
| Sync DB driver / `requests` inside `async def` | Use async libraries (async SQLAlchemy, `httpx.AsyncClient`) or `run_in_threadpool`. |
| Assuming `async def` is automatically faster | It's only faster for I/O-bound concurrency; it can be *slower* if you block. |
| CPU-bound work in `async def` | Use `def`, or offload to processes for real parallelism. |
| Making everything `async def` reflexively | Sync `def` runs in a threadpool and is fine for most apps. |
| Forgetting `await` on an async call | The coroutine never runs; you get a coroutine object, not a result. |

---

## 14. Key Takeaways

- Async provides **concurrency** (interleaving during waits), not **parallelism** (simultaneous execution).
- The **event loop** is one thread running tasks cooperatively; tasks must **yield via `await`** for others to run.
- FastAPI runs **`def` endpoints in a threadpool** (blocking is safe) and **`async def` on the event loop** (blocking is forbidden).
- **Never block the event loop.** One blocking call in an `async def` serializes every concurrent request — proven by the 5.06s vs 0.55s result.
- **`await`** is where a coroutine yields the thread during a wait; you can only `await` awaitable (non-blocking) things.
- Use **`run_in_threadpool`** to call unavoidable blocking code from `async def` without freezing the loop.
- Async **doesn't help CPU-bound work** — that needs parallelism (processes).
- **Choose deliberately:** sync `def` is production-grade for most apps; reach for async for high-concurrency I/O-bound workloads.

---

## ➡️ Next Lesson

**Lesson 29 — Authentication & Authorization** (the big Phase 4 security topic)
- Password hashing (`passlib`, `bcrypt`)
- OAuth2 with Password Flow and JWT tokens
- `Depends(get_current_user)` and role-based access control
