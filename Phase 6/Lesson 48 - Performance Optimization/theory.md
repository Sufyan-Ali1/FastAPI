# Lesson 48 — Performance Optimization

> **Goal of this lesson:** Make your API fast — the right way. Learn the **measure-first** mindset, fix the single most common backend performance bug (the **N+1 query problem**), understand **connection pooling** and **async I/O** for throughput, and use **profiling** (`py-spy`) to find real bottlenecks instead of guessing.
>
> `main.py` **counts the actual SQL queries** an endpoint fires, so you can *see* N+1 happen (1 + N queries) and watch eager loading collapse it to a constant.

---

## 1. Measure First — Don't Guess

The cardinal rule of optimization: **measure before you change anything.** Developers waste enormous effort "optimizing" code that isn't the bottleneck. Programs spend most of their time in a small fraction of the code — find *that* with data, not intuition.

> "Premature optimization is the root of all evil." — Donald Knuth

The loop is always: **measure → find the biggest bottleneck → fix it → measure again.** Optimizing without measuring is guessing, and you usually guess wrong.

> 🔑 **Profile first, optimize second.** The slow part is rarely where you think. Change one thing, re-measure, and keep only what actually helped.

---

## 2. The N+1 Query Problem — The #1 ORM Bug

The most common performance killer in database-backed APIs. It happens when you load a list of things, then trigger **one extra query per item** to load a relationship.

```python
authors = db.scalars(select(Author)).all()     # 1 query: get 100 authors
for author in authors:
    print(author.books)                          # +1 query EACH -> 100 more queries!
# Total: 1 + 100 = 101 queries to render one page
```

That's **N+1**: 1 query for the list, plus N queries (one per item) for the relationship. With 100 authors it's 101 queries; with 1000, it's 1001. Each is a round trip to the database — the endpoint crawls.

Why it's sneaky: the ORM makes `author.books` look like a free attribute access, but each one **lazily fires a SQL query**. In a loop, that's death by a thousand queries.

> 🔑 **N+1** = one query for a list + one query per item for a relationship. It's invisible in the code (`author.books` looks innocent) but catastrophic at scale. It's the first thing to check when a list endpoint is slow.

---

## 3. Fixing N+1 — Eager Loading

The fix (previewed in Lesson 25): tell the ORM to load the relationship **up front** in a fixed number of queries, instead of lazily per item. SQLAlchemy calls these **loader options**:

```python
from sqlalchemy.orm import selectinload, joinedload

# selectinload: 1 query for authors + 1 query for ALL their books = 2 total
authors = db.scalars(select(Author).options(selectinload(Author.books))).all()
for author in authors:
    print(author.books)      # already loaded -> NO extra queries

# joinedload: a single query with a JOIN
authors = db.scalars(select(Author).options(joinedload(Author.books))).unique().all()
```

| Loader | How | Best for |
|---|---|---|
| **`selectinload`** | 1 query for parents + 1 `IN` query for children | One-to-many / collections (usually preferred) |
| **`joinedload`** | Single `JOIN` query | Many-to-one / one-to-one; small collections |

Result: **2 queries regardless of N**, instead of N+1. The `main.py` demo counts them — the naive endpoint fires `1 + N`, the eager one fires `2`, no matter how many authors.

> 🔑 Eliminate N+1 with **eager loading** (`selectinload`/`joinedload`). Turn "1 + N queries" into a constant. This is the highest-impact database optimization you'll make.

---

## 4. Connection Pooling

Opening a database connection is expensive (TCP handshake, auth). Doing it per request would be slow — so SQLAlchemy keeps a **pool** of open connections and **reuses** them (Lesson 20). Each request borrows one and returns it.

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,          # keep 10 connections open and ready
    max_overflow=20,       # allow 20 more under burst load (then queue)
    pool_pre_ping=True,    # check a connection is alive before using it
    pool_recycle=1800,     # recycle connections older than 30 min
)
```

| Setting | Meaning |
|---|---|
| `pool_size` | Steady-state open connections |
| `max_overflow` | Extra connections allowed under load |
| `pool_pre_ping` | Test-before-use to avoid stale/dead connections |
| `pool_recycle` | Recycle old connections (DBs drop idle ones) |

Tuning matters: too small a pool queues requests under load; too large overwhelms the database (which has its own connection limit). Size it to your traffic and your database's capacity.

> 🔑 The engine's **connection pool** reuses connections so you don't pay the connect cost per request. Tune `pool_size`/`max_overflow` to your load — not so small it starves, not so large it exhausts the database.

---

## 5. Async I/O for Throughput

For **I/O-bound** work (Lesson 28), async lets one worker handle many concurrent requests by not sitting idle during waits. Within a single request, you can also **overlap** independent I/O with `asyncio.gather` instead of doing it sequentially:

```python
# Sequential: total time = a + b + c
a = await fetch_user()
b = await fetch_orders()
c = await fetch_recommendations()

# Concurrent: total time ≈ max(a, b, c) - they overlap
a, b, c = await asyncio.gather(fetch_user(), fetch_orders(), fetch_recommendations())
```

If three independent calls each take 100ms, `gather` runs them concurrently (~100ms total) instead of sequentially (~300ms). But remember Lesson 28's caveats: async only helps **I/O-bound** work, never blocks the event loop, and isn't automatically faster.

> 🔑 Use **`asyncio.gather`** to overlap independent I/O within a request, and async workers to handle concurrency across requests. Async is a throughput tool for **I/O-bound** work — not a magic speedup for CPU work.

---

## 6. Profiling — Find the Real Bottleneck

To know *where* time goes, **profile**. Options, from quick to production-grade:

- **Timing** — wrap a suspect block in `time.perf_counter()` for a rough number.
- **`cProfile`** — the stdlib profiler; shows where a function spends time.
  ```bash
  python -m cProfile -s cumulative myscript.py
  ```
- **`py-spy`** — a **sampling** profiler that attaches to a **running** process (even in production) with negligible overhead, and produces flame graphs:
  ```bash
  py-spy top --pid 12345           # live top-like view of a running app
  py-spy record -o profile.svg --pid 12345   # a flame graph
  ```
- **SQL logging** (`echo=True`) or a query counter — reveals N+1 and slow queries.
- **APM tools** (Datadog, New Relic, Sentry Performance) — profiling + tracing in production.

`py-spy` is the standout: it needs **no code changes** and can profile a live production process to find the hot path.

> 🔑 **`py-spy`** attaches to a running process with near-zero overhead — perfect for finding what's actually slow in production. Profile to find the hot path; don't optimize by guessing.

---

## 7. The Other High-Impact Wins

Most real speedups come from a short list you've already learned:

| Optimization | What it does | Lesson |
|---|---|---|
| **Fix N+1** | Eager-load relationships | this lesson / 25 |
| **Add indexes** | Speed up `WHERE`/`ORDER BY`/joins on big tables | 20 |
| **Cache hot reads** | Serve expensive, repeated reads from memory/Redis | 35 |
| **Paginate** | Never return whole tables; cursor for deep pages | 36 |
| **Select only needed columns** | Avoid over-fetching wide rows | — |
| **`response_model`** | Trim payloads to what clients need | 23 |
| **GZip middleware** | Compress large responses | 15 |
| **Connection pooling** | Reuse DB connections | this lesson / 20 |

> 💡 Indexes and fixing N+1 usually deliver the biggest database wins; caching and pagination the biggest read-path wins. Reach for exotic optimizations only after these.

---

## 8. The Optimization Loop in Practice

```
1. Measure    -> profile / log queries / time endpoints under realistic load
2. Find       -> the single biggest cost (often N+1 or a missing index)
3. Fix        -> eager load / add index / cache / paginate
4. Re-measure -> confirm it actually helped; note the new bottleneck
5. Repeat     -> until "fast enough"; then STOP (don't over-optimize)
```

Stop when it's fast enough for your requirements. Endless micro-optimization has diminishing returns and adds complexity.

---

## 9. Real-World Use Case — A Slow List Endpoint

`GET /authors` (each author with their book count) takes 3 seconds and the database is at 90% CPU. The investigation:

- **Measure:** enable SQL logging → the endpoint fires **201 queries** for 100 authors. Classic **N+1** — `author.books` is lazy-loaded per author.
- **Fix:** add `selectinload(Author.books)` → **2 queries**, total. The endpoint drops from 3s to 60ms and DB CPU falls to normal.
- **Re-measure:** now the next-biggest cost is a missing index on a filter column → add it. Then a hot read → cache it (Lesson 35).

One data-driven change (eager loading) delivered a 50× improvement. No guessing, no rewrite — just measure, find N+1, fix it, confirm. That's performance work in the real world.

---

## 10. Mini Task

`main.py` counts the SQL queries each endpoint fires, so N+1 is visible.

1. Install: `pip install fastapi uvicorn sqlalchemy httpx`
2. Run: `uvicorn main:app --reload`
3. Compare the two endpoints (both return the same data):
   - `GET /authors/n-plus-1` → response includes `query_count` = **1 + N** (the N+1 bug).
   - `GET /authors/optimized` → `query_count` = **2** (eager-loaded), regardless of N.
4. Add more authors (re-seed with a bigger number) and watch the N+1 count grow linearly while the optimized count stays at 2.
5. **Experiment:**
   - Switch the optimized endpoint from `selectinload` to `joinedload` and compare the query count and SQL.
   - Add an `asyncio.gather` example that overlaps two `asyncio.sleep` calls and time it.
   - Enable `echo=True` on the engine and read the actual SQL each endpoint emits.
6. **Bonus:** Add an index to a filtered column and reason about when it helps (big tables) vs when it doesn't (tiny tables).

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Optimizing without measuring | Profile first; fix the real bottleneck. |
| N+1 from lazy-loaded relationships | Eager-load with `selectinload`/`joinedload`. |
| Opening a DB connection per request | Use the engine's connection pool; tune it. |
| Assuming async is automatically faster | It helps I/O-bound concurrency; profile CPU work. |
| Returning whole tables | Paginate; select only needed columns. |
| Missing indexes on filtered/sorted columns | Add them for large tables. |
| Over-optimizing tiny code paths | Stop when it's fast enough; avoid needless complexity. |

---

## 12. Key Takeaways

- **Measure first.** Profile to find the real bottleneck; optimizing by guessing wastes effort.
- The **N+1 query problem** (1 query for a list + 1 per item for a relationship) is the #1 ORM perf bug — fix it with **eager loading** (`selectinload`/`joinedload`) to make it constant.
- **Connection pooling** reuses DB connections; tune `pool_size`/`max_overflow` to your load and the database's limits.
- **Async I/O** (workers + `asyncio.gather`) boosts throughput for **I/O-bound** work; it doesn't help CPU-bound code.
- **Profile** with timing, `cProfile`, and especially **`py-spy`** (attaches to a live process, near-zero overhead).
- Biggest wins: **fix N+1, add indexes, cache (35), paginate (36)**, trim payloads (`response_model`), pool connections.
- Follow the loop: **measure → fix the biggest → re-measure**, and **stop** when it's fast enough.

---

## ➡️ Next Lesson

**Lesson 49 — Docker**
- Writing a `Dockerfile` for a FastAPI app
- `docker-compose` for app + database + Redis
- Multi-stage builds for small images
