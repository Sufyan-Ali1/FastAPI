"""
Lesson 35 - Caching
-------------------
Runnable caching demos that need NO Redis server (fastapi-cache2's in-memory
backend). Each cached response includes a `generated_at` timestamp, so a cache
HIT is obvious: the timestamp does not change until the entry expires.

    /products/{id}     @cache(expire=10)  -> cached response (fast on repeat)
    /uncached/{id}     no cache           -> slow EVERY time (for comparison)
    PUT /products/{id} invalidates the cached product
    /fib/{n}           functools.lru_cache memoization (pure in-memory)

To use Redis instead, install fastapi-cache2[redis] and swap InMemoryBackend
for RedisBackend(redis) in the lifespan - the @cache decorators don't change.

Install once:

    pip install fastapi uvicorn fastapi-cache2

How to run (from inside this folder):

    uvicorn main:app --reload

Then:
    time curl -s http://127.0.0.1:8000/products/1   # slow (miss)
    time curl -s http://127.0.0.1:8000/products/1   # fast (hit, same generated_at)
"""

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

CACHE_TTL = 10  # seconds


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def expensive_lookup(product_id: int) -> dict:
    """Simulate a slow DB query / computation."""
    time.sleep(0.5)
    return {
        "id": product_id,
        "name": f"Product {product_id}",
        "price": round(product_id * 1.5, 2),
        "generated_at": now(),  # changes only when the function actually runs
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the cache backend once at startup. Swap InMemoryBackend() for
    # RedisBackend(redis) to get a shared, multi-worker cache - no other change.
    FastAPICache.init(InMemoryBackend(), prefix="lesson35")
    yield


app = FastAPI(title="Lesson 35 - Caching", lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "Caching demo. Compare /products/1 (cached) vs /uncached/1."}


# ---------------------------------------------------------------------------
# CACHED endpoint - first call is slow (miss), repeats are instant (hit).
# The cache key is derived from the path + params, so /products/1 and
# /products/2 cache separately.
# ---------------------------------------------------------------------------
@app.get("/products/{product_id}")
@cache(expire=CACHE_TTL, namespace="products")
async def get_product(product_id: int):
    return expensive_lookup(product_id)


# ---------------------------------------------------------------------------
# UNCACHED - slow on EVERY call, for comparison.
# ---------------------------------------------------------------------------
@app.get("/uncached/{product_id}")
async def get_product_uncached(product_id: int):
    return expensive_lookup(product_id)


# ---------------------------------------------------------------------------
# WRITE endpoint - invalidate the cache so the next read is fresh.
# (Here we clear the whole namespace for simplicity.)
# ---------------------------------------------------------------------------
@app.put("/products/{product_id}")
async def update_product(product_id: int, price: float):
    # ... update the DB here ...
    # Clear the "products" namespace so the next GET recomputes fresh data.
    # (namespace here must match the one on the @cache decorator above.)
    await FastAPICache.clear(namespace="products")  # explicit invalidation on write
    return {"id": product_id, "new_price": price, "note": "cache invalidated"}


# ---------------------------------------------------------------------------
# IN-MEMORY memoization with functools.lru_cache (pure, deterministic function)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=256)
def fibonacci(n: int) -> int:
    return n if n < 2 else fibonacci(n - 1) + fibonacci(n - 2)


@app.get("/fib/{n}")
def get_fib(n: int):
    return {"n": n, "value": fibonacci(n)}


@app.get("/fib-stats")
def fib_stats():
    info = fibonacci.cache_info()
    return {"hits": info.hits, "misses": info.misses,
            "size": info.currsize, "maxsize": info.maxsize}
