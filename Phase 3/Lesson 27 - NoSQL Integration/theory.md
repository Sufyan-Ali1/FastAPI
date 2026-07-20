# Lesson 27 — NoSQL Integration (Optional)

> **Goal of this lesson:** Step outside SQL. Learn to use **MongoDB** (a document database) with the async **Motor** driver and the **Beanie** ODM, and **Redis** (a key-value store) for **caching**. Understand *when* a document or key-value store fits better than SQL — and when it doesn't.
>
> This is the **optional** closer of Phase 3. `main.py` is runnable **without installing any servers**: it uses in-memory fakes (`mongomock-motor`, `fakeredis`) that expose the *exact same API* as real MongoDB/Redis — switching to real servers is a one-line change.

---

## 1. Where We Are

All of Phase 3 so far has been **SQL / relational** (SQLite, SQLAlchemy, SQLModel). That's the right default for most backends. But two **NoSQL** stores show up constantly in real systems, often *alongside* SQL:

| Store | Type | Classic job |
|---|---|---|
| **MongoDB** | Document database | Flexible/nested data, fast iteration |
| **Redis** | Key-value store (in-memory) | Caching, sessions, rate limiting, queues |

Recall the NoSQL families from Lesson 20 — this lesson makes two of them concrete.

> 🔑 NoSQL is **not** a replacement for SQL. Most production systems are **polyglot**: PostgreSQL for core relational data, Redis for caching, sometimes MongoDB for a flexible-schema slice. Use the right tool per need.

---

## 2. MongoDB — A Document Database

MongoDB stores **documents** (JSON-like objects) inside **collections** (loosely, "tables"). There's no fixed schema — documents in one collection can have different fields.

| SQL term | MongoDB term |
|---|---|
| Database | Database |
| Table | **Collection** |
| Row | **Document** (a BSON/JSON object) |
| Column | **Field** |
| Primary key `id` | **`_id`** (an `ObjectId` by default) |
| JOIN | (usually) embed, or `$lookup` |

A document:

```json
{
  "_id": ObjectId("665f1c..."),
  "name": "Keyboard",
  "sku": "KB-001",
  "price": 25.0,
  "tags": ["electronics", "office"],
  "specs": { "layout": "US", "wireless": true }
}
```

- **`_id`** is auto-generated (an `ObjectId` — a 12-byte unique id, not a sequential int). In an API you serialize it to a string.
- **Nested/embedded** data is natural — no join table needed for `specs` or `tags`.
- **Flexible schema** — add a field to one document without a migration. (Great for evolving data; risky without discipline, since nothing enforces structure — that's where Beanie helps.)

**When MongoDB fits:** highly variable or deeply nested documents, rapid iteration, denormalized read-heavy data, event/log storage. **When it doesn't:** data with lots of relationships and strong integrity needs — SQL's constraints and JOINs win there.

---

## 3. Motor — The Async MongoDB Driver

**Motor** is the official **async** MongoDB driver (async wrapper over PyMongo). It pairs naturally with `async def` FastAPI endpoints (Lesson 25's async mindset).

```python
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client["shop"]                 # a database
products = db["products"]           # a collection
```

### 3.1 CRUD with Motor (raw)

Everything is `await`ed, like Lesson 25:

```python
from bson import ObjectId

# CREATE
result = await products.insert_one({"name": "Keyboard", "sku": "KB-001", "price": 25.0})
new_id = result.inserted_id                      # an ObjectId

# READ one
doc = await products.find_one({"_id": ObjectId(id_str)})

# READ many (find returns a cursor)
docs = await products.find({"price": {"$gt": 20}}).to_list(length=100)

# UPDATE
await products.update_one({"_id": ObjectId(id_str)}, {"$set": {"price": 29.99}})

# DELETE
await products.delete_one({"_id": ObjectId(id_str)})
```

Note the **query operators**: `{"price": {"$gt": 20}}` means "price > 20". MongoDB queries are documents themselves (`$gt`, `$lt`, `$in`, `$regex`, ...).

> 🔑 Motor is powerful but **schemaless** — you pass raw dicts and get raw dicts back, and you must convert `ObjectId` ↔ string yourself. That's where an ODM helps.

---

## 4. Beanie — An ODM on Top of Motor

**Beanie** is an **ODM** (Object-Document Mapper) — the MongoDB equivalent of an ORM. It's built on **Motor + Pydantic**, so your documents are Pydantic models (very FastAPI-friendly).

```python
from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

class Product(Document):            # a Pydantic model that maps to a collection
    name: str
    sku: str
    price: float

    class Settings:
        name = "products"           # collection name

# once at startup:
client = AsyncIOMotorClient("mongodb://localhost:27017")
await init_beanie(database=client["shop"], document_models=[Product])
```

### 4.1 CRUD with Beanie

Objects and methods instead of raw dicts — much closer to SQLModel:

```python
# CREATE
product = Product(name="Keyboard", sku="KB-001", price=25.0)
await product.insert()

# READ one by id
product = await Product.get(product_id)

# READ many
products = await Product.find(Product.price > 20).to_list()

# UPDATE
product.price = 29.99
await product.save()

# DELETE
await product.delete()
```

| | Motor (raw) | Beanie (ODM) |
|---|---|---|
| Documents are | plain dicts | Pydantic models |
| Validation | none (you do it) | automatic (Pydantic) |
| `ObjectId` handling | manual | built-in |
| Queries | dict operators | typed expressions (`Product.price > 20`) |
| Feel | like raw SQL | like SQLModel |

> 🔑 **Motor = raw driver (control, dicts). Beanie = ODM (Pydantic models, ergonomics).** For a FastAPI app, Beanie is usually the nicer choice — it gives MongoDB the same "objects + validation" experience SQLModel gives SQL.

---

## 5. Redis — In-Memory Key-Value Store

**Redis** keeps data **in memory** (RAM), so reads/writes are *extremely* fast (microseconds). It's a **key → value** store: you `SET` a key and `GET` it later. Values can be strings, hashes, lists, sets, and more.

Redis is rarely your **primary** database (memory is volatile and limited). Instead it's a **support** store for:

| Use | How |
|---|---|
| **Caching** ⭐ | Store expensive results; serve them fast (this lesson) |
| **Sessions** | Store login sessions with a TTL |
| **Rate limiting** | Count requests per user/IP (Lesson 34) |
| **Queues / pub-sub** | Background jobs, real-time messaging |

The killer feature for caching is **TTL (time-to-live)** — a key can **auto-expire** after N seconds:

```python
import redis.asyncio as redis

r = redis.from_url("redis://localhost:6379")

await r.set("product:1", json_string, ex=60)   # expires in 60 seconds
value = await r.get("product:1")                # bytes, or None if missing/expired
await r.delete("product:1")                     # remove immediately
```

---

## 6. The Caching Pattern — Cache-Aside (Lazy Loading)

The most common caching strategy. The application checks the cache first, and only hits the slow store on a miss:

```
        ┌─────────────┐   hit    ┌──────────────────┐
GET ───►│ 1. Redis?   │─────────►│ return cached    │  (fast path)
        └──────┬──────┘          └──────────────────┘
               │ miss
               ▼
        ┌─────────────┐          ┌──────────────────┐
        │ 2. Database │─────────►│ 3. store in Redis│──► return
        └─────────────┘          │    with a TTL    │
                                  └──────────────────┘
```

In code (cache-aside read):

```python
async def get_product_cached(product_id: str):
    key = f"product:{product_id}"

    cached = await r.get(key)                 # 1. try cache
    if cached is not None:
        return json.loads(cached)             #    HIT -> fast

    doc = await products.find_one({"_id": ObjectId(product_id)})   # 2. MISS -> DB
    if doc is None:
        raise HTTPException(404, "Not found")

    data = serialize(doc)
    await r.set(key, json.dumps(data), ex=60) # 3. fill cache with TTL
    return data
```

### 6.1 Cache Invalidation

> *"There are only two hard things in Computer Science: cache invalidation and naming things."*

Stale cache is the classic bug: you update the DB but the cache still serves the old value. Rules:

- **On update/delete: invalidate (delete) the cache key**, so the next read re-fetches fresh.
  ```python
  await products.update_one({"_id": oid}, {"$set": {...}})
  await r.delete(f"product:{product_id}")     # <-- critical
  ```
- **Use a TTL** as a safety net, so even a missed invalidation self-heals when the key expires.
- Cache **reads that are expensive and repeated**, not everything.

> 🔑 Two levers keep a cache correct: **explicit invalidation** on writes + a **TTL** backstop. Forgetting the first is the #1 caching bug.

---

## 7. Integrating with FastAPI

Same shape as the SQL lessons: create the client **once** at startup (lifespan), share it, close it on shutdown.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Mongo (Beanie) + Redis clients created once
    client = AsyncIOMotorClient(MONGO_URL)
    await init_beanie(database=client["shop"], document_models=[Product])
    app.state.redis = redis.from_url(REDIS_URL)
    yield
    app.state.redis.close()
    client.close()
```

Endpoints are `async def` and `await` both stores — identical async discipline to Lesson 25.

---

## 8. Choosing the Right Store

| Need | Reach for |
|---|---|
| Structured, related data, integrity, transactions | **SQL** (Postgres / SQLite) — your default |
| Flexible/nested documents, fast iteration | **MongoDB** (Beanie/Motor) |
| Fast caching, sessions, rate limits, ephemeral data | **Redis** |
| All of the above in one app | **Polyglot** — combine them |

A very common production stack: **PostgreSQL** (source of truth) **+ Redis** (cache/sessions). MongoDB appears when a chunk of the domain is genuinely document-shaped.

> 🔑 Don't pick NoSQL for novelty. Start with SQL; add Redis when you need speed/caching; add MongoDB when the data is truly document-shaped. Each solves a *specific* problem.

---

## 9. Real-World Use Case — A Read-Heavy Product Page

Your product detail endpoint is hit thousands of times a minute, but product data changes rarely.

- **Without cache:** every request queries the database → wasted load, higher latency.
- **With Redis cache-aside:** the first request fills the cache; the next thousands are served from RAM in microseconds. On a product edit, you delete that product's cache key so customers see the change; a 60s TTL guarantees eventual freshness even if an invalidation is missed.

MongoDB could store each product as a rich nested document (specs, variants, reviews) with no joins — while Redis fronts it for speed. That's the polyglot pattern in miniature, and it's exactly what `main.py` demonstrates.

---

## 10. Mini Task

`main.py` runs a MongoDB-style **document** API fronted by a Redis **cache** — using in-memory fakes so **no servers are needed**.

1. Install (for the runnable fakes): `pip install fastapi uvicorn "motor" mongomock-motor fakeredis redis`
2. Run: `uvicorn main:app --reload` → open `/docs`.
3. Watch the cache work (responses include a `_source` field so you can *see* hit vs miss):
   - `POST /products` → create a document (note the string `id` from `ObjectId`).
   - `GET /products/{id}` → first call `_source: "database"` (miss), second call `_source: "cache"` (hit).
   - `PATCH /products/{id}` → then `GET` again → back to `_source: "database"` (invalidation worked), then `cache` on the next call.
   - `DELETE /products/{id}` → `GET` → 404, and the cache key is gone.
4. **Switch to real servers (optional):** the top of `main.py` has `USE_FAKES = True`. If you have MongoDB and Redis running (e.g. via Docker), set it to `False` — **the endpoint code doesn't change at all**, because the fakes share the real API.
5. **Bonus:**
   - Add a `GET /products` list endpoint with a `$gt` price filter via Motor.
   - Cache the list result under a key like `products:all` and invalidate it on any create/update/delete.
   - Rewrite the document layer using **Beanie** `Document` models instead of raw Motor and compare.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Updating the DB but not the cache | **Invalidate** (`r.delete(key)`) on every write. |
| Caching with no TTL | Always set `ex=...` as a freshness backstop. |
| Returning `ObjectId` in JSON | Convert `_id` to `str` (Pydantic/FastAPI can't serialize `ObjectId`). |
| Blocking Redis/Mongo calls in `async def` | Use async clients (`redis.asyncio`, Motor) and `await`. |
| Treating Redis as durable storage | It's in-memory/ephemeral; keep the source of truth elsewhere. |
| Using MongoDB for highly relational data | Use SQL; Mongo shines on document-shaped data. |
| Caching everything | Cache expensive, frequently-read, rarely-changed data. |

---

## 12. Key Takeaways

- **NoSQL complements SQL**, it doesn't replace it. Real systems are often **polyglot**.
- **MongoDB** = document database: collections of schemaless JSON-like documents; `_id` is an `ObjectId`; nesting over joins.
- **Motor** = async driver (raw dicts, `await`); **Beanie** = ODM on Motor+Pydantic (models + validation, SQLModel-like).
- **Redis** = fast in-memory key-value store for **caching**, sessions, rate limiting — with **TTL** auto-expiry.
- **Cache-aside**: check cache → on miss hit DB → fill cache with a TTL. **Invalidate on writes**; TTL is the backstop.
- Integrate like the SQL lessons: create clients once in **lifespan**, `async def` + `await`.
- **Choose deliberately:** SQL by default, Redis for speed/caching, MongoDB for document-shaped data.

---

## 🎉 Phase 3 Complete

You can now persist data for real: relational modeling with SQLAlchemy/SQLModel, migrations with Alembic, sync **and** async database access, and NoSQL with MongoDB + Redis. Your APIs no longer lose data on restart, and you can pick the right store per problem.

## ➡️ Next Lesson

**Lesson 28 — Async vs Sync Deep Dive** (start of Phase 4)
- `async def` vs `def`, the event loop, and `run_in_threadpool`
- When NOT to use async
- The theory behind the async choices you've been making since Lesson 25
