# Lesson 49 — Docker

> **Goal of this lesson:** Package your FastAPI app so it runs **the same everywhere**. Write a **`Dockerfile`**, shrink the image with **multi-stage builds**, and orchestrate your app **plus a database and Redis** with **`docker-compose`**. This is how modern backends are shipped.
>
> This lesson's deliverables are real, buildable files: a `Dockerfile`, `.dockerignore`, `docker-compose.yml`, and a small app — verified by actually building the image and validating the compose config.

---

## 1. The Problem — "Works on My Machine"

Your app runs locally. On the server it breaks: different Python version, a missing system library, a different OS, an env var that isn't set. This **environment drift** is one of the oldest problems in software.

**Docker** solves it by packaging your app **with its entire environment** — the Python version, dependencies, system libraries, and config — into a single **image** that runs identically on your laptop, a teammate's machine, CI, and production.

> 🔑 A Docker **image** bundles your app *and* everything it needs to run. "Works on my machine" becomes "works in the container" — which is the same container everywhere.

---

## 2. Containers vs VMs, Images vs Containers

- A **virtual machine** virtualizes a whole OS (heavy, slow to start). A **container** shares the host kernel and isolates just your app (lightweight, starts in milliseconds).
- An **image** is the built, immutable package (a blueprint). A **container** is a running instance of an image. One image → many containers.

```
Dockerfile  --build-->  Image  --run-->  Container(s)
(recipe)                (package)         (running app)
```

| | Virtual Machine | Container |
|---|---|---|
| Isolates | A full OS | Just your app + deps |
| Size | Gigabytes | Megabytes |
| Startup | Seconds–minutes | Milliseconds |
| Overhead | High | Low |

> 🔑 Containers are lightweight because they share the host kernel and package only your app. **Image = the blueprint; container = a running instance.**

---

## 3. The Dockerfile

A **`Dockerfile`** is a recipe: a list of instructions Docker runs to build your image. The core instructions:

| Instruction | Does |
|---|---|
| `FROM` | The base image to start from (e.g. `python:3.12-slim`) |
| `WORKDIR` | Set the working directory inside the image |
| `COPY` | Copy files from your project into the image |
| `RUN` | Run a command at **build** time (e.g. `pip install`) |
| `EXPOSE` | Document the port the app listens on |
| `CMD` | The command run when the **container starts** |
| `ENV` | Set an environment variable |

A basic FastAPI `Dockerfile`:

```dockerfile
FROM python:3.12-slim                 # small official Python base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Two important details:

- **`--host 0.0.0.0`** — inside a container you must bind to `0.0.0.0`, not `127.0.0.1`, or the app is unreachable from outside the container.
- **Copy `requirements.txt` and install *before* copying the code.** This uses Docker's **layer cache**: dependencies (which change rarely) are cached, so rebuilds after a code change skip the slow `pip install`.

> 🔑 Order Dockerfile steps from **least- to most-frequently-changing** (deps before code) so Docker's layer cache makes rebuilds fast. Bind uvicorn to `0.0.0.0` inside the container.

---

## 4. `.dockerignore`

Just like `.gitignore`, a **`.dockerignore`** keeps junk out of the image — smaller, faster builds, and no secrets baked in:

```dockerignore
__pycache__/
*.pyc
.venv/
.git/
.env                # never bake secrets into the image
*.db
.pytest_cache/
```

Without it, `COPY . .` drags in your virtualenv, `.git` history, local databases, and possibly a `.env` with secrets — bloating the image and leaking data.

> ⚠️ Always add a `.dockerignore`. Never copy `.env`, `.git`, virtualenvs, or local databases into an image. A secret baked into an image ships wherever the image goes.

---

## 5. Multi-Stage Builds — Smaller, Safer Images

A naive image often includes build tools (compilers, dev headers) that the running app doesn't need — bloating size and attack surface. A **multi-stage build** uses one stage to build dependencies and a second, clean stage that copies only what's needed to run:

```dockerfile
# ---- Stage 1: builder (has build tools) ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime (clean, small) ----
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local     # copy ONLY the installed packages
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- The **builder** stage installs dependencies (and could compile things).
- The **final** stage starts fresh and copies only the built artifacts — no build tools in the shipped image.
- Result: a **smaller, more secure** image (less to download, fewer vulnerabilities).

> 🔑 **Multi-stage builds** keep build-time tooling out of the final image — smaller downloads, faster deploys, and a reduced attack surface. Standard practice for production images.

---

## 6. `docker-compose` — Your App Plus Its Services

A real app isn't just the API — it needs a **database** and often **Redis**. Running each container by hand is tedious. **`docker-compose`** describes a **multi-container** setup in one YAML file and starts it all with one command:

```yaml
services:
  app:
    build: .                          # build the image from the Dockerfile
    ports:
      - "8000:8000"                   # host:container
    environment:
      DATABASE_URL: postgresql+psycopg://app:secret@db:5432/app
      REDIS_URL: redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: app
    volumes:
      - pgdata:/var/lib/postgresql/data   # persist data across restarts

  redis:
    image: redis:7

volumes:
  pgdata:
```

Key concepts:

| Concept | Meaning |
|---|---|
| **`services`** | Each container (app, db, redis) |
| **`build`** vs **`image`** | Build from a Dockerfile, or pull a prebuilt image |
| **`ports`** | Map a container port to the host (`host:container`) |
| **`depends_on`** | Start order (db/redis before app) |
| **`volumes`** | Persist data (a DB volume survives container restarts) |
| **networking** | Compose puts services on one network; the app reaches the DB by its **service name** (`db`), not `localhost` |

That last point is crucial: inside the compose network, the app connects to `db:5432` and `redis:6379` — using the **service names** as hostnames, not `localhost`.

> 🔑 `docker-compose` runs your **app + database + Redis** together with one command. Services reach each other by **service name** (`db`, `redis`), and named **volumes** keep database data across restarts.

---

## 7. Running It

```bash
docker build -t myapi .            # build the image
docker run -p 8000:8000 myapi      # run one container

docker compose up --build          # build + start app + db + redis together
docker compose up -d               # detached (background)
docker compose logs -f app         # follow the app's logs
docker compose down                # stop and remove containers
docker compose down -v             # ...and delete volumes (wipes DB data)
```

After `docker compose up`, the API is at `http://localhost:8000`, backed by a real Postgres and Redis — the same stack you'd run in production.

---

## 8. Production Considerations

A few things separate a demo image from a production one:

- **Run as a non-root user** — don't run the app as `root` inside the container (add a `USER` step).
- **Pin versions** — `python:3.12-slim` (not `latest`) and a pinned `requirements.txt`, for reproducible builds.
- **Multiple workers** — production runs multiple worker processes (Gunicorn + Uvicorn workers — Lesson 50), not a single `uvicorn --reload`.
- **Health checks** — a `/health` endpoint and a compose `healthcheck` so orchestrators know the app is alive.
- **Config via environment** — inject `DATABASE_URL`, `SECRET_KEY`, etc. as env vars (Lesson 45); never bake secrets into the image.
- **Migrations** — run `alembic upgrade head` (Lesson 24) as a startup/deploy step, not `create_all`.
- **Small base images** — `slim` (or `alpine`, with caveats) plus multi-stage builds.

> 🔑 A production image: pinned versions, **non-root user**, multiple workers, env-injected config (no baked secrets), a health check, and migrations run at deploy. The demo image gets you started; these harden it.

---

## 9. Real-World Use Case — Shipping the Whole Stack

Your auction API needs FastAPI, PostgreSQL, and Redis. With Docker:

- The **`Dockerfile`** (multi-stage) builds a small image of the API with its exact dependencies.
- **`docker-compose.yml`** brings up the API, a Postgres container (with a volume so bids survive restarts), and a Redis container (for caching + rate limiting), all networked together.
- A teammate clones the repo and runs `docker compose up` — the **entire stack** starts identically, no "install Postgres, install Redis, set up Python" instructions needed.
- CI builds the same image and runs the tests against it. Production runs the same image with real env vars and multiple workers.

One image, one compose file — the same environment from a laptop to production. That reproducibility is why containers won.

---

## 10. Mini Task

This lesson ships buildable Docker files and a small app.

1. Ensure Docker is installed (`docker --version`).
2. Build the image:
   ```bash
   docker build -t lesson49-api .
   ```
3. Run it:
   ```bash
   docker run -p 8000:8000 lesson49-api      # then open http://localhost:8000
   ```
4. Bring up the whole stack (app + Postgres + Redis):
   ```bash
   docker compose up --build
   ```
   Note the app reaches the DB via the service name `db`, not `localhost`.
5. **Inspect the multi-stage build:** note the final image doesn't contain build tooling. Compare image size with `docker images`.
6. **Experiment:**
   - Change a line of code, rebuild, and observe the layer cache skips `pip install`.
   - Add a `USER` step to run as non-root.
   - Add a compose `healthcheck` on the app's `/health` endpoint.
7. **Bonus:** Add an Alembic migration step to the compose startup.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Binding uvicorn to `127.0.0.1` in a container | Bind to `0.0.0.0` or it's unreachable. |
| No `.dockerignore` | Add one; keep out `.git`, venv, `.env`, DBs. |
| Copying `.env` / secrets into the image | Inject secrets as env vars at runtime. |
| Copying code before installing deps | Deps first for layer-cache-friendly rebuilds. |
| Connecting to the DB via `localhost` in compose | Use the **service name** (`db`, `redis`). |
| Using `:latest` base images | Pin versions for reproducibility. |
| Single `--reload` process in production | Use multiple workers (Lesson 50). |
| Running as root | Add a non-root `USER`. |

---

## 12. Key Takeaways

- **Docker** packages your app with its whole environment into an **image** that runs identically everywhere — killing "works on my machine."
- Containers are **lightweight** (share the host kernel); **image = blueprint, container = running instance**.
- A **`Dockerfile`** is the build recipe (`FROM`, `WORKDIR`, `COPY`, `RUN`, `EXPOSE`, `CMD`); bind uvicorn to `0.0.0.0` and order steps deps-before-code for caching.
- Add a **`.dockerignore`**; never bake `.env`, `.git`, venvs, or DBs into the image.
- **Multi-stage builds** keep build tooling out of the final image — smaller and safer.
- **`docker-compose`** runs app + database + Redis together; services reach each other by **service name**, and **volumes** persist data.
- Production images: pinned versions, **non-root**, multiple workers, env-injected config, health checks, migrations at deploy.

---

## ➡️ Next Lesson

**Lesson 50 — Production Server**
- Uvicorn vs Gunicorn vs Uvicorn workers
- `gunicorn -k uvicorn.workers.UvicornWorker`
- Reverse proxy (Nginx) in front of the app
