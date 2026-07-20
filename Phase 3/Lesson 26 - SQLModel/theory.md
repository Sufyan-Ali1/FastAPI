# Lesson 26 — SQLModel

> **Goal of this lesson:** Meet **SQLModel** — the library by FastAPI's creator (Sebastián Ramírez) that **fuses SQLAlchemy and Pydantic into one class**. Learn how one `SQLModel` class can be *both* a database table *and* a validation schema, the `table=True` vs schema-model pattern, and — honestly — the trade-offs versus keeping them separate (Lesson 23).
>
> `main.py` is the same Products API one more time, built with SQLModel. Compare the amount of code to Lessons 23/25.

---

## 1. The Motivation

In Lesson 23 you maintained **two parallel class families** for every resource:

```python
class Product(Base):              # SQLAlchemy MODEL (the table)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    ...

class ProductRead(BaseModel):     # Pydantic SCHEMA (the API shape)
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: float
    ...
```

The fields are duplicated — once with SQLAlchemy's `Mapped/mapped_column`, once with Pydantic's plain annotations. Change a field and you edit it in two places.

**SQLModel's pitch:** what if one class could be both? Define fields **once**, and use the class as a table *and* as a Pydantic model.

> 🔑 SQLModel is **built on top of** SQLAlchemy and Pydantic — it doesn't replace them. A SQLModel table class *is* a real SQLAlchemy model, and *is* a real Pydantic model. Same author as FastAPI, designed to feel like FastAPI.

---

## 2. Anatomy of a SQLModel Class

```python
from sqlmodel import SQLModel, Field

class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    sku: str = Field(unique=True, index=True)
    price: float
    supplier_id: int = Field(foreign_key="suppliers.id")
```

What changed from what you know:

- Inherit from **`SQLModel`** (not `Base`, not `BaseModel`).
- **`table=True`** makes this class a real database table. Without it, the class is *just* a Pydantic model (a schema).
- Fields are declared with normal type hints, using **`Field(...)`** — which is SQLModel's single `Field` that combines Pydantic's validation options *and* SQLAlchemy's column options (`primary_key`, `foreign_key`, `unique`, `index`).
- `id: int | None = Field(default=None, primary_key=True)` — the primary key is `None` before insertion and filled by the DB after.

| Concept | SQLAlchemy (L21–25) | SQLModel |
|---|---|---|
| Base class | `Base(DeclarativeBase)` + `BaseModel` | `SQLModel` (one class does both) |
| Column | `mapped_column(...)` | `Field(...)` |
| Table flag | `__tablename__ = "..."` | `table=True` (name defaults to lowercased class) |
| Primary key | `mapped_column(primary_key=True)` | `Field(primary_key=True)` |
| Foreign key | `mapped_column(ForeignKey("t.id"))` | `Field(foreign_key="t.id")` |
| Validation | separate Pydantic schema | same class (or a non-table SQLModel) |

> 💡 `__tablename__` is optional in SQLModel; it defaults to the class name lowercased (`Product` → `product`). We set it explicitly when we want a specific name (e.g. `products`).

---

## 3. `table=True` vs `table=False` — Tables and Schemas

This is the key idea. The **same base class** (`SQLModel`) produces two kinds of classes depending on `table`:

| | `table=True` | (no `table=` / `table=False`) |
|---|---|---|
| Is it a DB table? | ✅ Yes — creates/maps a table | ❌ No |
| Is it a Pydantic model? | ✅ Yes | ✅ Yes |
| Use it for | Persisting rows | Request/response schemas |

So the **schema-vs-model separation from Lesson 23 still exists** — you just express it with SQLModel instead of mixing two libraries:

```python
# A shared base of common fields (NOT a table)
class ProductBase(SQLModel):
    name: str
    sku: str
    price: float
    supplier_id: int

# The TABLE (adds the id and table=True)
class Product(ProductBase, table=True):
    __tablename__ = "products"
    id: int | None = Field(default=None, primary_key=True)

# INPUT schema (not a table) - same as base
class ProductCreate(ProductBase):
    pass

# OUTPUT schema (not a table) - adds id
class ProductRead(ProductBase):
    id: int

# PARTIAL update (not a table) - all optional
class ProductUpdate(SQLModel):
    name: str | None = None
    price: float | None = None
    supplier_id: int | None = None
```

> 🔑 The mental model: **one `table=True` class (the model) + a few `table=False` classes (the schemas), all sharing a base.** You still separate input/output — SQLModel just removes the two-library duplication and gives you inheritance from a common base.

---

## 4. No `from_attributes` Needed

Remember Lesson 23's `model_config = ConfigDict(from_attributes=True)` so Pydantic could read ORM objects? With SQLModel, a `table=True` class **is already a Pydantic model**, so FastAPI serializes it directly. Returning a `Product` from an endpoint with `response_model=ProductRead` just works — SQLModel wires ORM mode for you.

```python
@app.get("/products/{id}", response_model=ProductRead)
def get_product(id: int, session: Session = Depends(get_session)):
    product = session.get(Product, id)      # a Product (table object)
    ...
    return product                          # -> serialized as ProductRead
```

---

## 5. Engine and Session — SQLModel's Thin Wrappers

SQLModel re-exports SQLAlchemy's engine/session with tiny conveniences:

```python
from sqlmodel import SQLModel, create_engine, Session, select

engine = create_engine("sqlite:///shop.db",
                       connect_args={"check_same_thread": False})

# Create tables from every table=True class:
SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:   # SQLModel's Session (a thin subclass)
        yield session
```

- `create_engine` — the same SQLAlchemy engine (connection pool, Lesson 20).
- `SQLModel.metadata.create_all` — like `Base.metadata.create_all`; creates all `table=True` tables. (For real apps, **Alembic still applies** — Lesson 24.)
- `Session` — SQLModel's subclass of SQLAlchemy's `Session`. Its `.exec()` (note: `exec`, not `execute`) returns unwrapped objects directly.
- `select` — SQLModel's `select`, typed to return your model objects.

### Querying with `.exec()`

```python
# list
products = session.exec(select(Product).order_by(Product.id)).all()

# one by filter
product = session.exec(select(Product).where(Product.sku == "KB-001")).first()

# one by primary key
product = session.get(Product, 1)
```

> 💡 SQLAlchemy uses `session.execute(stmt).scalars().all()`. SQLModel's `session.exec(stmt).all()` gives you the objects directly — a small ergonomic win.

---

## 6. CRUD with SQLModel

The session mechanics are exactly Lesson 22 (`add` / `commit` / `refresh` / `delete`) — only the classes changed.

```python
@app.post("/products", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, session: Session = Depends(get_session)):
    # Build a table object from the input schema.
    product = Product.model_validate(payload)     # or Product(**payload.model_dump())
    session.add(product)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "SKU already exists")
    session.refresh(product)
    return product
```

- **`Product.model_validate(payload)`** converts the `ProductCreate` schema into a `Product` table object. (This is the SQLModel-idiomatic way; `Product(**payload.model_dump())` also works.)
- Everything else — `add`, `commit`, `rollback`, `refresh` — is identical to plain SQLAlchemy.

Partial update:

```python
updates = payload.model_dump(exclude_unset=True)   # only sent fields
for field, value in updates.items():
    setattr(product, field, value)
session.commit()
```

---

## 7. Relationships

SQLModel has its own `Relationship` (mirroring SQLAlchemy's `relationship`):

```python
from sqlmodel import Relationship

class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    products: list["Product"] = Relationship(back_populates="supplier")

class Product(SQLModel, table=True):
    __tablename__ = "products"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    supplier_id: int = Field(foreign_key="suppliers.id")
    supplier: Supplier | None = Relationship(back_populates="products")
```

Same `back_populates` idea as Lesson 21. To expose a nested relationship in a response, use a `table=False` read schema that includes it — but note relationships are **not** auto-included; you build a read model with the nested field and populate it (or use SQLAlchemy loader options). We keep the demo's nested endpoint simple.

---

## 8. The Honest Trade-offs — SQLModel vs Separate (Lesson 23)

SQLModel is elegant, but it's a real engineering choice, not a no-brainer. Weigh it:

**Advantages**
- **Less duplication** — define fields once; share a base across table + schemas.
- **One mental model** — one `Field`, one library, one style; feels like FastAPI.
- **Great for small/medium apps and prototypes** — fast to write, less boilerplate.
- Same author as FastAPI → tight, idiomatic integration.

**Drawbacks / cautions**
- **Younger, thinner library.** It wraps SQLAlchemy + Pydantic; sometimes you still drop down to raw SQLAlchemy for advanced queries/loader options, and error messages can get confusing across the two layers.
- **The abstraction can leak.** Complex relationships, inheritance, and async patterns are less documented than plain SQLAlchemy.
- **Coupling risk.** A `table=True` class that's *also* your API schema can blur the boundary — it's easy to accidentally expose or accept fields you shouldn't. (Discipline via separate `Create`/`Read` classes still matters.)
- **The industry default is still explicit SQLAlchemy 2.0 + Pydantic** (Lesson 23) for large/complex production systems, largely for maturity and control.

| Choose SQLModel when | Choose separate SQLAlchemy + Pydantic when |
|---|---|
| Small/medium app, prototype, MVP | Large/complex domain, many advanced queries |
| You value minimal boilerplate | You want maximum control & mature tooling |
| Team likes the FastAPI-style feel | Team already fluent in SQLAlchemy 2.0 |
| Schemas closely mirror tables | Schemas diverge a lot from tables |

> 🔑 There's **no wrong choice** — both are legitimate and widely used. SQLModel trades a little control for a lot less boilerplate. Know both; pick per project. This course teaches the separate approach as the foundation (so you understand the layers), and SQLModel as the ergonomic option.

---

## 9. Real-World Use Case — A Fast MVP

You're prototyping a startup's inventory service this week. Requirements are still shifting, tables mostly mirror the API, and you want to move fast. **SQLModel is ideal here:** one class per resource plus a couple of schema classes, no two-library duplication, and it plugs straight into FastAPI. If the product succeeds and the domain grows complex (heavy reporting queries, intricate relationships), you can migrate the hot paths to explicit SQLAlchemy — because SQLModel *is* SQLAlchemy underneath, that migration is incremental, not a rewrite.

---

## 10. Mini Task

`main.py` is the Products API built with SQLModel.

1. Install: `pip install sqlmodel`
2. Run: `uvicorn main:app --reload` → open `/docs`. To clients it's identical to Lessons 23/25.
3. Exercise the same flows: create supplier/product, duplicate SKU → 409, missing supplier → 404, list filter, `PATCH` one field, `DELETE` → 204.
4. **Compare the code.** Open Lesson 23's `main.py` and this one side by side. Count how many times `name`, `sku`, `price` are declared in each. Notice SQLModel's single `ProductBase` versus the repeated field lists.
5. **Bonus:**
   - Add a `category: str | None = None` field to `ProductBase` and see it appear on **both** the table and the schemas from one edit (the whole point).
   - Add a `Relationship` between `Supplier` and `Product` and a `GET /suppliers/{id}/full` that returns the supplier with a `products` list.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Forgetting `table=True` on the model | Without it the class is a schema only — no table is created. |
| Adding `table=True` to a request/response schema | Schemas must be `table=False` (default); only the persisted model is a table. |
| Using `.execute().scalars()` habit from SQLAlchemy | SQLModel uses `session.exec(stmt).all()` (unwrapped). |
| Expecting relationships to auto-serialize | Build a read schema with the nested field; relationships aren't auto-included. |
| Thinking SQLModel replaces Alembic | It doesn't — real schema changes still need migrations (Lesson 24). |
| Assuming SQLModel is "better" than SQLAlchemy | It's a trade-off: less boilerplate, less control. Choose per project. |

---

## 12. Key Takeaways

- **SQLModel = SQLAlchemy + Pydantic in one class**, by FastAPI's author. A `table=True` class is both a table and a Pydantic model.
- Declare fields **once** with a single **`Field(...)`** that carries both validation and column options.
- **`table=True`** → database table; **no `table`** → plain schema. Keep the `Create`/`Read`/`Update` split via a shared base.
- **No `from_attributes` needed** — table classes serialize directly with `response_model`.
- Engine/session are SQLAlchemy under the hood; query with **`session.exec(select(...)).all()`**. Alembic still applies.
- **Trade-off:** SQLModel cuts boilerplate; explicit SQLAlchemy + Pydantic gives more control and maturity. Both are valid — choose per project.

---

## ➡️ Next Lesson

**Lesson 27 — NoSQL Integration (Optional)**
- MongoDB with Motor / Beanie
- Redis for caching
- When a document store or key-value store fits better than SQL
