"""
Lesson 50 - Production Server (the app)
---------------------------------------
Each response reports the OS process id (PID) of the worker that handled it.
Run with multiple workers and hit / repeatedly - the PID changes as different
worker processes serve requests, proving multi-worker concurrency.

Dev (single worker, auto-reload):
    uvicorn main:app --reload

Multiple workers (production style, no reload):
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

Gunicorn + Uvicorn workers (Linux/macOS - the classic combo):
    gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000
"""

import os

from fastapi import FastAPI

app = FastAPI(title="Lesson 50 - Production Server")

# An in-memory counter - note it is PER WORKER (not shared). Under multiple
# workers each process has its own count, which is exactly why shared state
# (real counters, caches, rate limits) must live in Redis.
_local_hits = {"count": 0}


@app.get("/")
def root():
    _local_hits["count"] += 1
    return {
        "message": "Handled by a worker process.",
        "worker_pid": os.getpid(),          # changes across workers
        "this_worker_hits": _local_hits["count"],  # per-worker, NOT global
    }


@app.get("/health")
def health():
    return {"status": "ok", "pid": os.getpid()}
