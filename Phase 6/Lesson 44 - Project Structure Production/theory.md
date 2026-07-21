# Lesson 44 — Project Structure (Production)

> **Goal of this lesson:** Graduate from a single `main.py` to the **layered project structure** real FastAPI codebases use: `core/`, `db/`, `models/`, `schemas/`, `services/`, `api/`, and a thin `main.py`. Learn **why** each layer exists, how a request flows through them, and the **separation of concerns** that keeps a large app maintainable.
>
> This lesson's code **is** the structure: a fully working, layered `app/` package you can run and test. Read the files alongside the theory.

---

## 1. The Problem — One File Doesn't Scale

Every lesson so far put everything in one `main.py`: models, schemas, routes, DB setup, business logic. That's perfect for learning one concept. But a real app with dozens of resources, auth, background tasks, and services becomes a **2000-line `main.py`** that is:

- **Hard to navigate** — where's the bid-validation logic? Somewhere in the wall of code.
- **Hard to test** — business logic is tangled with HTTP handling.
- **Hard for teams** — everyone edits the same file; merge conflicts everywhere.
- **Hard to change** — swapping the database touches everything.

The fix is **separation of concerns**: split the code into layers, each with **one job**.

> 🔑 A single `main.py` is fine for a demo, wrong for a product. Production apps organize code into **layers** so each piece has one responsibility and one place to live.

---

## 2. The Standard Layered Structure

The layout most production FastAPI projects converge on:

```text
app/
├── main.py            # assembles the app: creates FastAPI(), includes routers
├── core/              # cross-cutting concerns: config, security
│   ├── config.py
│   └── security.py
├── db/                # database setup: engine, Session, Base, get_db
│   └── base.py
├── models/            # SQLAlchemy models (database tables)
│   └── item.py
├── schemas/           # Pydantic schemas (API request/response shapes)
│   └── item.py
├── services/          # business logic (the "what the app does")
│   └── item_service.py
├── api/               # the HTTP layer: routers + shared dependencies
│   ├── deps.py
│   └── routes/
│       └── items.py
└── tests/             # the test suite (Phase 5)
    └── test_items.py
```

Each folder is a **layer** with a single responsibility. You always know where a given kind of code belongs.

---

## 3. What Each Layer Does

| Layer | Responsibility | Contains |
|---|---|---|
| **`core/`** | App-wide concerns | Configuration (Lesson 45), security helpers — password hashing, JWT (Lesson 29) |
| **`db/`** | Database plumbing | `engine`, `SessionLocal`, `Base`, the `get_db` dependency |
| **`models/`** | Persistence | SQLAlchemy models = database tables |
| **`schemas/`** | API contract | Pydantic `Create`/`Read`/`Update` schemas |
| **`services/`** | Business logic | The rules and operations, independent of HTTP |
| **`api/`** | HTTP layer | Routers (endpoints) + shared dependencies |
| **`main.py`** | Assembly | Creates the app, wires routers and middleware |
| **`tests/`** | Verification | The pytest suite |

Two folders you already know deserve emphasis: **`models/` vs `schemas/`** — the SQLAlchemy-model / Pydantic-schema split from Lesson 23, now given their own directories. And the **new** layer to internalize is **`services/`**.

---

## 4. The Services Layer — The Key Idea

The single most important structural idea in this lesson: **keep business logic out of your route functions.** Routes should be **thin** — parse the request, call a service, return the result. The **service** holds the actual logic.

```python
# api/routes/items.py  — THIN: HTTP only
@router.post("/items", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    return item_service.create_item(db, payload)   # delegate to the service

# services/item_service.py  — the actual logic, no HTTP
def create_item(db: Session, payload: ItemCreate) -> Item:
    if db.scalar(select(Item).where(Item.sku == payload.sku)):
        raise DuplicateSKUError(payload.sku)       # a domain error, not HTTPException
    item = Item(**payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item
```

Why separate them?

- **Testable** — you can test `create_item` logic without HTTP, TestClient, or a router.
- **Reusable** — the same service can be called from a route, a background task, a WebSocket handler, or a CLI.
- **Swappable** — change the HTTP framework or add a GraphQL layer without rewriting the logic.
- **Readable** — routes read like a table of contents; services hold the details.

> 🔑 **Routes handle HTTP; services handle logic.** A route that's more than a few lines usually has business logic that belongs in a service. This split is what makes a codebase scale and stay testable.

---

## 5. The Request Flow Through the Layers

A request travels **down** through the layers and a response comes back **up**:

```
HTTP request
   │
   ▼
api/routes/items.py    ── validates input via schemas/, gets a session from db/
   │                       (thin: no business logic here)
   ▼
services/item_service.py ── applies business rules, uses models/
   │
   ▼
models/item.py + db/    ── reads/writes the database
   │
   ▲  returns a model object
services  ─► route serializes it via schemas/ (response_model)
   │
   ▼
HTTP response
```

- `schemas/` defines what comes **in** and goes **out**.
- `db/` provides the session (`get_db`).
- `services/` does the work using `models/`.
- `core/` supplies config and security to whoever needs them.

---

## 6. Dependency Direction — Avoiding Spaghetti

Layers should depend **inward/downward**, never in a cycle:

```
api  ──►  services  ──►  models  ──►  db
 │                         ▲
 └──────► schemas          │
core (config/security) ────┘  (used by many, depends on few)
```

- **`api`** may import `services`, `schemas`, `db`, `core`.
- **`services`** may import `models`, `schemas`, `core` — but **not** `api` (logic shouldn't know about routes).
- **`models`** import only `db` (Base) and `core`.
- **`core`** depends on almost nothing.

If `services` starts importing from `api`, you have a **circular dependency** and the layering has broken down.

> 🔑 Dependencies flow one way: **outer layers know about inner ones, not vice-versa.** `services` never imports `api`. Keeping the arrows pointing one direction is what prevents a tangled codebase.

---

## 7. A Thin `main.py`

With everything in its layer, `main.py` becomes a small **assembly point** — it creates the app and wires the pieces:

```python
# app/main.py
from fastapi import FastAPI
from app.api.routes import items, users
from app.db.base import Base, engine

Base.metadata.create_all(bind=engine)   # (Alembic in real prod - Lesson 24)

app = FastAPI(title="My API")
app.include_router(items.router)
app.include_router(users.router)
```

Run it with `uvicorn app.main:app --reload`. `main.py` doesn't *do* anything itself — it just **connects** the layers. That's the sign of a well-structured app.

---

## 8. Domain-Level Errors vs HTTP Errors

A subtle but important consequence of layering: **services shouldn't raise `HTTPException`.** `HTTPException` is an HTTP concern; a service is HTTP-agnostic. Instead, services raise **domain errors**, and the API layer translates them to HTTP responses (via exception handlers, Lesson 13):

```python
# services raise domain errors:
class ItemNotFoundError(Exception): ...

# api/ translates them (in main.py or a handlers module):
@app.exception_handler(ItemNotFoundError)
def handle_not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

This keeps services reusable outside HTTP (a background task calling a service gets a clean exception, not an `HTTPException` it can't use). *(For small apps, raising `HTTPException` in services is a common pragmatic shortcut — but know the cleaner boundary.)*

---

## 9. Two Ways to Organize — By Layer vs By Feature

The structure above is **by layer** (all models together, all routes together). An alternative is **by feature** (each feature owns its models/schemas/routes):

```
by layer:                 by feature:
app/                      app/
├── models/               ├── items/
├── schemas/              │   ├── models.py
├── services/             │   ├── schemas.py
└── api/routes/           │   ├── service.py
                          │   └── router.py
                          └── users/
                              └── ...
```

- **By layer** — simpler for small/medium apps; the syllabus structure; easy to find "all the models."
- **By feature** — scales better for very large apps; each feature is self-contained and can be owned by a team.

Both are legitimate. This lesson uses **by layer** (the common default); large teams often migrate to **by feature**.

> 💡 Start **by layer**. If the app grows huge and teams own distinct domains, consider **by feature**. Consistency matters more than which you pick.

---

## 10. Real-World Use Case — The Auction API, Structured

Recall the Phase 4 auction API. As one `main.py` it would be unmaintainable. Structured:

- `models/auction.py`, `models/bid.py` — the tables.
- `schemas/auction.py`, `schemas/bid.py` — the API contracts.
- `services/bidding.py` — the atomic bid logic (testable without a router).
- `core/security.py` — JWT + hashing; `core/config.py` — settings.
- `db/base.py` — engine, session, `get_db`.
- `api/routes/auctions.py`, `api/routes/bids.py` — thin endpoints delegating to services.
- `api/deps.py` — `get_current_user`, pagination params.
- `main.py` — assembles it all.

Now a new developer knows exactly where bid logic lives (`services/bidding.py`), can unit-test it in isolation, and the same service is callable from the WebSocket handler and the background auction-closer. That's the payoff of structure.

---

## 11. Mini Task

This lesson's `app/` package is a working, layered mini-API. Explore it.

1. Install: `pip install fastapi uvicorn sqlalchemy httpx pytest`
2. Run it: `uvicorn app.main:app --reload` (from the lesson folder) → open `/docs`.
3. Run the tests: `pytest` → the service and endpoint tests pass.
4. **Trace a request:** follow `POST /items` from `api/routes/items.py` → `services/item_service.py` → `models/item.py`. Notice the route is thin and the logic lives in the service.
5. **Experiment:**
   - Add a new resource (`users`) with its own model, schema, service, and route — copy the item layer's shape.
   - Move a piece of logic from a route into its service and re-run the tests.
   - Try to import `api` from a service and notice why that's a smell (circular dependency).
6. **Bonus:** Convert the layout **by feature** (an `items/` package with `models.py`, `schemas.py`, `service.py`, `router.py`) and compare.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Business logic inside route functions | Move it to a `services/` module; keep routes thin. |
| One giant `main.py` | Split into layers; `main.py` only assembles. |
| Circular imports (`services` importing `api`) | Dependencies flow one way: api → services → models. |
| Mixing models and schemas in one place | Separate `models/` (SQLAlchemy) and `schemas/` (Pydantic). |
| `HTTPException` deep in services | Raise domain errors; translate in the API layer. |
| Inconsistent structure across the app | Pick by-layer or by-feature and apply it everywhere. |
| Putting config/secrets in random files | Centralize in `core/config.py` (Lesson 45). |

---

## 13. Key Takeaways

- A single `main.py` doesn't scale; production apps use a **layered structure** with one responsibility per layer.
- The standard layout: **`core/`** (config, security), **`db/`** (engine/session/Base), **`models/`** (tables), **`schemas/`** (API contract), **`services/`** (business logic), **`api/`** (routers + deps), thin **`main.py`**, **`tests/`**.
- The key move: **routes stay thin (HTTP only); services hold the business logic** — making it testable, reusable, and swappable.
- Requests flow **down** through the layers; **dependencies point one way** (api → services → models), never in a cycle.
- `main.py` is a small **assembly point** that wires routers and middleware.
- Prefer **domain errors** in services, translated to HTTP in the API layer.
- **By-layer** is the common default; **by-feature** scales for large teams. Consistency matters most.

---

## ➡️ Next Lesson

**Lesson 45 — Configuration Management**
- `pydantic-settings` for typed, validated config
- `.env` files and environment variables
- Separate dev / staging / prod settings
