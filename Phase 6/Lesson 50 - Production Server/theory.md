# Lesson 50 — Production Server

> **Goal of this lesson:** Serve FastAPI the way production does. Understand **Uvicorn vs Gunicorn vs Uvicorn workers**, run multiple worker processes to use all your CPU cores (`gunicorn -k uvicorn.workers.UvicornWorker`), and put a **reverse proxy (Nginx)** in front for TLS, buffering, and static files.
>
> This lesson's deliverables are real config: a small app that reports its worker PID, a `gunicorn_conf.py`, and an `nginx.conf` example.

---

## 1. The Dev Server Is Not a Production Server

All course you've run `uvicorn main:app --reload`. That's a **development** command:

- `--reload` watches files and restarts on change — great locally, wasteful and unstable in production.
- A single Uvicorn process uses **one CPU core**. Your 8-core server would sit 87% idle.
- No process supervision, no graceful restarts, no TLS.

Production needs **multiple worker processes**, no `--reload`, proper supervision, and usually a **reverse proxy** in front.

> 🔑 `uvicorn --reload` is for **development only**. Production runs multiple workers, no reload, and a reverse proxy — a different setup entirely.

---

## 2. Uvicorn — The ASGI Server

FastAPI is an **ASGI** app; it needs an ASGI **server** to actually handle HTTP. **Uvicorn** is that server (Lesson 2). It's fast and it's what runs your app — but by itself it's a **single process**:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000        # one worker process
```

One process = one CPU core doing the work (Python's GIL means one process can't use multiple cores for CPU-bound work). To use a multi-core machine, you run **multiple worker processes**.

Uvicorn can spawn workers itself:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4   # 4 worker processes
```

This is the **simplest** production option and is often enough.

---

## 3. The Multi-Worker Idea

Each **worker** is a separate OS process running a copy of your app. They share the listening port; the OS load-balances incoming connections across them.

```
             ┌── worker 1 (PID 101) ── uses core 1
port 8000 ──►├── worker 2 (PID 102) ── uses core 2
             ├── worker 3 (PID 103) ── uses core 3
             └── worker 4 (PID 104) ── uses core 4
```

- More workers → handle more requests concurrently and use all cores.
- Common sizing rule of thumb: **`(2 × CPU cores) + 1`** workers (tune to your workload).
- Workers **don't share memory** — an in-memory cache or rate-limit counter is per-worker (the multi-process caveat you saw in Lessons 31/34/35 → use Redis for shared state).

> 🔑 Run **multiple workers** to use all CPU cores and handle more concurrency. Start around **(2 × cores) + 1**. Remember workers don't share memory — shared state (cache, rate limits, WebSocket connections) needs Redis.

---

## 4. Gunicorn + Uvicorn Workers — The Classic Combo

**Gunicorn** is a battle-tested **process manager** (a "worker master") for Python web apps. On its own Gunicorn only speaks WSGI (sync), but it can manage **Uvicorn worker processes** that speak ASGI — giving you Gunicorn's robust process management *plus* Uvicorn's async speed:

```bash
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \      # each worker is a Uvicorn (ASGI) worker
  --workers 4 \
  --bind 0.0.0.0:8000
```

- **`-k uvicorn.workers.UvicornWorker`** — the worker *class*: tells Gunicorn to run Uvicorn (ASGI) workers instead of default sync ones. **This is the key flag.**
- Gunicorn adds: graceful restarts, worker health monitoring, restarting crashed/hung workers, configurable timeouts — production-grade supervision.

> 🔑 **`gunicorn -k uvicorn.workers.UvicornWorker`** is the classic FastAPI production command: Gunicorn manages the process lifecycle; Uvicorn workers run your async app. Gunicorn = supervisor; Uvicorn = the actual ASGI engine.

Note: Gunicorn is **Unix-only** (Linux/macOS), which is where you deploy anyway. On Windows for local testing, use `uvicorn --workers`.

---

## 5. Uvicorn vs Gunicorn vs Uvicorn Workers

Clearing up the confusing trio:

| | What it is | Role |
|---|---|---|
| **Uvicorn** | An **ASGI server** | Actually runs your FastAPI app |
| **Gunicorn** | A **process manager** | Supervises worker processes (restarts, timeouts) |
| **Uvicorn worker** | Uvicorn running **as a Gunicorn worker** | Combines both: Gunicorn supervises, Uvicorn serves |

Two valid production setups:

- **`uvicorn --workers N`** — simpler; Uvicorn manages its own workers. Good default, especially in containers where the orchestrator handles supervision.
- **`gunicorn -k uvicorn.workers.UvicornWorker --workers N`** — more mature process management (graceful reloads, per-worker timeouts). Long the standard.

> 💡 In a **container** (Lesson 49) with an orchestrator (Kubernetes, ECS) supervising the process, plain **`uvicorn --workers`** is often enough — sometimes even one worker per container, scaled by running more containers. Use **Gunicorn** when you want richer in-process supervision.

---

## 6. Why a Reverse Proxy (Nginx)?

You *can* expose Uvicorn/Gunicorn directly, but production almost always puts a **reverse proxy** — usually **Nginx** — in front. The proxy sits between the internet and your app:

```
Internet ──► Nginx (:443) ──► Gunicorn/Uvicorn workers (:8000) ──► FastAPI
```

Nginx handles the things an app server shouldn't:

| Nginx does | Why |
|---|---|
| **TLS/HTTPS termination** | Decrypt once at the edge; certificates in one place |
| **Serving static files** | Far faster than your Python app; offloads it |
| **Load balancing** | Spread traffic across multiple app servers |
| **Buffering** | Absorb slow clients so workers aren't tied up |
| **Rate limiting / security** | Block bad traffic before it reaches your app |
| **Compression, caching** | Gzip, cache headers at the edge |

> 🔑 A **reverse proxy (Nginx)** in front handles TLS, static files, buffering, and load balancing — freeing your app workers to just run application logic. Don't expose Uvicorn/Gunicorn directly to the internet in serious deployments.

---

## 7. A Minimal Nginx Config

Nginx forwards (`proxy_pass`) requests to your app and passes along the real client info:

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;              # your app server
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;    # so the app knows it's HTTPS
    }

    # WebSockets (Lesson 31) need the upgrade headers:
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- **`proxy_pass`** — forward to the app server.
- **`X-Forwarded-*`** headers — tell the app the **real client IP** and **original protocol** (critical for logging, rate limiting per-IP, and HTTPS awareness).
- **WebSocket** locations need `Upgrade`/`Connection` headers or the handshake fails.

> 💡 For FastAPI to trust `X-Forwarded-*` (e.g. to see real client IPs behind the proxy), run Uvicorn with `--proxy-headers` and appropriate `--forwarded-allow-ips`.

---

## 8. The Full Production Stack

Putting Phase 6 together, a typical deployment looks like:

```
                      ┌──────────── one server / container ────────────┐
Internet ─HTTPS─► Nginx ─► Gunicorn (master)
                              ├── UvicornWorker 1 ─┐
                              ├── UvicornWorker 2 ─┤► FastAPI app
                              └── UvicornWorker N ─┘
                                        │
                                        ▼
                              PostgreSQL + Redis (shared state)
```

- **Nginx**: TLS, static, load balancing, security.
- **Gunicorn**: supervises workers, graceful restarts.
- **Uvicorn workers**: run the async FastAPI app across all cores.
- **Redis**: shared cache / rate limits / WebSocket fan-out (since workers don't share memory).
- **Process supervision**: `systemd` on a VM, or the container orchestrator (Kubernetes/ECS) restarts the whole container if it dies.

---

## 9. Real-World Use Case — Deploying the Auction API

Your auction API goes live on a 4-core Linux server:

- Run it with `gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 9 --bind 127.0.0.1:8000` (≈ 2×4+1), managed by a **systemd** unit that restarts it on failure and on boot.
- **Nginx** terminates HTTPS (with a Let's Encrypt cert), forwards to `127.0.0.1:8000`, passes `X-Forwarded-*`, and handles the WebSocket upgrade for live bidding.
- Because there are 9 workers (no shared memory), the WebSocket connection manager and rate-limit counters live in **Redis**, so a bid broadcast reaches clients on any worker.
- Config comes from environment variables (Lesson 45); migrations run at deploy (Lesson 24).

The result uses all four cores, survives crashes, serves HTTPS, and scales — the standard production shape.

---

## 10. Mini Task

This lesson ships a PID-reporting app and production server config.

1. Run the app in dev: `uvicorn main:app --reload` → `GET /` shows the worker's PID.
2. Run with **multiple workers**: `uvicorn main:app --workers 4` → hit `/` several times and note the **PID changes** as different workers handle requests.
3. On Linux/macOS, run the Gunicorn combo:
   ```bash
   gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000
   ```
4. Read `gunicorn_conf.py` (worker count, worker class, bind, timeouts) and `nginx.conf` (the reverse-proxy config).
5. **Experiment:**
   - Compute `(2 × cores) + 1` for your machine and use that worker count.
   - Add `--proxy-headers` to uvicorn and reason about why it's needed behind Nginx.
   - Note that an in-memory counter differs per worker — the reason shared state needs Redis.
6. **Bonus:** Write a `systemd` unit file that runs the Gunicorn command and restarts on failure.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Running `--reload` in production | Dev only; use workers, no reload. |
| A single worker on a multi-core box | Run multiple workers to use all cores. |
| Expecting in-memory state to be shared across workers | It isn't; use Redis for shared cache/rate-limit/WS state. |
| Exposing Uvicorn/Gunicorn directly to the internet | Put Nginx (or a cloud LB) in front for TLS/security. |
| Missing `X-Forwarded-*` handling | Set them in Nginx and run uvicorn with `--proxy-headers`. |
| Broken WebSockets behind a proxy | Add the `Upgrade`/`Connection` headers in Nginx. |
| Way too many workers | Too many exhausts memory/DB connections; start near (2×cores)+1. |

---

## 12. Key Takeaways

- `uvicorn --reload` is **dev only**; production runs **multiple workers**, no reload, behind a proxy.
- **Uvicorn** is the **ASGI server** (runs your app); **Gunicorn** is a **process manager** (supervises workers); a **Uvicorn worker** is Uvicorn running under Gunicorn.
- Run **multiple workers** to use all CPU cores; size around **(2 × cores) + 1**. Workers **don't share memory** — shared state needs **Redis**.
- The classic command: **`gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers N`**; the simpler alternative is **`uvicorn --workers N`** (great in containers).
- Put a **reverse proxy (Nginx)** in front for **TLS, static files, load balancing, buffering, and security**; pass **`X-Forwarded-*`** headers.
- The full stack: **Nginx → Gunicorn/Uvicorn workers → FastAPI**, with **Redis** for shared state and **systemd**/an orchestrator for supervision.

---

## ➡️ Next Lesson

**Lesson 51 — Deployment Options**
- VPS, and PaaS (Render / Railway / Fly.io)
- Cloud (AWS, GCP Cloud Run)
- Choosing where to deploy
