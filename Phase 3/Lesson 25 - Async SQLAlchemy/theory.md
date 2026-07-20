# Lesson 25 — Async SQLAlchemy

> **Goal of this lesson:** Rebuild the database layer the **async** way. Learn `create_async_engine`, `AsyncSession`, the `async def get_db` dependency, and `await`-ing queries in `async def` endpoints. Then — just as important — learn **when async DB access actually helps and when plain sync is the right call.**
>
> `main.py` is the Lesson 23 Products API converted to fully async. Compare them line by line.

---

## 1. Quick Refresher — Sync vs Async

FastAPI supports two kinds of endpoint functions:

```python
@app.get("/a")
def sync_endpoint():        # runs in a threadpool
    ...

@app.get("/b")
async def async_endpoint(): # runs on the event loop
    ...
```

- A **`def`** endpoint runs in FastAPI's **threadpool** — fine for blocking work.
- An **`async def`** endpoint runs on the **event loop** — but it must **never block**. Every slow I/O call inside it must be `await`ed so the loop can serve other requests meanwhile.

The database is I/O. In an `async def` endpoint, a **blocking** (sync) DB call would freeze the whole event loop. So if your endpoints are `async def`, your database calls must be `async` too. That's what async SQLAlchemy provides.

> 🔑 The rule: **don't block the event loop.** Sync DB in `async def` = blocking. Either use sync DB in `def` endpoints (Lessons 22–24) **or** async DB in `async def` endpoints (this lesson). Don't mix a blocking DB call into an `async def`.

(The deep dive on async vs sync and the event loop is **Lesson 28**. This lesson is the practical DB mechanics.)

---

## 2. What Changes Going Async

The concepts are identical to sync SQLAlchemy — same models, same `select()`, same session idea. Only the **plumbing** gains `async`/`await`:

| Sync (Lessons 22–24) | Async (this lesson) |
|---|---|
| `create_engine(url)` | `create_async_engine(url)` |
| driver `sqlite://` | async driver `sqlite+aiosqlite://` |
| `sessionmaker(...)` → `Session` | `async_sessionmaker(...)` → `AsyncSession` |
| `def get_db()` + `yield` | `async def get_db()` + `async with` |
| `db.execute(stmt)` | `await db.execute(stmt)` |
| `db.get(Model, id)` | `await db.get(Model, id)` |
| `db.commit()` | `await db.commit()` |
| `db.refresh(obj)` | `await db.refresh(obj)` |
| `def endpoint(...)` | `async def endpoint(...)` |

> 🔑 **The models don't change at all.** `Supplier`, `Product`, `Mapped[...]`, `mapped_column(...)`, relationships — all identical. Async only affects the engine, session, and the `await`ed calls.

---

## 3. The Async Driver

Async needs a database driver that speaks async. You pick it in the URL:

| Database | Sync URL | Async URL | Async driver to install |
|---|---|---|---|
| SQLite | `sqlite:///shop.db` | `sqlite+aiosqlite:///shop.db` | `aiosqlite` |
| PostgreSQL | `postgresql+psycopg://...` | `postgresql+asyncpg://...` | `asyncpg` |
| MySQL | `mysql+pymysql://...` | `mysql+aiomysql://...` | `aiomysql` |

```bash
pip install aiosqlite      # for this lesson
```

The `+aiosqlite` part tells SQLAlchemy to use the async driver.

---

## 4. The Async Engine and Session Factory

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine("sqlite+aiosqlite:///shop.db", echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,   # keep attributes usable after commit (see §6)
    autoflush=False,
)
```

- **`create_async_engine`** — the async twin of `create_engine`. Same pooling ideas (Lesson 20), now non-blocking.
- **`async_sessionmaker`** — produces `AsyncSession` objects instead of `Session`.
- **`expire_on_commit=False`** — important. By default SQLAlchemy *expires* objects after `commit()`, so the next attribute access reloads them from the DB. In async that reload is itself an awaitable — accessing `product.id` after commit without awaiting can raise. Setting this to `False` keeps the committed object's attributes loaded, which is what you want for returning it in a response.

> 💡 We no longer pass `connect_args={"check_same_thread": False}`. That was a workaround for **sync** SQLite running across threadpool threads. The async driver runs on a single event loop, so it isn't needed here.

---

## 5. The Async `get_db` Dependency

Same idea as Lesson 22 — one session per request — now `async`:

```python
async def get_db():
    async with AsyncSessionLocal() as db:   # async context manager
        yield db                            # closes automatically on exit
```

- `async with` opens the `AsyncSession` and **guarantees it closes** when the request ends (replacing the `try/finally` + `close()`).
- It's still an injected dependency: `db: AsyncSession = Depends(get_db)`.

```python
from typing import Annotated
DB = Annotated[AsyncSession, Depends(get_db)]
```

FastAPI fully supports `async def` dependencies — it awaits them on the event loop.

---

## 6. Async CRUD — `await` Everything

The endpoints become `async def` and every DB call is `await`ed. Reads use `await db.execute(stmt)` then `.scalars()`:

### Create

```python
@app.post("/products", response_model=ProductRead, status_code=201)
async def create_product(payload: ProductCreate, db: DB):
    if await db.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(404, "Supplier not found")

    product = Product(**payload.model_dump())
    db.add(product)                     # add() is NOT awaited (no I/O yet)
    try:
        await db.commit()               # awaited: this hits the DB
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "SKU already exists")
    await db.refresh(product)
    return product
```

Note: `db.add(product)` is **not** awaited — it only stages the object in memory. The I/O happens at `await db.commit()`.

### Read (one and list)

```python
@app.get("/products/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, db: DB):
    product = await db.get(Product, product_id)     # awaited
    if product is None:
        raise HTTPException(404, "Product not found")
    return product

@app.get("/products", response_model=list[ProductRead])
async def list_products(db: DB, q: str | None = None):
    stmt = select(Product)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    result = await db.execute(stmt.order_by(Product.id))   # awaited
    return result.scalars().all()                          # unwrap objects
```

> 🔑 Sync 2.0 lets you write `db.scalars(stmt)` as a shortcut. In async the common pattern is `result = await db.execute(stmt)` then `result.scalars().all()`. (`await db.scalars(stmt)` also exists.) Either way, the `await` is on the DB round-trip.

### Update and delete

```python
# UPDATE (PATCH)
product = await db.get(Product, product_id)
for field, value in payload.model_dump(exclude_unset=True).items():
    setattr(product, field, value)
await db.commit()
await db.refresh(product)

# DELETE
product = await db.get(Product, product_id)
await db.delete(product)
await db.commit()
```

---

## 7. Creating Tables Async (lifespan)

`Base.metadata.create_all` is a sync function; with an async engine you run it through `engine.begin()` + `run_sync`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()   # cleanly close the pool on shutdown
```

- `run_sync` bridges the sync `create_all` onto the async connection.
- In a real project you'd use **Alembic** (Lesson 24) instead of `create_all`; this is just for the demo.
- `await engine.dispose()` releases pooled connections at shutdown.

---

## 8. A Big Async Gotcha — Lazy-Loaded Relationships

In **sync** SQLAlchemy, accessing `product.supplier` lazily fires a query on demand. In **async**, lazy loading **doesn't work by default** — the implicit query would need an `await` it can't insert, and you'll get an error like *"greenlet_spawn has not been called"*.

Two clean fixes:

1. **Eager-load** the relationship in the query with `selectinload`:
   ```python
   from sqlalchemy.orm import selectinload

   stmt = select(Product).options(selectinload(Product.supplier)).where(Product.id == pid)
   product = (await db.execute(stmt)).scalars().first()
   # product.supplier is now already loaded -> safe to serialize
   ```
2. Or design the response so it doesn't touch un-loaded relationships.

> 🔑 Async + relationships = **load them explicitly** (`selectinload`, `joinedload`). Don't rely on lazy loading. (This also dovetails with fixing the **N+1 problem** in Lesson 48.)

---

## 9. When to Use Async vs Sync (the important judgment call)

Async is not automatically "faster" or "better." It helps in a specific situation.

**Async DB shines when:**
- Your service is **I/O-bound** and handles **many concurrent requests** that each wait on the database (or other network calls). While one request awaits the DB, the event loop serves others on the same worker.
- You're already `async` for other reasons — calling external async APIs, WebSockets, streaming (Lessons 31–32), LLM calls.

**Plain sync is perfectly fine (often better) when:**
- Your app is simple or low-traffic — the complexity of async isn't worth it.
- Your endpoints do **CPU-bound** work — async doesn't help CPU-bound code (that needs processes/threads; Lesson 28).
- You (or your team) are still getting comfortable — sync SQLAlchemy is simpler to reason about and debug.

**The honest trade-offs:**

| | Sync SQLAlchemy | Async SQLAlchemy |
|---|---|---|
| Endpoint style | `def` (threadpool) | `async def` (event loop) |
| Concurrency model | Threads | Event loop |
| Lazy relationships | Just work | Must eager-load |
| Debugging | Simpler stack traces | Harder (async internals) |
| Ecosystem/driver maturity | Very mature | Mature, slightly fewer drivers |
| Best for | Most CRUD apps, learning | High-concurrency I/O-bound services |

> 🔑 **Don't cargo-cult async.** FastAPI runs your **sync** `def` endpoints in a threadpool perfectly well — a sync SQLAlchemy CRUD app can serve serious traffic. Reach for async DB when you have **many concurrent I/O-bound requests**, or you're already in an async stack. When in doubt for a straightforward CRUD API, **sync is a fine, professional choice.**

---

## 10. Real-World Use Case — A High-Concurrency Read API

Picture a product-catalog API behind a busy storefront: thousands of concurrent `GET /products` requests, each a quick DB read, plus some calls out to a pricing microservice.

- **Sync:** each in-flight request occupies a threadpool thread while it waits on the DB/network. Under heavy concurrency you exhaust threads and queue up.
- **Async:** while each request `await`s the DB and the pricing service, the event loop serves other requests on the same worker. You handle far more simultaneous waiting requests per process.

That's the sweet spot for async: **lots of requests, each mostly waiting on I/O.** For a low-traffic internal CRUD tool, sync would be simpler and just as good.

---

## 11. Mini Task

`main.py` is the Lesson 23 API, fully async.

1. Install the async driver: `pip install aiosqlite`
2. Run it: `uvicorn main:app --reload` → open `/docs`. The endpoints look identical in Swagger — async is invisible to clients.
3. Exercise the same flows as Lesson 23:
   - `POST /suppliers`, `POST /products` → 201.
   - Duplicate SKU → 409; missing supplier → 404.
   - `GET /products/{id}/full` → note it uses `selectinload` to eager-load the supplier (§8).
   - `PATCH` with a single field; `DELETE` → 204.
4. **Prove the gotcha:** in `get_product_full`, temporarily remove the `selectinload(...)` option and access `product.supplier` — observe the async lazy-load error. Put it back.
5. **Bonus:** Add `GET /suppliers/{id}/full` returning the supplier with its `products` list, using `selectinload(Supplier.products)`. Return 404 if missing.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Blocking (sync) DB call inside `async def` | Use async DB calls, or make the endpoint `def`. |
| Forgetting `await` on `execute`/`commit`/`get`/`refresh` | Every DB round-trip must be `await`ed. |
| Using the sync `sqlite:///` URL with the async engine | Use `sqlite+aiosqlite:///`. |
| Lazy-accessing a relationship | Eager-load with `selectinload`/`joinedload`. |
| Attribute access errors after commit | Set `expire_on_commit=False` on the session factory. |
| `create_all` called directly on async engine | Wrap with `await conn.run_sync(Base.metadata.create_all)`. |
| Choosing async "because it's faster" | Async helps I/O-bound concurrency; sync is fine for most CRUD. |

---

## 13. Key Takeaways

- Async DB exists so `async def` endpoints don't **block the event loop** on database I/O.
- Swap the plumbing: `create_async_engine`, `async_sessionmaker` → `AsyncSession`, `async def get_db` with `async with`. **Models are unchanged.**
- Use an **async driver** in the URL: `sqlite+aiosqlite://` (or `postgresql+asyncpg://`).
- **`await`** every DB round-trip: `execute`, `get`, `commit`, `refresh`, `delete`. Read via `await db.execute(stmt)` → `.scalars().all()`.
- Set **`expire_on_commit=False`**; create tables via `run_sync`; `await engine.dispose()` on shutdown.
- Async **lazy loading doesn't work** — eager-load relationships with `selectinload`.
- **Choose deliberately:** async for high-concurrency I/O-bound services; **sync is perfectly professional** for most CRUD apps. Don't cargo-cult async.

---

## ➡️ Next Lesson

**Lesson 26 — SQLModel**
- The library by FastAPI's author that fuses SQLAlchemy + Pydantic into one class
- One model instead of separate ORM model + Pydantic schema
- Trade-offs vs. keeping them separate (Lesson 23)
