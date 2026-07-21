# Lesson 45 — Configuration Management

> **Goal of this lesson:** Stop hardcoding settings. Load configuration from **environment variables** and **`.env` files** with **`pydantic-settings`** — typed, validated, and centralized — and manage **separate dev / staging / prod** environments cleanly. This upgrades the simple `core/config.py` stub from Lesson 44 into real production config.
>
> `main.py` uses a `pydantic-settings` `Settings` class; `.env.example` shows the file format (a real `.env` stays out of version control).

---

## 1. The Problem — Hardcoded Settings

Every app has values that **change between environments** or **must stay secret**:

- Database URLs, Redis URLs
- The JWT `SECRET_KEY`, API keys, third-party credentials
- Feature flags, timeouts, page-size limits
- The environment name itself (dev / staging / prod)

Hardcoding them is wrong on every axis:

```python
SECRET_KEY = "my-secret-123"          # ❌ committed to git = leaked forever
DATABASE_URL = "postgresql://localhost/dev"   # ❌ same in prod? disaster
```

- **Secrets in code** end up in version control — a security incident.
- **Same values everywhere** means dev accidentally hits the prod database, or vice-versa.
- **Scattered constants** are impossible to audit or change safely.

The fix follows the **Twelve-Factor App** principle: **store config in the environment**, separate from code.

> 🔑 Config that varies by environment or must stay secret belongs in the **environment**, never hardcoded. Code is the same across environments; **configuration** is what differs.

---

## 2. Environment Variables — The Foundation

An **environment variable** is a key/value set outside your program, in the OS/shell:

```bash
export DATABASE_URL="postgresql://prod-host/app"
export SECRET_KEY="a-long-random-value"
```

Your app reads them at startup. The same code, given different env vars, behaves as dev, staging, or prod — no code change. Reading them raw with `os.getenv` works but is clumsy:

```python
import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
PORT = int(os.getenv("PORT", "8000"))          # manual type conversion
DEBUG = os.getenv("DEBUG", "false").lower() == "true"   # manual bool parsing
```

Every var is a string; you hand-convert types and hand-check required ones. That's exactly what `pydantic-settings` automates.

---

## 3. `pydantic-settings` — Typed, Validated Config

**`pydantic-settings`** (a companion to Pydantic) reads config from env vars into a **typed, validated `Settings` model**. You get type conversion, validation, defaults, and required-field enforcement for free.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "My API"
    database_url: str                      # required (no default) -> must be provided
    secret_key: str                        # required
    port: int = 8000                       # typed: "8000" -> 8000 automatically
    debug: bool = False                    # "true"/"1"/"yes" -> True automatically
    allowed_origins: list[str] = []        # parses JSON/CSV from the env

settings = Settings()                      # reads env vars + .env at instantiation
```

What you get:

| Feature | Behavior |
|---|---|
| **Type conversion** | `PORT=8000` (string) → `int`; `DEBUG=true` → `bool` |
| **Validation** | Wrong types / missing required fields raise a clear error at startup |
| **Defaults** | Fields with a default are optional |
| **Required fields** | Fields **without** a default must be provided or the app won't start |
| **`.env` loading** | Reads a `.env` file automatically |
| **Case-insensitive** | `DATABASE_URL` env var maps to `database_url` field |

> 🔑 `pydantic-settings` turns a pile of stringly-typed env vars into a **validated, typed object**. A missing `SECRET_KEY` fails **loudly at startup**, not mysteriously at request time.

---

## 4. `.env` Files

Setting env vars by hand every time is tedious. A **`.env`** file holds them for local development, and `pydantic-settings` loads it automatically (via `env_file=".env"`):

```bash
# .env
APP_NAME="My API (dev)"
DATABASE_URL="sqlite:///./dev.db"
SECRET_KEY="dev-only-not-secret"
DEBUG=true
ALLOWED_ORIGINS=["http://localhost:3000"]
```

Precedence: **real environment variables override the `.env` file.** So in production you set actual env vars (no `.env` needed); locally the `.env` fills them in.

### 4.1 NEVER commit `.env`

A `.env` contains secrets. It must be **git-ignored**. The convention is to commit a **`.env.example`** (same keys, dummy/empty values) so teammates know what to set:

```bash
# .env.example  (committed - a template, no real secrets)
APP_NAME=
DATABASE_URL=
SECRET_KEY=
DEBUG=false
```

```gitignore
.env            # never commit real secrets
```

> ⚠️ Committing a real `.env` is the classic way secrets leak into a repo. **Git-ignore `.env`; commit `.env.example`.** If a secret is ever committed, it's compromised — rotate it, don't just delete the file.

---

## 5. Centralize and Inject Settings

Create the `Settings` **once** and import it everywhere (this is your Lesson 44 `core/config.py`, upgraded):

```python
# app/core/config.py
settings = Settings()      # created once at import
```

Everything else reads from `settings` instead of hardcoding:

```python
engine = create_engine(settings.database_url)
app = FastAPI(title=settings.app_name)
SECRET_KEY = settings.secret_key
```

### 5.1 Settings as a dependency (optional but clean)

For testability, you can expose settings via a dependency so tests can **override** it (Lesson 41):

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()      # cached - built once

@app.get("/info")
def info(settings: Annotated[Settings, Depends(get_settings)]):
    return {"app": settings.app_name}
```

`@lru_cache` means `Settings()` is constructed once (reading env/`.env` is not repeated), and tests can do `app.dependency_overrides[get_settings] = lambda: test_settings`.

> 🔑 Build `Settings` **once** (module-level or `@lru_cache`d) and read config from it app-wide. Injecting it via a dependency makes config **overridable in tests**.

---

## 6. Multiple Environments — dev / staging / prod

Real deployments have several environments that differ only in **configuration**:

| Environment | Database | Debug | Secrets |
|---|---|---|---|
| **dev** | local SQLite / dev DB | on | dummy |
| **staging** | staging DB | off | staging secrets |
| **prod** | production DB | off | real secrets |

Two common ways to manage them:

### 6.1 Per-environment `.env` files

Keep `.env.dev`, `.env.staging`, `.env.prod` and choose which to load:

```python
import os
env = os.getenv("APP_ENV", "dev")                 # APP_ENV picks the file
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=f".env.{env}")
```

### 6.2 Real env vars in deployed environments

Locally use a `.env`; in staging/prod, the platform (Render, Railway, AWS, Kubernetes, GitHub Actions) injects **real environment variables** — no `.env` file ships. Since real env vars override `.env`, the same `Settings` class works everywhere.

An **`environment` field** lets code branch when needed:

```python
class Settings(BaseSettings):
    environment: str = "dev"       # "dev" | "staging" | "prod"

if settings.environment == "prod":
    assert settings.secret_key != "dev-only-not-secret"   # guard against dev secrets
```

> 🔑 The **same code + same `Settings` class** runs in every environment; only the **injected values** differ. That's the whole point — configuration, not code, changes between dev, staging, and prod.

---

## 7. Validating Config at Startup

Because `Settings()` runs at startup, you can **fail fast** on bad config — far better than a mysterious error under load. Use Pydantic validators (Lesson 9):

```python
from pydantic import field_validator

class Settings(BaseSettings):
    secret_key: str
    environment: str = "dev"

    @field_validator("secret_key")
    @classmethod
    def secret_must_be_strong_in_prod(cls, v, info):
        # (cross-field checks use a model_validator; simplified here)
        if len(v) < 16:
            raise ValueError("SECRET_KEY too short")
        return v
```

A misconfigured app now refuses to start with a clear message — you catch it at deploy time, not at 3am in production.

> 🔑 Validate critical config (secret length, required URLs, allowed environment names) in `Settings` so a bad deploy **fails immediately and loudly** instead of silently misbehaving.

---

## 8. Real-World Use Case — One Codebase, Three Environments

Your auction API ships to dev, staging, and prod:

- **`core/config.py`** defines one `Settings` class with `database_url`, `redis_url`, `secret_key`, `environment`, `allowed_origins`.
- **Locally**, a git-ignored `.env` provides dev values (SQLite, a dummy secret, `debug=true`).
- **In CI/staging/prod**, the platform injects real env vars (the staging/prod database, a strong secret from a secret manager, `debug=false`).
- A `field_validator` rejects a weak `secret_key` when `environment == "prod"`, so a botched deploy fails at startup.
- The **exact same image/code** runs everywhere; only the environment's injected values change.

No secrets in git, no accidental cross-environment database hits, and config is typed and auditable in one file. That's production configuration done right.

---

## 9. Mini Task

This lesson ships a `pydantic-settings` config plus a `.env.example`.

1. Install: `pip install fastapi uvicorn pydantic-settings`
2. Copy the example to a real (git-ignored) `.env`:
   ```bash
   cp .env.example .env
   ```
   Edit values, then run: `uvicorn main:app --reload` → `GET /config` shows the loaded (non-secret) settings.
3. **See env override `.env`:** set a variable in your shell (`APP_NAME="From Shell"` / `set APP_NAME=...` on Windows) and restart — the shell value wins over the `.env`.
4. **See required-field enforcement:** remove `SECRET_KEY` from `.env` and no env var, restart, and watch the app refuse to start with a validation error.
5. **See type conversion:** set `DEBUG=true` and `PORT=9000` and confirm they arrive as a real `bool` and `int`.
6. **Experiment:**
   - Add an `environment` field and a validator that rejects a weak secret when it's `"prod"`.
   - Add a per-environment `.env.dev` / `.env.prod` and select via `APP_ENV`.
7. **Bonus:** Expose settings via a `get_settings` dependency and override it in a test.

---

## 10. Common Mistakes

| Mistake | Fix |
|---|---|
| Hardcoding secrets/URLs in code | Read them from env via `pydantic-settings`. |
| Committing a real `.env` | Git-ignore `.env`; commit `.env.example`. |
| Manual `os.getenv` + string parsing everywhere | Use a typed `Settings` model. |
| Same secret in dev and prod | Different values per environment; strong secrets in prod. |
| Building `Settings()` repeatedly | Build once (module-level or `@lru_cache`). |
| No validation on config | Validate critical fields so bad deploys fail at startup. |
| Leaking secrets via a `/config` endpoint | Only expose non-secret settings; never return `secret_key`. |

---

## 11. Key Takeaways

- **Config belongs in the environment, not the code** (Twelve-Factor). Same code, different env values per environment.
- **`pydantic-settings`** loads env vars into a **typed, validated `Settings` model** — automatic type conversion, defaults, and required-field enforcement.
- **`.env`** files hold local config and are loaded automatically; **real env vars override `.env`**.
- **Never commit `.env`** (secrets) — git-ignore it and commit a **`.env.example`** template.
- Build `Settings` **once** and read from it everywhere (your `core/config.py`); optionally inject via a **dependency** for test overrides.
- Manage **dev/staging/prod** by injecting different values (per-env `.env` files locally, real env vars in deployed environments); an `environment` field lets code branch.
- **Validate config at startup** so a misconfigured deploy fails **loudly and immediately**.
- Never expose secrets through an endpoint.

---

## ➡️ Next Lesson

**Lesson 46 — Logging**
- Structured logging with `structlog` / `loguru`
- Request-ID tracing across a request
- Log levels and what to log (and never log)
