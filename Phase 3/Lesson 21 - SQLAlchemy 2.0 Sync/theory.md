# Lesson 21 — SQLAlchemy 2.0 (Sync)

> **Goal of this lesson:** Write your **first real database-backed Python code**. Learn the three pillars — **Engine**, **Base**, **Session** — define **models** (tables as Python classes), and wire up **relationships** (One-to-Many and Many-to-Many).
>
> Still **no FastAPI** here (that's Lesson 22). We focus 100% on SQLAlchemy so the ORM clicks before we mix it with the web layer. `main.py` runs against SQLite — the same code works on PostgreSQL by changing one line.

---

## 1. What Is SQLAlchemy?

**SQLAlchemy** is the standard, most-used database toolkit for Python. It's the ORM we previewed in Lesson 20 — the thing that maps **tables ↔ Python classes** and **rows ↔ objects**.

It has two layers:

| Layer | What it is | This lesson |
|---|---|---|
| **Core** | SQL toolkit — build/run SQL expressions | We use a little |
| **ORM** | Maps classes ↔ tables, objects ↔ rows | Our main focus |

> ⚠️ **Version matters.** SQLAlchemy **1.x** and **2.0** have different syntax. We use **2.0** (the modern style with `Mapped` type hints). Old tutorials using `Column(...)` at class level without type hints are 1.x-style — recognize them but don't copy them.

**Install** (if not already):

```bash
pip install sqlalchemy
```

We practice with **SQLite** (built into Python, zero setup). The exact same ORM code runs on PostgreSQL/MySQL by changing only the connection URL.

---

## 2. The Three Pillars

Everything in SQLAlchemy revolves around three objects. Learn what each does:

| Pillar | Analogy | Responsibility |
|---|---|---|
| **Engine** | The power plant | Manages the DB connection + **connection pool**. Created **once** per app. |
| **Base** | The blueprint registry | Parent class all your models inherit from. Collects table definitions. |
| **Session** | The conversation | Your workspace for reading/writing rows. Created **per unit of work** (in FastAPI: per request). |

```
   Engine  ──owns──►  Connection Pool  ──talks to──►  Database
     ▲
     │ uses
   Session  ──reads/writes──►  your model objects (Product, Supplier, ...)
     ▲
     │ inherit from
   Base  ◄──  Product, Supplier, Tag   (your models = tables)
```

---

## 3. The Engine

The **Engine** is the starting point. It holds the **connection pool** (remember Lesson 20) and knows how to talk to your specific database.

```python
from sqlalchemy import create_engine

engine = create_engine("sqlite:///shop.db", echo=True)
```

- **Connection URL** format: `dialect+driver://user:password@host:port/database`
  | Database | URL example |
  |---|---|
  | SQLite (file) | `sqlite:///shop.db` |
  | SQLite (memory) | `sqlite:///:memory:` |
  | PostgreSQL | `postgresql+psycopg://user:pass@localhost:5432/mydb` |
  | MySQL | `mysql+pymysql://user:pass@localhost:3306/mydb` |
- **`echo=True`** logs every SQL statement SQLAlchemy runs — invaluable for learning. Turn it off in production.
- Create the engine **once** for the whole application. It's not per-request.

> 🔑 The Engine does **not** open a connection immediately. It opens them lazily (when first needed) and reuses them via the pool.

---

## 4. Base — The Declarative Foundation

Every model class inherits from a common **Base**. In SQLAlchemy 2.0, you define it like this:

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

`Base` carries the **metadata** — a registry of every table you define. That registry is what lets you create all tables at once:

```python
Base.metadata.create_all(engine)   # CREATE TABLE for every model, if not present
Base.metadata.drop_all(engine)     # DROP every table (careful!)
```

> 🔑 `create_all` only creates tables that **don't already exist**. It does **not** alter existing tables when you change a model — that's what **Alembic migrations** (Lesson 24) are for.

---

## 5. Defining Models (Tables as Classes)

This is the heart of the ORM. A **class** = a **table**, an **attribute** = a **column**.

```python
from sqlalchemy import String, Integer, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column

class Supplier(Base):
    __tablename__ = "suppliers"

    id:   Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
```

Breaking down the 2.0 syntax:

- `__tablename__` — the real table name in the database.
- `Mapped[int]` — the **Python type** of the attribute (the type hint is meaningful here, not just documentation).
- `mapped_column(...)` — the **column definition** (constraints, type details, keys).

### 5.1 `Mapped[...]` and nullability

The type hint controls whether the column is **NULL**-able:

```python
name:    Mapped[str]          # NOT NULL  (required)
notes:   Mapped[str | None]   # NULL allowed (optional)
```

> 🔑 `Mapped[str]` → `NOT NULL`. `Mapped[str | None]` → nullable. The Optional-ness of the type hint drives the column constraint automatically.

### 5.2 Common `mapped_column` options

| Option | SQL effect |
|---|---|
| `primary_key=True` | PRIMARY KEY (auto-increments for ints) |
| `nullable=False` | NOT NULL (usually inferred from the type hint) |
| `unique=True` | UNIQUE constraint |
| `index=True` | Create an index for faster lookups |
| `default=...` | Python-side default value |
| `server_default=...` | Database-side default |

### 5.3 Column types

| SQLAlchemy type | Python | SQL |
|---|---|---|
| `Integer` | `int` | INTEGER |
| `String(n)` | `str` | VARCHAR(n) |
| `Text` | `str` | TEXT (long) |
| `Numeric(10, 2)` | `Decimal` | NUMERIC — **use for money** |
| `Float` | `float` | FLOAT |
| `Boolean` | `bool` | BOOLEAN |
| `DateTime` | `datetime` | TIMESTAMP |

> 💡 For prices/money, prefer `Numeric` over `Float` to avoid rounding errors. (Our demo uses `Numeric(10, 2)`.)

---

## 6. The Session — Your Unit of Work

The **Session** is how you actually read and write rows. It's a workspace that tracks the objects you touch and flushes changes to the database.

```python
from sqlalchemy.orm import Session

with Session(engine) as session:
    supplier = Supplier(name="Acme Inc")   # a new Python object (not saved yet)
    session.add(supplier)                  # stage it for insertion
    session.commit()                       # write to DB (runs INSERT)
    print(supplier.id)                     # DB-generated id is now populated
```

### 6.1 The Session lifecycle

| Step | Method | What happens |
|---|---|---|
| **Add** | `session.add(obj)` | Object becomes *pending* (not in DB yet) |
| **Flush** | `session.flush()` (often automatic) | SQL is sent, but not yet permanent |
| **Commit** | `session.commit()` | Transaction is saved permanently |
| **Rollback** | `session.rollback()` | Undo everything since last commit |
| **Refresh** | `session.refresh(obj)` | Reload the object's attributes from DB |

> 🔑 The Session wraps a **transaction** (Lesson 20). Nothing is permanent until `commit()`. If an error happens, `rollback()` undoes it. The `with Session(...)` block auto-closes the session (returning its connection to the pool).

### 6.2 Reading data — the 2.0 `select()` style

SQLAlchemy 2.0 uses `select()` + `session.scalars()` / `session.execute()`:

```python
from sqlalchemy import select

# get one by primary key (simplest)
supplier = session.get(Supplier, 1)

# query with a filter
stmt = select(Supplier).where(Supplier.name == "Acme Inc")
supplier = session.scalars(stmt).first()

# get a list
stmt = select(Product).where(Product.price > 20).order_by(Product.price.desc())
products = session.scalars(stmt).all()
```

| Helper | Returns |
|---|---|
| `session.get(Model, pk)` | One object by primary key (or `None`) |
| `session.scalars(stmt).first()` | First matching object (or `None`) |
| `session.scalars(stmt).all()` | List of objects |
| `session.scalars(stmt).one()` | Exactly one (errors if 0 or >1) |

> 💡 `scalars()` unwraps single-column results into plain objects. Use `session.execute(stmt)` when you select multiple columns/expressions and want rows.

### 6.3 Update and delete

```python
# UPDATE: load, mutate the attribute, commit — the ORM writes the SQL
product = session.get(Product, 1)
product.price = 29.99
session.commit()

# DELETE
session.delete(product)
session.commit()
```

No SQL strings — you change Python attributes and the ORM figures out the `UPDATE`/`DELETE`.

---

## 7. Relationships — Where the ORM Shines

Relationships turn foreign keys into **navigable Python attributes**. This is the payoff for using an ORM.

### 7.1 One-to-Many (Supplier → Products)

One supplier has many products. The foreign key lives on the **"many"** side.

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class Supplier(Base):
    __tablename__ = "suppliers"
    id:   Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))

    # one supplier -> list of products
    products: Mapped[list["Product"]] = relationship(back_populates="supplier")

class Product(Base):
    __tablename__ = "products"
    id:          Mapped[int] = mapped_column(primary_key=True)
    name:        Mapped[str] = mapped_column(String(100))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    # each product -> its one supplier
    supplier: Mapped["Supplier"] = relationship(back_populates="products")
```

Now you navigate in Python — no manual JOINs:

```python
supplier = session.get(Supplier, 1)
print(supplier.products)         # -> [Product(...), Product(...)]  (a list)

product = session.get(Product, 1)
print(product.supplier.name)     # -> "Acme Inc"   (follow FK backwards)
```

Two key pieces:

- **`ForeignKey("suppliers.id")`** — the actual DB constraint (column → column).
- **`relationship(back_populates=...)`** — the Python-level navigation. `back_populates` links the two sides so updating one updates the other in memory.

### 7.2 Many-to-Many (Product ↔ Tag)

A product can have many tags; a tag applies to many products. This needs an **association (join) table**.

```python
from sqlalchemy import Table, Column

# The association table — just two foreign keys
product_tags = Table(
    "product_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id"), primary_key=True),
    Column("tag_id",     ForeignKey("tags.id"),     primary_key=True),
)

class Product(Base):
    __tablename__ = "products"
    id:   Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    tags: Mapped[list["Tag"]] = relationship(
        secondary=product_tags, back_populates="products"
    )

class Tag(Base):
    __tablename__ = "tags"
    id:   Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    products: Mapped[list["Product"]] = relationship(
        secondary=product_tags, back_populates="tags"
    )
```

- **`secondary=product_tags`** tells SQLAlchemy to route the relationship through the join table.
- Assign in Python and the ORM manages the join-table rows for you:

```python
keyboard.tags.append(Tag(name="electronics"))
session.commit()          # inserts into product_tags automatically
print(keyboard.tags)      # -> [Tag(name="electronics")]
```

### 7.3 Relationship cheat sheet

| Type | Foreign key location | `relationship` uses |
|---|---|---|
| One-to-Many | On the "many" table | `back_populates` on both sides |
| Many-to-One | (same relationship, other direction) | `back_populates` |
| Many-to-Many | In a separate association table | `secondary=` + `back_populates` |
| One-to-One | On either side, with `unique=True` | `back_populates` + `uselist=False` |

---

## 8. Putting It Together — The Standard Setup

Almost every SQLAlchemy project has this skeleton (you'll reuse it in Lesson 22 with FastAPI):

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

# 1. Engine (once)
engine = create_engine("sqlite:///shop.db", echo=True)

# 2. Base (once)
class Base(DeclarativeBase):
    pass

# 3. Models (Supplier, Product, Tag ... inherit from Base)
# ...

# 4. Create tables
Base.metadata.create_all(engine)

# 5. Use a Session per unit of work
with Session(engine) as session:
    session.add(Supplier(name="Acme Inc"))
    session.commit()
```

---

## 9. Real-World Use Case — Inventory API, the SQLAlchemy Way

Phase 1's Inventory API stored `products.json`, `suppliers.json`, and manually linked them. With SQLAlchemy:

- `Product`, `Supplier` become **model classes**.
- "Product belongs to a supplier" → a **relationship**, so `product.supplier` just works.
- "List a supplier's products" → `supplier.products` (no manual filtering).
- "SKU must be unique" → `mapped_column(unique=True)`.
- Product tags/categories → a **many-to-many** relationship.
- Data survives restarts because it's in a real database file, not rewritten JSON.

In Lesson 22 we drop this straight into FastAPI: the Session becomes a `Depends()` dependency, and each endpoint does its CRUD through the ORM.

---

## 10. Mini Task

`main.py` is a **runnable script** (not a server) that builds the whole thing.

1. Make sure SQLAlchemy is installed: `pip install sqlalchemy`
2. Run it:
   ```bash
   python main.py
   ```
3. Watch the output. Because `echo=True`, you'll see the **real SQL** SQLAlchemy generates for every `CREATE TABLE`, `INSERT`, `SELECT`, and `JOIN` — connect it back to Lesson 20.
4. It creates `shop.db` in this folder. Delete it and re-run to start fresh.
5. **Bonus tasks** (edit `main.py`):
   - Add a new `Supplier` with two products, then print `supplier.products`.
   - Query all products priced over `50`, sorted ascending.
   - Add a third `Tag` and attach it to two different products, then print each tag's `products`.
   - Change a product's `supplier_id` by reassigning `product.supplier = other_supplier`, commit, and confirm with `session.refresh`.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Forgetting `session.commit()` | Changes are lost when the session closes. Always commit writes. |
| Creating the Engine per request | Create it **once**; the pool is meant to be shared. |
| Using 1.x `Column(...)` without `Mapped[...]` | Use 2.0 `Mapped[...]` + `mapped_column(...)`. |
| Expecting `create_all` to alter tables | It only **creates missing** tables. Schema changes need **Alembic** (Lesson 24). |
| Accessing relationships after the session closed | Load data (or use `expire_on_commit=False`) before the session ends. |
| Using `Float` for money | Use `Numeric(10, 2)` to avoid rounding errors. |

---

## 12. Key Takeaways

- SQLAlchemy has **Core** (SQL toolkit) and **ORM** (classes↔tables). We use **2.0** style with `Mapped[...]`.
- **Engine** = connection pool + DB dialect. Create it **once**. URL picks the database.
- **Base** (`DeclarativeBase`) collects models; `Base.metadata.create_all(engine)` builds the tables.
- A **model** is a class with `__tablename__` and `Mapped[...] = mapped_column(...)` attributes.
- `Mapped[str]` = NOT NULL; `Mapped[str | None]` = nullable.
- The **Session** is a per-unit-of-work transaction: `add` → `commit`, or `rollback`. Read with `select()` + `scalars()`, or `session.get()`.
- **Relationships** turn foreign keys into Python attributes: **One-to-Many** (`ForeignKey` + `back_populates`), **Many-to-Many** (`secondary=` association table).
- Change attributes → the ORM writes the `UPDATE`/`INSERT`/`DELETE` for you.

---

## ➡️ Next Lesson

**Lesson 22 — SQLAlchemy with FastAPI**
- Providing the DB Session as a `Depends()` dependency
- Full CRUD endpoints backed by the database
- Turning the Phase 1 Inventory API into a real database-backed API
