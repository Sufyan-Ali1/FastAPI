"""
Lesson 28 - Async vs Sync Deep Dive
-----------------------------------
A runnable FastAPI app that lets you FEEL the difference between blocking and
non-blocking endpoints by firing concurrent requests at them.

Four endpoints, same 0.5s of "work", very different behaviour under load:

    /sync-blocking      def        + time.sleep       -> threadpool (safe)
    /async-blocking     async def  + time.sleep       -> BLOCKS the loop (bad)
    /async-nonblocking  async def  + asyncio.sleep     -> yields the loop (good)
    /async-offload      async def  + run_in_threadpool -> offloads blocking work

Install once:

    pip install fastapi uvicorn httpx

How to run (from inside this folder):

    uvicorn main:app --reload

Then either open http://127.0.0.1:8000/docs, or run the built-in load test that
fires 10 concurrent requests at each endpoint and prints the wall-clock time:

    python main.py            # starts a server on port 8001 and runs the test
"""

import asyncio
import time

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

app = FastAPI(title="Lesson 28 - Async vs Sync Deep Dive")

WORK_SECONDS = 0.5


def blocking_work(seconds: float = WORK_SECONDS) -> None:
    """A stand-in for slow BLOCKING work: a sync sleep, a heavy library call,
    a sync DB driver, a requests.get(...). It does NOT cooperate with the
    event loop - while it runs, nothing else on that thread can proceed."""
    time.sleep(seconds)


@app.get("/")
def root():
    return {
        "message": "Compare the endpoints under concurrent load. See /docs.",
        "endpoints": [
            "/sync-blocking",
            "/async-blocking",
            "/async-nonblocking",
            "/async-offload",
            "/cpu-bound",
        ],
    }


# ---------------------------------------------------------------------------
# 1. SYNC endpoint (def). FastAPI runs it in a THREADPOOL, so a blocking call
#    here does NOT freeze the event loop - other requests use other threads.
# ---------------------------------------------------------------------------
@app.get("/sync-blocking")
def sync_blocking():
    blocking_work()
    return {"path": "sync-blocking", "note": "ran in a threadpool thread"}


# ---------------------------------------------------------------------------
# 2. ASYNC endpoint that BLOCKS (anti-pattern). time.sleep is synchronous, so
#    it holds the single event-loop thread for the whole 0.5s. Concurrent
#    requests to this endpoint SERIALIZE - this is the classic async bug.
# ---------------------------------------------------------------------------
@app.get("/async-blocking")
async def async_blocking():
    time.sleep(WORK_SECONDS)  # WRONG inside async def - blocks the event loop
    return {"path": "async-blocking", "note": "blocked the event loop (bad)"}


# ---------------------------------------------------------------------------
# 3. ASYNC endpoint done right. asyncio.sleep is awaitable: it yields control
#    back to the event loop, which serves other requests while this one waits.
# ---------------------------------------------------------------------------
@app.get("/async-nonblocking")
async def async_nonblocking():
    await asyncio.sleep(WORK_SECONDS)  # yields the loop while waiting
    return {"path": "async-nonblocking", "note": "awaited - loop stayed free"}


# ---------------------------------------------------------------------------
# 4. ASYNC endpoint that MUST call blocking code: offload it to the threadpool
#    with run_in_threadpool so the event loop is not blocked.
# ---------------------------------------------------------------------------
@app.get("/async-offload")
async def async_offload():
    await run_in_threadpool(blocking_work)  # blocking work, off the loop
    return {"path": "async-offload", "note": "offloaded blocking work"}


# ---------------------------------------------------------------------------
# 5. CPU-BOUND work. async does NOT help CPU-bound code (there is no I/O to
#    await). Keep it in a def so it runs in a threadpool and does not block
#    the loop. (True parallelism needs multiple processes - a later topic.)
# ---------------------------------------------------------------------------
@app.get("/cpu-bound")
def cpu_bound(n: int = 2_000_000):
    total = sum(i * i for i in range(n))
    return {"path": "cpu-bound", "n": n, "checksum": total % 1_000_000}


# ===========================================================================
# Built-in load test: fire N concurrent requests at each endpoint and time it.
# Run:  python main.py
# ===========================================================================
def _run_load_test() -> None:
    import threading

    import httpx
    import uvicorn

    port = 8001
    base = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # wait for startup
    for _ in range(50):
        try:
            httpx.get(base + "/", timeout=1.0)
            break
        except Exception:
            time.sleep(0.1)

    concurrency = 10

    async def hammer(path: str) -> float:
        async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
            start = time.perf_counter()
            await asyncio.gather(*(client.get(path) for _ in range(concurrency)))
            return time.perf_counter() - start

    print(f"\nFiring {concurrency} concurrent requests, each doing "
          f"{WORK_SECONDS}s of work:\n")
    print(f"{'endpoint':<22}{'total wall time':>16}   interpretation")
    print("-" * 72)
    interp = {
        "/sync-blocking": "threadpool: overlap",
        "/async-blocking": "SERIALIZED (blocked loop)",
        "/async-nonblocking": "awaited: full overlap",
        "/async-offload": "offloaded: overlap",
    }
    for path in ["/sync-blocking", "/async-blocking", "/async-nonblocking", "/async-offload"]:
        elapsed = asyncio.run(hammer(path))
        print(f"{path:<22}{elapsed:>14.2f}s   {interp[path]}")

    print("\nIf async were 'automatically faster', /async-blocking would not be "
          "the slowest.\nThe difference is whether the endpoint frees the event "
          "loop while it waits.")
    server.should_exit = True
    thread.join(timeout=5)


if __name__ == "__main__":
    _run_load_test()
