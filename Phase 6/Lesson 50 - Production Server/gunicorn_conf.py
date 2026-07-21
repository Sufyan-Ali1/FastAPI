"""
gunicorn_conf.py - Gunicorn configuration for a FastAPI app.

Use it with:

    gunicorn main:app -c gunicorn_conf.py

Gunicorn (a process manager) runs Uvicorn WORKERS (the ASGI server), giving you
robust supervision + async serving. Gunicorn is Unix-only (Linux/macOS), which
is where you deploy; on Windows use `uvicorn --workers` for local testing.
"""

import multiprocessing

# Bind address (behind Nginx you'd bind to 127.0.0.1; exposed, to 0.0.0.0).
bind = "0.0.0.0:8000"

# THE KEY SETTING: run each worker as a Uvicorn (ASGI) worker.
worker_class = "uvicorn.workers.UvicornWorker"

# Worker count: a common rule of thumb is (2 x CPU cores) + 1.
workers = multiprocessing.cpu_count() * 2 + 1

# Restart a worker after this many requests (mitigates slow memory leaks).
max_requests = 1000
max_requests_jitter = 100          # add randomness so workers don't restart together

# Kill and restart a worker that hangs longer than this (seconds).
timeout = 30
graceful_timeout = 30              # time to finish in-flight requests on reload

# Trust proxy headers from Nginx (real client IP, original scheme).
forwarded_allow_ips = "*"          # in prod, restrict to the proxy's IP

# Logging to stdout/stderr (a container/orchestrator collects these).
accesslog = "-"
errorlog = "-"
loglevel = "info"
