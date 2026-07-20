# Lesson 24 — Alembic (Database Migrations)

> **Goal of this lesson:** Solve the problem we've flagged since Lesson 21: `Base.metadata.create_all()` **cannot change an existing table**. Learn **Alembic** — the standard migration tool — to version your database schema like you version your code: `init`, **autogenerate**, `upgrade`, `downgrade`.
>
> This is a **command-line workflow** lesson. Instead of a `main.py` server, the runnable artifact is a real, working Alembic setup in this folder: `models.py` + `alembic.ini` + `alembic/`. Follow the commands and watch it work.

---

## 1. The Problem `create_all` Can't Solve

`Base.metadata.create_all(engine)` only creates tables that **don't exist yet**. It does **nothing** to a table that's already there.

So the moment your app is live with real data and you change a model:

```python
class Product(Base):
    ...
    description: Mapped[str | None] = mapped_column(String(300))  # NEW column
```

`create_all` sees `products` already exists and **skips it entirely**. Your new `description` column is never added. Your options without a migration tool are all bad:

- ✗ Drop and recreate the table → **you lose all data**.
- ✗ Hand-write `ALTER TABLE` SQL every time → error-prone, no history, no undo.
- ✗ Different developers' databases drift out of sync.

**Migrations** fix this. A migration is a versioned, ordered script that describes *how to change the schema* — and how to reverse it.

> 🔑 `create_all` is fine for the very first setup or throwaway learning DBs. For any database you can't afford to wipe, you need **migrations**.

---

## 2. What Is Alembic?

**Alembic** is the migration tool written by SQLAlchemy's author. It's the standard for Python. It gives you:

- A **`versions/`** folder of migration scripts, each with a unique **revision id**.
- A chain: every migration knows its **`down_revision`** (the one before it), forming an ordered history.
- A special table in your database, **`alembic_version`**, storing which revision the DB is currently at.
- **Autogenerate**: it compares your **models** to the **actual database** and writes the migration for you.

```
   models.py (what the schema SHOULD be)
          │  alembic compares
          ▼
   actual database (what it IS)
          │  difference
          ▼
   a migration script in alembic/versions/
```

Think of it as **git for your database schema**: each migration is a commit, `upgrade` moves forward, `downgrade` moves back, and `alembic_version` is like `HEAD`.

---

## 3. The Files (this folder)

```text
Lesson 24 - Alembic Database Migrations/
├── models.py            # Base + models = the SOURCE OF TRUTH for the schema
├── alembic.ini          # Alembic config (logging, script location, url)
└── alembic/
    ├── env.py           # run at every command; wires Alembic to our models
    ├── script.py.mako   # template for new migration files
    └── versions/        # the migration scripts (the important part)
        ├── ...create_suppliers_and_products.py
        └── ...add_product_description.py
```

- **`models.py`** — your `Base` and models. Alembic reads `Base.metadata` from here.
- **`alembic.ini`** — created by `alembic init`. Points to the `alembic/` folder.
- **`alembic/env.py`** — the glue script. We edited two things in it (next section).
- **`alembic/versions/`** — the generated migrations. **These are committed to git** — they're real project history.

> 🔑 Migration files in `versions/` are **code you commit**. Your teammates and your production server run the same migrations to reach the same schema. The `.db` file is *not* committed; the migrations that build it are.

---

## 4. One-Time Setup

### 4.1 Install and initialize

```bash
pip install alembic
alembic init alembic          # creates alembic.ini + the alembic/ folder
```

### 4.2 Wire `env.py` to your models (two edits)

By default `env.py` has `target_metadata = None` and doesn't know your models. Point it at them:

```python
# in alembic/env.py

# 1. Import your Base's metadata so autogenerate can see your models.
from models import Base, DATABASE_URL
target_metadata = Base.metadata

# 2. Use one source of truth for the URL (from models.py, not hardcoded in .ini).
config.set_main_option("sqlalchemy.url", DATABASE_URL)
```

- **`target_metadata`** is what autogenerate compares against the live DB. Without it, autogenerate produces empty migrations.
- Setting the URL here means `models.py` is the single place the connection string lives.

### 4.3 SQLite-only: batch mode

SQLite has very limited `ALTER TABLE` (it can't drop a column, rename many things, etc.). Alembic works around this with **batch mode**, which recreates the table behind the scenes. Enable it in both `context.configure(...)` calls in `env.py`:

```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,     # SQLite: emulate ALTER via table copy
)
```

You'll see it in the generated migration as `op.batch_alter_table(...)`. PostgreSQL/MySQL don't need this.

---

## 5. The Everyday Workflow

Four commands cover 95% of daily use.

### 5.1 `alembic revision --autogenerate` — write a migration

After you change a model, ask Alembic to diff it against the database and generate a migration:

```bash
alembic revision --autogenerate -m "create suppliers and products"
```

Real output from this folder's first run:

```
INFO  [alembic.autogenerate.compare.tables] Detected added table 'suppliers'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'products'
Generating .../versions/39391bd0e8a2_create_suppliers_and_products.py ... done
```

That generated file:

```python
revision = "39391bd0e8a2"
down_revision = None          # this is the FIRST migration

def upgrade():
    op.create_table("suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table("products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sku", sa.String(length=30), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
    )

def downgrade():
    op.drop_table("products")
    op.drop_table("suppliers")
```

Notice it captured **everything** from the models: the FK, the `UNIQUE(sku)`, the `Numeric(10,2)`, nullability — automatically.

> ⚠️ **Always read the generated migration before running it.** Autogenerate is excellent but not perfect — it can miss renames (it sees a drop + an add), some server defaults, and certain constraint changes. The header even says `# please adjust!`. Review, then commit.

### 5.2 `alembic upgrade head` — apply migrations

`head` means "the latest revision." This runs every `upgrade()` not yet applied:

```bash
alembic upgrade head
```

```
INFO  [alembic.runtime.migration] Running upgrade  -> 39391bd0e8a2, create suppliers and products
```

The tables now exist, and `alembic_version` records `39391bd0e8a2`.

### 5.3 Change a model → autogenerate again

Now add a column to `Product` in `models.py`:

```python
description: Mapped[str | None] = mapped_column(String(300))
```

Autogenerate a second migration:

```bash
alembic revision --autogenerate -m "add product description"
```

```
INFO  [alembic.autogenerate.compare.tables] Detected added column 'products.description'
```

Generated `upgrade()` (note the SQLite **batch** wrapper):

```python
def upgrade():
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.String(length=300), nullable=True))
```

Apply it:

```bash
alembic upgrade head
# products columns are now: id, name, sku, price, supplier_id, description
```

The new column was added **without touching existing rows** — that's the whole point.

### 5.4 `alembic downgrade` — reverse a migration

Every migration's `downgrade()` undoes its `upgrade()`. Step back one revision:

```bash
alembic downgrade -1
# products columns are back to: id, name, sku, price, supplier_id
```

- `alembic downgrade -1` → back one step.
- `alembic downgrade <revision>` → back to a specific revision.
- `alembic downgrade base` → undo everything (empty schema).

> 🔑 `downgrade` is your safety net / rollback. Good migrations always have a correct `downgrade()`. Autogenerate writes it for you, but review it too.

---

## 6. Inspecting State

| Command | Shows |
|---|---|
| `alembic current` | The revision the database is **currently** at |
| `alembic history` | The full ordered chain of migrations |
| `alembic heads` | The latest revision(s) available |
| `alembic show <rev>` | Details of one migration |

```bash
$ alembic history
39391bd0e8a2 -> a55cebd7caa8 (head), add product description
<base> -> 39391bd0e8a2, create suppliers and products
```

Read it bottom-to-top: base → create tables → add description (head).

---

## 7. The Mental Model — `create_all` vs Alembic

| | `create_all` | Alembic |
|---|---|---|
| Creates missing tables | ✅ | ✅ (via a migration) |
| **Alters existing tables** | ❌ | ✅ |
| Keeps a history | ❌ | ✅ (`versions/`) |
| Reversible | ❌ | ✅ (`downgrade`) |
| Team/prod reproducible | ❌ | ✅ |
| Good for | first setup, throwaway/test DBs | any real database |

**In FastAPI:** once you adopt Alembic, you **remove** `Base.metadata.create_all()` from your app's lifespan (Lesson 22) and instead run `alembic upgrade head` as a deploy step. The app no longer creates its own schema; migrations own it.

---

## 8. Real-World Use Case — Shipping a Schema Change Safely

Your Inventory API is in production with thousands of products. Marketing wants a `description` field. The safe path:

1. Add the column to the `Product` **model** in `models.py`.
2. `alembic revision --autogenerate -m "add product description"`.
3. **Read** the generated migration; adjust if needed (e.g. a sensible default).
4. Commit the migration file with your code change in the same PR.
5. On deploy, CI runs `alembic upgrade head` → the column is added, **existing rows untouched**.
6. If something's wrong, `alembic downgrade -1` rolls it back.

No dropped tables, no lost data, every environment identical. This is non-negotiable in real backends — and it's exactly what Phase 5/6 (testing & deployment) will build on.

---

## 9. Mini Task

This folder is already a **working** Alembic project. Reproduce the workflow yourself:

1. Install Alembic if needed: `pip install alembic`
2. Start from a clean database:
   ```bash
   # (from inside this lesson folder)
   rm shop.db            # delete any existing db  (PowerShell: del shop.db)
   alembic upgrade head  # rebuild it from the committed migrations
   ```
   Confirm: `alembic current` shows the head revision, and `products` has a `description` column.
3. Walk the history: `alembic history` and `alembic downgrade -1`, then check the `products` columns changed. `alembic upgrade head` to restore.
4. **Make your own change:**
   - Add a new column to a model in `models.py`, e.g.
     `stock_quantity: Mapped[int] = mapped_column(default=0)`
   - `alembic revision --autogenerate -m "add stock_quantity"`
   - **Open the generated file in `alembic/versions/`** and read it.
   - `alembic upgrade head`, verify the column exists, then `alembic downgrade -1` to reverse.
5. **Bonus:** Break autogenerate on purpose — rename a column in `models.py` and autogenerate. Notice Alembic sees a **drop + add** (losing data), not a rename. Fix the migration by hand to use `batch_op.alter_column(..., new_column_name=...)`. This is why you always review.

---

## 10. Common Mistakes

| Mistake | Fix |
|---|---|
| `target_metadata = None` left in `env.py` | Set it to `Base.metadata`, or autogenerate finds nothing. |
| Running an autogenerated migration without reading it | Always review; it can misread renames and defaults. |
| Editing a migration that's already applied in prod | Create a **new** migration instead; never rewrite history others have run. |
| Keeping `create_all()` **and** Alembic | Pick migrations for real DBs; drop `create_all` from the app. |
| SQLite `ALTER` errors | Enable `render_as_batch=True` in `env.py`. |
| Forgetting to commit `versions/` files | They're project code — commit them so everyone gets the same schema. |
| Expecting autogenerate to detect data, not schema | Migrations change **structure**; data changes go in the migration body manually (`op.execute(...)`). |

---

## 11. Key Takeaways

- `create_all` **can't alter existing tables** — real databases need **migrations**.
- **Alembic** versions your schema: `versions/` scripts + an `alembic_version` table (like git + HEAD).
- One-time setup: `alembic init`, then in `env.py` set `target_metadata = Base.metadata` and the URL.
- **Autogenerate** diffs your models against the live DB and writes the migration — but **always review it**.
- Daily commands: `revision --autogenerate` → `upgrade head`; reverse with `downgrade -1`; inspect with `current` / `history`.
- Each migration has an `upgrade()` and a reversible `downgrade()`, chained by `down_revision`.
- SQLite needs `render_as_batch=True`; Postgres/MySQL don't.
- In production, **migrations replace `create_all`** and run as a deploy step.

---

## ➡️ Next Lesson

**Lesson 25 — Async SQLAlchemy**
- `create_async_engine`, `AsyncSession`, `async with`
- `async def` endpoints with `await db.execute(...)`
- When async DB access actually helps (and when sync is fine)
