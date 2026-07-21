# Lesson 35 — Caching

> **Goal of this lesson:** Make repeated, expensive work fast by **remembering results**. Learn **in-memory caching** (`functools.lru_cache`, TTL caches), **Redis caching** (shared, distributed), and **`fastapi-cache2`** for one-decorator response caching — plus the genuinely hard parts: **cache keys, TTLs, and invalidation**.
>
> Builds directly on Lesson 27's Redis cache-aside. `main.py` is runnable with **no Redis server** (uses the in-memory backend) and shows cache hits vs misses.

---

## 1. Why Cache?

A **cache** stores the result of expensive work so the next request can reuse it instead of redoing it. The payoff:

| Benefit | Example |
|---|---|
| **Speed** | Serve a cached result in microseconds instead of a 200ms DB query. |
| **Reduced load** | Fewer hits on your database / downstream services. |
| **Lower cost** | Each avoided call to a paid API/LLM/DB saves money. |
| **Resilience** | A cached copy can serve traffic even if the source is briefly slow. |

The classic case: a **read-heavy, rarely-changing** resource hit thousands of times a minute. Compute it once, serve the cached copy to everyone else.

> 🔑 Cache what is **expensive to produce, frequently read, and infrequently changed.** Caching cheap or rapidly-changing data adds complexity for little gain — and risks serving stale data.

---

## 2. The Caching Layers

"Caching" spans several layers; this lesson focuses on the application layer:

| Layer | Where | Example |
|---|---|---|
| **In-memory (app)** | Inside your process's RAM | `lru_cache`, a dict, `cachetools` |
| **Distributed (app)** | A shared store across processes | **Redis** / Memcached |
| **HTTP / CDN** | Between client and server | `Cache-Control` headers, Cloudflare |
| **Database** | Inside the DB | Query cache, materialized views |

In-memory is fastest but **per-process**; Redis is shared across all workers; HTTP/CDN caching offloads work before it ever reaches you. You often combine them.

---

## 3. In-Memory Caching

The simplest cache lives in your process's memory.

### 3.1 `functools.lru_cache` — memoize a function

Python's built-in decorator caches a function's return value keyed by its arguments. Perfect for **pure, expensive** computations:

```python
from functools import lru_cache

@lru_cache(maxsize=128)          # keep up to 128 results, evict least-recently-used
def fibonacci(n: int) -> int:
    return n if n < 2 else fibonacci(n - 1) + fibonacci(n - 2)

fibonacci(100)   # computed once
fibonacci(100)   # returned instantly from cache
fibonacci.cache_info()   # hits/misses/size stats
```

- **Keyed by the arguments** — same args → cached result.
- **`maxsize`** bounds memory via LRU eviction (`None` = unbounded).
- **No TTL** — entries never expire on their own (clear with `.cache_clear()`).
- Args must be **hashable**.

> ⚠️ `lru_cache` is great for deterministic, pure functions. It's **wrong** for anything that changes over time or depends on external state (a DB row), because it never expires — you'd serve stale data forever.

### 3.2 TTL caches (`cachetools`)

When you need **time-based expiry**, use a TTL cache (e.g. the `cachetools` library):

```python
from cachetools import TTLCache
cache = TTLCache(maxsize=1000, ttl=60)   # entries expire after 60 seconds
cache["user:1"] = user_data
value = cache.get("user:1")              # None once it has expired
```

### 3.3 In-memory trade-offs

| Pro | Con |
|---|---|
| Fastest possible (RAM, same process) | **Per-process** — each worker has its own copy |
| Zero infrastructure | Lost on restart |
| Simple | Bounded by one machine's memory; can't share across servers |

> 🔑 In-memory caching is **per-process**. With multiple workers (Lesson 50), each has a separate cache — cache hit rates drop and different workers can serve different cached values. Fine for single-process or truly static data; otherwise reach for Redis.

---

## 4. Redis Caching (Distributed)

**Redis** (Lesson 27) is an in-memory store **shared** across all your workers and servers, with built-in **TTL**. That makes it the standard application cache for anything beyond a single process.

The **cache-aside** pattern (from Lesson 27), recapped:

```python
async def get_product(product_id: str):
    key = f"product:{product_id}"
    cached = await redis.get(key)
    if cached is not None:               # HIT
        return json.loads(cached)
    data = await db_fetch(product_id)    # MISS -> source
    await redis.set(key, json.dumps(data), ex=60)   # fill with TTL
    return data
```

| | In-memory | Redis |
|---|---|---|
| Shared across workers/servers | ❌ No | ✅ Yes |
| Survives app restart | ❌ No | ✅ Yes (separate process) |
| Speed | Fastest (RAM, same process) | Very fast (network hop) |
| TTL / expiry | Manual / `cachetools` | Built in (`ex=`) |
| Infrastructure | None | Needs a Redis server |
| Best for | Single process, static data | Multi-worker, shared cache |

> 🔑 **In-memory for a single process or static data; Redis when the cache must be shared and consistent across workers.** Both are valid — pick by your deployment.

---

## 5. `fastapi-cache2` — Response Caching by Decorator

Writing cache-aside by hand in every endpoint is repetitive. **`fastapi-cache2`** does it with one decorator, and can back onto **in-memory** *or* **Redis** — you switch backends without touching endpoint code.

### 5.1 Setup

```python
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

@asynccontextmanager
async def lifespan(app: FastAPI):
    FastAPICache.init(InMemoryBackend(), prefix="cache")   # or RedisBackend(redis)
    yield

app = FastAPI(lifespan=lifespan)
```

### 5.2 Caching an endpoint

```python
@app.get("/products/{product_id}")
@cache(expire=30)                 # cache this response for 30 seconds
async def get_product(product_id: int):
    return expensive_lookup(product_id)   # runs on a miss; skipped on a hit
```

- **`@cache(expire=30)`** — the response is cached for 30 seconds. The first call runs the function; subsequent calls within 30s return the cached response **without running it**.
- The cache **key** is derived automatically from the path + query params, so `/products/1` and `/products/2` cache separately.
- Swap `InMemoryBackend()` for `RedisBackend(redis)` and the **exact same decorators** now use a shared Redis cache.

> 💡 To use Redis, `pip install "fastapi-cache2[redis]"` and init with `RedisBackend(redis_client)`. This lesson uses `InMemoryBackend` so it runs with no server, but the decorators are backend-agnostic.

---

## 6. Cache Keys

A cache is a **key → value** map. The key must capture **everything the result depends on**, or you'll serve the wrong cached value.

- `fastapi-cache2` builds keys from the **prefix + path + query parameters** by default.
- If a response depends on something *else* (the current user, a header, a language), that must be part of the key — otherwise user A gets user B's cached data. You can supply a custom **`key_builder`**.

```
GET /products?category=books&page=1   -> key: cache:...:/products?category=books&page=1
GET /products?category=toys&page=1    -> a DIFFERENT key (different result)
```

> 🔑 The cache key must include every input that changes the output. **A too-broad key serves the wrong data** (a subtle, dangerous bug — e.g. caching per-user data under a user-independent key). When in doubt, include more in the key.

---

## 7. TTL and Invalidation — The Hard Part

> *"There are only two hard things in Computer Science: cache invalidation and naming things."*

A cache is only useful if it's **fresh enough**. Two mechanisms keep it correct:

### 7.1 TTL (time-to-live)

Every cached entry gets an **expiry**. After it lapses, the next request recomputes and refills. TTL is your safety net: even if you forget to invalidate, stale data self-heals within the TTL.

- **Short TTL** (seconds) → fresher, less effective caching.
- **Long TTL** (minutes/hours) → more effective, riskier staleness.
- Pick per resource: a stock price maybe 1s; a product catalog maybe 5 min; a country list maybe a day.

### 7.2 Explicit invalidation on writes

When the underlying data **changes** (create/update/delete), **delete the cache key** so the next read refills with fresh data:

```python
@app.get("/products/{product_id}")
@cache(expire=300, namespace="products")     # tag cached entries with a namespace
async def get_product(product_id: int): ...

@app.put("/products/{product_id}")
async def update(product_id: int, ...):
    ...  # update the DB
    await FastAPICache.clear(namespace="products")   # clear that namespace
```

The `namespace` you clear must **match** the one on the `@cache` decorator — clearing a namespace the entries weren't stored under does nothing (a subtle no-op bug).

> 🔑 Two levers keep a cache correct: an **explicit invalidation on writes** + a **TTL backstop**. Forgetting the invalidation is the #1 caching bug (you update the DB but keep serving the old cached value until the TTL expires).

---

## 8. Cache Stampede (Thundering Herd)

When a popular cached entry **expires**, many concurrent requests can all miss at once and hammer the database simultaneously to refill it — a **stampede**. Mitigations:

- **Slightly randomized (jittered) TTLs** so entries don't all expire together.
- **Locking / single-flight** so only one request refills while others wait.
- **Stale-while-revalidate** — serve the stale value while one request refreshes.

You don't need to implement these on day one, but know the term: a naive cache can turn one expiry into a traffic spike.

---

## 9. What NOT to Cache

| Don't cache | Why |
|---|---|
| Rapidly changing data | Stale almost immediately; little benefit |
| Highly personalized responses (unless keyed per user) | Risk of leaking one user's data to another |
| Write endpoints (`POST`/`PUT`/`DELETE`) | They change state; caching them is meaningless/harmful |
| Sensitive data without care | A shared cache can expose it across requests |
| Cheap-to-compute results | The cache overhead isn't worth it |

> 🔑 Default to caching **idempotent GETs** of expensive, shared, rarely-changing data. Be very deliberate before caching anything **per-user** — the key must isolate users.

---

## 10. Real-World Use Case — A Hot Product Endpoint

`GET /products/{id}` is hit thousands of times a minute; product data changes a few times a day.

- Add `@cache(expire=300)` (5 minutes). The first request computes and caches; the next thousands are served from cache in microseconds — the database barely notices.
- On `PUT /products/{id}`, **invalidate** that product's cache key so an edit is visible immediately; the 5-minute TTL is the backstop if an invalidation is ever missed.
- In production, back it with **Redis** so all workers share one cache and hit rates stay high.

This is the same cache-aside idea from Lesson 27, now expressed as a one-line decorator with a proper TTL + invalidation policy.

---

## 11. Mini Task

`main.py` runs with **no Redis** (in-memory backend) and shows caching clearly.

1. Install: `pip install fastapi-cache2`
2. Run: `uvicorn main:app --reload`
3. Hit the slow, cached endpoint twice and compare:
   ```bash
   time curl -s http://127.0.0.1:8000/products/1    # slow (miss, ~0.5s)
   time curl -s http://127.0.0.1:8000/products/1    # fast (hit, ~0ms)
   ```
   Note the `generated_at` field is **identical** on the second call — proof it's the cached response.
4. Hit `/products/2` → different key → a fresh (slow) miss.
5. Wait past the TTL and call `/products/1` again → it recomputes (new `generated_at`).
6. Compare with `/uncached/1`, which is slow **every** time.
7. **Experiment:**
   - Call `PUT /products/1` and confirm the cache is invalidated (next GET recomputes).
   - Check the `lru_cache` stats via `/fib/{n}` and `/fib-stats`.
8. **Bonus:** Switch the backend to `RedisBackend` (needs `pip install "fastapi-cache2[redis]"` and a Redis server) and confirm the endpoint code doesn't change.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Caching per-user data under a user-independent key | Include the user in the cache key. |
| Updating the DB but not invalidating the cache | Clear the key on writes; TTL is only a backstop. |
| Using `lru_cache` for data that changes over time | It never expires; use a TTL cache or Redis. |
| In-memory cache with multiple workers | Each worker caches separately; use Redis for a shared cache. |
| No TTL at all | Always set an expiry so staleness self-heals. |
| Caching write endpoints | Only cache idempotent reads. |
| Same TTL for everything | Tune per resource by how fast it changes. |

---

## 13. Key Takeaways

- **Cache** = remember expensive results to serve future requests fast. Cache the **expensive + frequently-read + rarely-changed**.
- **In-memory** (`lru_cache`, `cachetools` TTL) is fastest but **per-process** and (for `lru_cache`) has no TTL.
- **Redis** gives a **shared, TTL-backed** cache across all workers — the standard app cache beyond one process.
- **`fastapi-cache2`** adds response caching with `@cache(expire=...)`; the same decorator works on **in-memory or Redis** backends.
- The **cache key** must include every input that affects the output — a too-broad key serves the wrong data.
- Keep it correct with a **TTL** + **explicit invalidation on writes**; forgetting invalidation is the classic bug.
- Beware **cache stampede** on popular-key expiry; mitigate with jittered TTLs / single-flight.
- Don't cache rapidly-changing, per-user (un-keyed), or write endpoints.

---

## ➡️ Next Lesson

**Lesson 36 — Pagination**
- Limit/offset pagination and its trade-offs
- Cursor-based pagination for large/real-time datasets
- Consistent paginated response shapes
