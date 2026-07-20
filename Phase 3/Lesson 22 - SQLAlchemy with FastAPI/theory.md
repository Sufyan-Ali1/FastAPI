# Lesson 22 — SQLAlchemy with FastAPI

> **Goal of this lesson:** Connect the ORM from Lesson 21 to a real FastAPI app. Learn the **`get_db` dependency** (a database Session per request, using the `yield` pattern from Lesson 14), and build **full CRUD endpoints** — Create, Read, Update, Delete — backed by SQLite through SQLAlchemy.
>
> This is the lesson where your API stops using JSON files and starts using a **real database**. `main.py` is a runnable FastAPI app (`uvicorn main:app --reload`).

---

## 1. Where We Are

- **Lesson 20:** database concepts (SQL, connections, pooling, ORM).
- **Lesson 21:** SQLAlchemy on its own — Engine, Base, Session, models, relationships.
- **Lesson 22 (now):** put the Session inside FastAPI so every request can read/write the database.

The one new idea: **each HTTP request gets its own Session**, opened at the start and closed at the end. FastAPI's **dependency injection** (Lesson 14) makes this clean.

> 🔑 The golden rule: **one Session per request.** Not one global session, not one per app. Open it when the request starts, close it when the request ends.

---

## 2. Why One Session Per Request?

A Session wraps a transaction and is **not thread-safe**. If you shared one global Session across all requests:

- Concurrent requests would corrupt each other's transaction state.
- A failure in one request could roll back another's work.
- Objects would leak between unrelated requests.

So instead: borrow a connection from the pool, wrap it in a fresh Session, do the request's work, commit or roll back, then return the connection to the pool. That "borrow → use → return" is exactly the **connection pool** behaviour from Lesson 20 — and SQLAlchemy's Engine handles the pool for you.

---

## 3. The Database Setup

Three objects set up once for the whole app (in a real project these live in a `database.py`; we keep them at the top of `main.py` for now — production structure is Lesson 44):

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 1. The Engine (owns the connection pool)
engine = create_engine(
    "sqlite:///shop.db",
    echo=True,
    connect_args={"check_same_thread": False},  # SQLite + FastAPI, see §9
)

# 2. A Session factory - call SessionLocal() to get a new Session
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# 3. The declarative Base for all models
class Base(DeclarativeBase):
    pass
```

### 3.1 `sessionmaker` — the Session factory

In Lesson 21 we wrote `Session(engine)` directly. In an app we instead build a **factory** with `sessionmaker`, then call `SessionLocal()` whenever we need a session. It bakes in the engine and our preferred settings:

| Setting | Meaning |
|---|---|
| `bind=engine` | Every session uses this engine's pool. |
| `autoflush=False` | Don't auto-send pending SQL before every query (more predictable). |
| `autocommit=False` | You control transactions explicitly with `commit()`. (This is the only supported value in 2.0.) |

> 🔑 `engine` and `SessionLocal` are created **once**. `SessionLocal()` is called **per request** to make a short-lived Session.

---

## 4. The `get_db` Dependency (the heart of this lesson)

This is the standard pattern for giving each request a Session. It uses **`yield`** — the cleanup-style dependency from Lesson 14:

```python
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()      # open a session (borrow a pooled connection)
    try:
        yield db             # hand it to the endpoint
    finally:
        db.close()           # ALWAYS runs - return the connection to the pool
```

How FastAPI uses it:

1. A request arrives at an endpoint that declares `db: Session = Depends(get_db)`.
2. FastAPI runs `get_db` up to the `yield`, creating a Session.
3. The value after `yield` (the `db`) is injected into your endpoint.
4. Your endpoint runs its queries using `db`.
5. When the response is sent, FastAPI resumes `get_db` **after** the `yield`, running the `finally` block → `db.close()`.

```python
from fastapi import Depends

@app.get("/products")
def list_products(db: Session = Depends(get_db)):
    return db.scalars(select(Product)).all()
```

The endpoint never opens or closes the session — the dependency owns its lifecycle. Every endpoint just asks for `db` and uses it.

> 💡 `Annotated` shorthand keeps signatures clean and is the modern style:
> ```python
> from typing import Annotated
> DB = Annotated[Session, Depends(get_db)]
>
> @app.get("/products")
> def list_products(db: DB):
>     ...
> ```

---

## 5. Creating the Tables

Models are defined exactly as in Lesson 21. We create their tables once, at startup, using FastAPI's **lifespan** handler:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # create tables if missing
    yield                                   # app runs here
    # (shutdown cleanup could go here)

app = FastAPI(lifespan=lifespan)
```

> 🔑 `create_all` only creates tables that don't exist yet. Changing a model later (adding a column) will **not** update the table — that needs **Alembic migrations** (Lesson 24). For now, if you change a model during learning, delete `shop.db` and restart.

---

## 6. Request Schemas (Pydantic) vs Models (SQLAlchemy)

You now have **two kinds of classes** that look similar but do different jobs:

| Class kind | Base class | Job |
|---|---|---|
| **Model** | `Base` (SQLAlchemy) | A database table. Persists rows. |
| **Schema** | `BaseModel` (Pydantic) | Validates request bodies / shapes responses. |

For request bodies we use Pydantic, exactly like Phase 1/2:

```python
from pydantic import BaseModel, Field

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    sku: str = Field(..., min_length=3, max_length=30)
    price: float = Field(..., gt=0)
    supplier_id: int = Field(..., ge=1)
```

The endpoint receives a validated `ProductCreate`, then builds a `Product` **model** from it to save.

> ⚠️ **Responses in this lesson are shaped by hand** (a small `to_dict` helper), because returning a SQLAlchemy model directly doesn't serialize automatically. That's deliberate — **Lesson 23** introduces `from_attributes=True` (ORM mode) and `response_model`, which makes responses automatic and clean. Here we keep the focus on the **session + CRUD** mechanics.

---

## 7. CRUD — The Four Operations

This is the core skill. Each maps a SQL operation from Lesson 20 to a FastAPI endpoint using `db`.

### 7.1 CREATE — `POST` (201)

```python
@app.post("/products", status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**payload.model_dump())   # schema -> model
    db.add(product)
    try:
        db.commit()                             # INSERT
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "SKU already exists")
    db.refresh(product)                         # load the DB-generated id
    return to_dict(product)
```

- `db.add()` stages, `db.commit()` writes.
- A duplicate `sku` violates the `UNIQUE` constraint → SQLAlchemy raises `IntegrityError` → we roll back and return **409** (the database enforces uniqueness, not a manual loop!).
- `db.refresh()` reloads the row so the generated `id` is available.

### 7.2 READ — `GET` (list + one)

```python
@app.get("/products")
def list_products(
    db: Session = Depends(get_db),
    q: str | None = None,
    min_price: float | None = None,
):
    stmt = select(Product)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))   # case-insensitive
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    products = db.scalars(stmt.order_by(Product.id)).all()
    return [to_dict(p) for p in products]

@app.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return to_dict(product)
```

- Filtering happens **in SQL** (`.where`, `.ilike`, `.order_by`) — the database does the work, not Python loops over a JSON file.
- `db.get(Model, pk)` fetches by primary key; `None` → **404**.

### 7.3 UPDATE — `PUT` (full replace)

```python
@app.put("/products/{product_id}")
def update_product(product_id: int, payload: ProductCreate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    for field, value in payload.model_dump().items():
        setattr(product, field, value)          # mutate attributes
    db.commit()                                 # ORM writes the UPDATE
    db.refresh(product)
    return to_dict(product)
```

You mutate the loaded object's attributes; `commit()` generates the `UPDATE`.

### 7.4 DELETE — `DELETE` (204)

```python
@app.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    db.delete(product)
    db.commit()
    # 204 => return nothing
```

---

## 8. The Full Request Lifecycle

Putting it all together, here's what happens on `POST /products`:

```
1. Request arrives with a JSON body.
2. Pydantic validates the body into a ProductCreate.        (422 if invalid)
3. Depends(get_db) opens a Session (borrows a pooled conn).
4. Endpoint builds a Product model and db.add() + db.commit().
5. SQLAlchemy sends INSERT; the DB assigns an id.
6. db.refresh() reloads the row.
7. Endpoint returns a dict -> FastAPI serializes to JSON (201).
8. FastAPI resumes get_db past the yield -> db.close().
9. The connection returns to the pool for the next request.
```

Every endpoint follows this same skeleton. The only thing that changes is the CRUD in the middle.

---

## 9. The SQLite + FastAPI Gotcha

SQLite, by default, refuses to use a connection across different threads. FastAPI runs **sync** endpoint functions in a **threadpool**, so a session may touch the DB from a different thread than the one that created the connection. Two settings handle this:

```python
create_engine(
    "sqlite:///shop.db",
    connect_args={"check_same_thread": False},   # allow cross-thread use
)
```

- `check_same_thread=False` is **SQLite-specific** — you don't need it for PostgreSQL/MySQL.
- It's safe here because each request still uses its **own** session, and the pool serializes access.

> 💡 This is the single most common "it works in Lesson 21 but breaks in FastAPI" error. Remember it.

---

## 10. Real-World Use Case — Retiring `products.json`

Compare the Phase 1 Inventory API's create-product logic:

```python
# Phase 1 (JSON files)
products = load_json("products.json")
if any(p["sku"] == payload.sku for p in products):     # manual uniqueness
    raise HTTPException(409, "Duplicate SKU")
new_id = max((p["id"] for p in products), default=0) + 1  # manual id
products.append({"id": new_id, **payload.model_dump()})
save_json("products.json", products)                   # rewrite whole file
```

versus this lesson:

```python
# Phase 3 (database)
product = Product(**payload.model_dump())
db.add(product)
try:
    db.commit()                                        # DB enforces UNIQUE + id
except IntegrityError:
    db.rollback()
    raise HTTPException(409, "SKU already exists")
db.refresh(product)
```

- Uniqueness → a `UNIQUE` constraint, not a loop.
- IDs → the database, not `max(...) + 1`.
- No whole-file rewrite; concurrent requests are safe.

That's the Phase 3 payoff, live in a FastAPI app.

---

## 11. Mini Task

`main.py` is a runnable FastAPI app for a small **Products + Suppliers** API backed by SQLite.

1. Install deps if needed: `pip install fastapi uvicorn sqlalchemy`
2. Run it:
   ```bash
   uvicorn main:app --reload
   ```
3. Open `http://127.0.0.1:8000/docs` and try, in order:
   - `POST /suppliers` → create a supplier (note the returned `id`).
   - `POST /products` with that `supplier_id` → **201**.
   - `POST /products` again with the **same `sku`** → **409** (the DB rejected the duplicate).
   - `GET /products?q=key&min_price=10` → filtered list.
   - `GET /products/{id}` for a missing id → **404**.
   - `PUT /products/{id}` → change the price, then `GET` it again.
   - `DELETE /products/{id}` → **204**, then `GET` it → **404**.
4. Stop the server and restart it → your data is still there (`shop.db`). No more losing data on restart.
5. **Bonus:** Add `GET /suppliers/{supplier_id}/products` that returns a supplier's products via the relationship (`supplier.products`). Return 404 if the supplier doesn't exist.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| One global Session for the whole app | Use `get_db` so each request gets its own Session. |
| Forgetting `db.commit()` | Writes are discarded when the session closes. |
| Not calling `db.rollback()` after an error | Leaves the session in a broken state; always roll back on failure. |
| Returning a SQLAlchemy model directly | Doesn't serialize cleanly yet — shape it (Lesson 23 automates this). |
| Missing `check_same_thread=False` for SQLite | Threadpool errors under FastAPI. |
| Expecting model changes to alter tables | `create_all` won't migrate; delete `shop.db` or use Alembic (Lesson 24). |
| Not calling `db.refresh()` after insert | The generated `id` (and defaults) won't be populated on the object. |

---

## 13. Key Takeaways

- **One Session per request.** `engine` and `SessionLocal` are app-wide singletons; `SessionLocal()` runs per request.
- **`get_db` with `yield`** is the canonical dependency: open a Session, `yield` it, `close()` in `finally`.
- Endpoints declare `db: Session = Depends(get_db)` (or an `Annotated` alias) and never manage the session lifecycle themselves.
- Create tables once at startup with `Base.metadata.create_all` in a **lifespan** handler.
- **CRUD** maps cleanly: `add`+`commit` (create), `get`/`select` (read), attribute mutation+`commit` (update), `delete`+`commit` (delete).
- The database enforces **UNIQUE** (catch `IntegrityError` → 409) and generates **IDs** — no manual loops.
- SQLite under FastAPI needs `connect_args={"check_same_thread": False}`.
- Responses are shaped by hand **for now** — Lesson 23 makes them automatic with `from_attributes` + `response_model`.

---

## ➡️ Next Lesson

**Lesson 23 — Pydantic + SQLAlchemy Together**
- `from_attributes=True` (ORM mode) so Pydantic can read model objects directly
- `response_model` for automatic, clean responses
- Proper **schema vs model** separation (`ProductCreate`, `ProductRead`, `ProductUpdate`)
