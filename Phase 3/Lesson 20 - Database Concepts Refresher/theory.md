# Lesson 20 — Database Concepts Refresher

> **Goal of this lesson:** Before touching SQLAlchemy, build a rock-solid mental model of **databases**. Understand **SQL vs NoSQL**, how a **relational database** is structured, what a **connection** and a **connection pool** are, what an **ORM** actually does, and why we're leaving JSON files behind.
>
> This is a **concepts** lesson. No FastAPI yet. `main.py` uses Python's built-in `sqlite3` so you can run real SQL today without installing anything.

---

## 1. Why This Lesson Exists

In Phase 1 and Phase 2, we stored data in **JSON files**:

```python
def load_json(filename):
    with open(filename) as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
```

That was perfect for learning. But JSON-file storage falls apart in the real world:

| Problem with JSON files | What goes wrong |
|---|---|
| **No concurrency safety** | Two requests writing at once overwrite each other's data. |
| **Rewrites the whole file** | To change one record you load, edit, and rewrite the entire file. |
| **No querying** | "Give me all orders over $500, sorted by date" means loading everything into Python and filtering by hand. |
| **No relationships** | Linking a purchase order to a supplier is manual bookkeeping. |
| **No integrity rules** | Nothing stops you saving an order that points to a supplier that doesn't exist. |
| **Slow at scale** | 100,000 records means reading a 50 MB file on every request. |
| **No transactions** | If the server crashes mid-save, the file can be left half-written and corrupt. |

A **database** solves every one of these. Phase 3 is where your APIs grow up.

---

## 2. What Is a Database?

A **database** is an organized system for **storing, querying, updating, and protecting** data.

A **Database Management System (DBMS)** is the software that runs the database — it handles storage on disk, concurrent access, querying, and integrity. Examples: PostgreSQL, MySQL, SQLite, MongoDB, Redis.

> 🔑 You don't read/write files yourself anymore. You **send commands** to the DBMS, and it manages the data safely and efficiently.

Two big families exist: **SQL (relational)** and **NoSQL (non-relational)**.

---

## 3. SQL vs NoSQL

### 3.1 SQL (Relational) Databases

Data lives in **tables** — like spreadsheets with strict columns. Tables can **relate** to each other. You query using **SQL** (Structured Query Language).

Examples: **PostgreSQL**, **MySQL**, **SQLite**, SQL Server, MariaDB.

```
products table
+----+-----------+---------+-------+
| id | name      | sku     | price |
+----+-----------+---------+-------+
| 1  | Keyboard  | KB-001  | 25.00 |
| 2  | Mouse     | MS-002  | 15.00 |
+----+-----------+---------+-------+
```

- **Structured**: every row has the same columns.
- **Schema-enforced**: a `price` column of type `NUMERIC` will reject `"hello"`.
- **Relationships**: an `orders` table can reference `products` by id.
- **ACID transactions**: strong guarantees (explained in section 6).

### 3.2 NoSQL (Non-Relational) Databases

An umbrella term for databases that **don't** use rigid tables. Several sub-types:

| Type | Stores data as | Example | Good for |
|---|---|---|---|
| **Document** | JSON-like documents | MongoDB | Flexible/nested data |
| **Key-Value** | key → value pairs | Redis | Caching, sessions |
| **Column-family** | wide sparse columns | Cassandra | Huge write volume |
| **Graph** | nodes + edges | Neo4j | Social networks, relationships |

```json
// A MongoDB "document" — shape can vary per record
{
  "_id": "abc123",
  "name": "Keyboard",
  "sku": "KB-001",
  "price": 25.00,
  "specs": { "layout": "US", "wireless": true }
}
```

- **Flexible schema**: documents in the same collection can have different fields.
- **Scales horizontally** easily (spread across many servers).
- **Weaker** cross-record guarantees (traditionally).

### 3.3 Head-to-Head

| Aspect | SQL (Relational) | NoSQL |
|---|---|---|
| **Structure** | Fixed tables + schema | Flexible documents/keys |
| **Query language** | SQL (standardized) | Varies per database |
| **Relationships** | First-class (JOINs) | Manual or embedded |
| **Consistency** | Strong (ACID) | Often eventual (tunable) |
| **Scaling** | Vertical (bigger server) | Horizontal (more servers) |
| **Best when** | Data is structured & related | Data is flexible or massive-scale |

### 3.4 Which Should You Learn First?

**SQL.** It's the default for 90% of backends, the concepts transfer everywhere, and it's what employers expect. This course focuses on **PostgreSQL-style SQL via SQLAlchemy**, practicing locally with **SQLite** (same SQL, zero setup).

> 🔑 Rule of thumb: **Start with a relational (SQL) database.** Reach for NoSQL only when you have a specific reason (caching → Redis, flexible documents → MongoDB). Phase 3 lesson 27 covers NoSQL as optional.

---

## 4. Anatomy of a Relational Database

Learn this vocabulary — every Phase 3 lesson builds on it.

| Term | Meaning | Analogy |
|---|---|---|
| **Table** | A collection of rows of one type | A spreadsheet / an Excel sheet |
| **Row (record)** | One entry | One line in the spreadsheet |
| **Column (field)** | One attribute + its type | A spreadsheet column header |
| **Schema** | The definition of tables/columns/types | The blueprint |
| **Primary Key (PK)** | Column that uniquely identifies a row | The row's ID badge |
| **Foreign Key (FK)** | Column pointing to another table's PK | A cross-reference link |
| **Index** | Extra structure that speeds up lookups | A book's index |
| **Query** | A command to read/change data | A question you ask |

### 4.1 Primary Key

Every row needs a unique identity. Usually an auto-incrementing integer `id`.

```
products
+----+----------+
| id | name     |   ← "id" is the PRIMARY KEY: unique, never null
+----+----------+
| 1  | Keyboard |
| 2  | Mouse    |
+----+----------+
```

This replaces the `next_id = max(ids) + 1` logic you hand-wrote with JSON files. The database generates IDs for you.

### 4.2 Foreign Key & Relationships

A **foreign key** links tables. This is the superpower JSON files never had.

```
suppliers                      products
+----+-----------+             +----+----------+-------------+
| id | name      |             | id | name     | supplier_id |
+----+-----------+             +----+----------+-------------+
| 1  | Acme Inc  | <-----------| 1  | Keyboard | 1           |
| 2  | Globex    |     ▲       | 2  | Mouse    | 1           |
+----+-----------+     |       | 3  | Monitor  | 2           |
                       |       +----+----------+-------------+
              products.supplier_id  → suppliers.id
```

The three relationship types:

| Relationship | Example | Implementation |
|---|---|---|
| **One-to-Many** | One supplier has many products | FK on the "many" side (`products.supplier_id`) |
| **Many-to-Many** | Products ↔ Tags | A join table (`product_tags`) |
| **One-to-One** | User ↔ Profile | FK with a UNIQUE constraint |

> 🔑 A foreign key **enforces integrity**: the DB refuses to insert a product whose `supplier_id` doesn't exist. Remember the Phase 1 assignment rule "order item product IDs must reference existing products"? The database enforces that automatically.

---

## 5. SQL — The Language

SQL is how you talk to a relational database. It splits into two everyday categories:

**DDL — Data Definition Language** (defines structure):

```sql
CREATE TABLE products (
    id    INTEGER PRIMARY KEY,
    name  TEXT    NOT NULL,
    sku   TEXT    NOT NULL UNIQUE,
    price REAL    NOT NULL
);
```

**DML — Data Manipulation Language** (works with rows) — this is your **CRUD**:

```sql
-- CREATE
INSERT INTO products (name, sku, price) VALUES ('Keyboard', 'KB-001', 25.00);

-- READ
SELECT * FROM products;
SELECT name, price FROM products WHERE price > 20 ORDER BY price DESC;

-- UPDATE
UPDATE products SET price = 29.99 WHERE id = 1;

-- DELETE
DELETE FROM products WHERE id = 2;
```

Map it back to what you already know:

| HTTP / CRUD | SQL | Phase 1 JSON equivalent |
|---|---|---|
| POST (create) | `INSERT` | append to list + save file |
| GET (read) | `SELECT ... WHERE` | load file + filter in Python |
| PUT (update) | `UPDATE ... WHERE` | find, mutate, save file |
| DELETE | `DELETE ... WHERE` | remove from list + save file |

The huge win: `WHERE`, `ORDER BY`, `LIMIT`, and `JOIN` run **inside the database engine** on indexed data — far faster than loading everything into Python.

### 5.1 JOIN — Combining Tables

The feature JSON files can only dream of. A JOIN follows a foreign key to pull related rows together in **one query**:

```sql
SELECT products.name, suppliers.name AS supplier
FROM products
JOIN suppliers ON products.supplier_id = suppliers.id;
```

```
name      | supplier
----------+----------
Keyboard  | Acme Inc
Mouse     | Acme Inc
Monitor   | Globex
```

---

## 6. Transactions & ACID

A **transaction** groups several statements into one all-or-nothing unit.

Classic example — a purchase order that must update two tables:

```sql
BEGIN;
  UPDATE products SET stock_quantity = stock_quantity + 50 WHERE id = 1;
  UPDATE purchase_orders SET status = 'received' WHERE id = 7;
COMMIT;   -- both succeed together
-- if anything fails: ROLLBACK  → neither change is saved
```

If the server crashed between the two updates with **JSON files**, you'd get inconsistent data (stock updated but order still "draft"). A transaction prevents that.

**ACID** is the set of guarantees a good SQL database gives every transaction:

| Letter | Property | Meaning |
|---|---|---|
| **A** | Atomicity | All statements succeed, or none do. |
| **C** | Consistency | The DB never violates its rules (e.g. FK constraints). |
| **I** | Isolation | Concurrent transactions don't corrupt each other. |
| **D** | Durability | Once committed, data survives a crash/power loss. |

> 🔑 ACID is the real reason we abandon JSON files. It's data safety you cannot reasonably build by hand.

---

## 7. Connections

To talk to a database, your app opens a **connection** — a live session between your program and the DBMS.

```python
import sqlite3
conn = sqlite3.connect("shop.db")   # 1. open a connection
cursor = conn.cursor()              # 2. get a cursor to run statements
cursor.execute("SELECT * FROM products")  # 3. run SQL
rows = cursor.fetchall()            # 4. read results
conn.commit()                       # 5. save changes (for writes)
conn.close()                        # 6. close the connection
```

A connection carries: **authentication** (user/password), a **network socket** to the DB server, and **transaction state**.

> ⚠️ Connections are **expensive** to open. For a server like PostgreSQL, each new connection means a TCP handshake, authentication, and the server allocating memory/a process. Doing this on **every** HTTP request would be painfully slow.

---

## 8. Connection Pooling

Opening a fresh connection per request is wasteful. The solution is a **connection pool**: a set of ready-made connections kept open and **reused**.

```
Without a pool (slow):
  request → OPEN connection → query → CLOSE connection   (repeat, every time)

With a pool (fast):
  ┌─────────── Connection Pool (e.g. 5 open connections) ───────────┐
  │   [conn1] [conn2] [conn3] [conn4] [conn5]                       │
  └────────────────────────────────────────────────────────────────┘
  request → BORROW a connection → query → RETURN it to the pool
```

**How it works:**
1. On startup, the pool opens a handful of connections (say 5).
2. A request **borrows** one, runs its queries, then **returns** it (not closed).
3. If all are busy, new requests **wait** for one to free up (or the pool grows to a max).
4. Idle connections may be recycled after a timeout.

**Why it matters:**

| Benefit | Explanation |
|---|---|
| **Speed** | Skips the connect/authenticate cost on every request. |
| **Resource control** | Caps total connections so you don't overwhelm the DB. |
| **Scalability** | Hundreds of requests share a small, fixed set of connections. |

> 🔑 You rarely manage pools by hand. **SQLAlchemy has a connection pool built in** — when you create an `engine` (Lesson 21), you're creating a pool. Knowing what it *is* means you'll understand settings like `pool_size` and `max_overflow` later.

---

## 9. What Is an ORM?

**ORM = Object-Relational Mapper.** It maps **database tables ↔ Python classes**, and **rows ↔ Python objects**, so you work with objects instead of writing raw SQL strings.

**Raw SQL** approach:

```python
cursor.execute("SELECT id, name, price FROM products WHERE id = ?", (1,))
row = cursor.fetchone()          # a plain tuple: (1, 'Keyboard', 25.0)
name = row[1]                    # you index by position — fragile
```

**ORM** approach (SQLAlchemy-style, coming in Lesson 21):

```python
class Product(Base):
    __tablename__ = "products"
    id    = Column(Integer, primary_key=True)
    name  = Column(String)
    price = Column(Float)

product = session.get(Product, 1)   # a real Python object
print(product.name)                 # attribute access — clear & safe
product.price = 29.99               # change an attribute...
session.commit()                    # ...ORM writes the UPDATE for you
```

**The mapping:**

| Database | Python (ORM) |
|---|---|
| Table | Class |
| Row | Object (instance) |
| Column | Attribute |
| Relationship (FK) | A linked object / list of objects |
| `SELECT`/`INSERT`/`UPDATE` | Method calls (`session.get`, `session.add`, `commit`) |

### 9.1 Why Use an ORM?

| Benefit | Explanation |
|---|---|
| **Pythonic** | Work with objects and attributes, not string SQL. |
| **Safer** | Auto-parameterizes queries → prevents SQL injection. |
| **Less boilerplate** | No hand-writing every INSERT/UPDATE statement. |
| **Portable** | Same code targets SQLite, PostgreSQL, MySQL. |
| **Integrates with types** | Pairs beautifully with Pydantic (Lesson 23). |

### 9.2 The Trade-offs (ORMs aren't free)

| Downside | Explanation |
|---|---|
| **Learning curve** | Sessions, relationships, and lazy-loading take time. |
| **Hidden queries** | A convenient attribute access can silently fire many SQL queries (the "N+1" problem — Lesson 48). |
| **Less control** | Very complex queries can be easier in raw SQL. |
| **Abstraction leaks** | You still need to understand the SQL underneath. |

> 🔑 An ORM is a **convenience layer over SQL — not a replacement for understanding it.** That's exactly why this refresher teaches SQL first. This course uses **SQLAlchemy 2.0**, the standard Python ORM (and later **SQLModel**, which fuses SQLAlchemy + Pydantic).

---

## 10. The Road Ahead (Where Phase 3 Is Going)

You now have the vocabulary. Here's how the next lessons use it:

| Lesson | Topic | Builds on this lesson |
|---|---|---|
| 21 | SQLAlchemy 2.0 (Sync) | Engine (= a **connection pool**), models (= **tables** as classes) |
| 22 | SQLAlchemy + FastAPI | DB **session** injected as a `Depends()` dependency |
| 23 | Pydantic + SQLAlchemy | Separate **schema** (Pydantic) from **model** (ORM table) |
| 24 | Alembic | Version-control your **schema** changes (migrations) |
| 25 | Async SQLAlchemy | `AsyncSession` for async endpoints |
| 26 | SQLModel | ORM + Pydantic combined |
| 27 | NoSQL (optional) | MongoDB / Redis |

---

## 11. Real-World Use Case — Rebuilding the Inventory API

Remember the Phase 1 **Inventory & Purchase Order API**? With JSON files you wrote:

```python
products = load_json("products.json")           # read the whole file
if any(p["sku"] == new_sku for p in products):  # manual uniqueness check
    raise HTTPException(409, "Duplicate SKU")
products.append(new_product)
save_json("products.json", products)            # rewrite the whole file
```

With a database, that becomes:

```sql
-- UNIQUE constraint enforces this automatically; a duplicate raises an error
CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT UNIQUE, ...);
INSERT INTO products (sku, ...) VALUES ('KB-001', ...);
```

- Uniqueness → a `UNIQUE` **constraint**, not a manual loop.
- "Product must reference an existing supplier" → a **foreign key**.
- "Receive order updates stock" → a **transaction** (atomic).
- "List products under $50, sorted by price" → one `SELECT ... WHERE ... ORDER BY`.
- Two requests at once → the DB handles **concurrency** safely.

**The entire assignment gets shorter, faster, and safer.** That's what Phase 3 unlocks.

---

## 12. Mini Task

This lesson's `main.py` is a **runnable SQLite demo** — real SQL, no installs needed.

1. Run it (it's a plain script, not a server):
   ```bash
   python main.py
   ```
2. Read the console output top to bottom. It walks through:
   - Opening a **connection**
   - `CREATE TABLE` (DDL)
   - `INSERT` / `SELECT` / `UPDATE` / `DELETE` (DML = CRUD)
   - A `JOIN` across two related tables (FK)
   - A **transaction** with `COMMIT` and a deliberate `ROLLBACK`
   - A tiny hand-written "mini-ORM" showing what an ORM does conceptually
3. It creates a real file called `shop.db` in this folder — that's your database. Delete it and re-run to start fresh.
4. **Bonus:** Open `shop.db` and explore it:
   - In Python: `sqlite3.connect("shop.db")` then run your own `SELECT`.
   - Add a `SELECT` that returns only products priced over `20`, sorted descending.
   - Add a second supplier and a product linked to it, then re-run the JOIN.

---

## 13. Key Takeaways

- **Databases replace JSON files** because they give querying, relationships, concurrency safety, and **ACID** guarantees.
- **SQL (relational)** = fixed tables + schema + relationships; **NoSQL** = flexible documents/keys. **Learn SQL first.**
- Core relational vocabulary: **table, row, column, primary key, foreign key, index, schema**.
- **SQL** does CRUD via `INSERT / SELECT / UPDATE / DELETE`, and `JOIN` combines related tables.
- A **transaction** is all-or-nothing; **ACID** = Atomicity, Consistency, Isolation, Durability.
- A **connection** is a live session to the DB and is **expensive to open**.
- A **connection pool** reuses a fixed set of open connections for speed and resource control.
- An **ORM** maps tables↔classes and rows↔objects so you write Python, not SQL strings — convenient, but you must still understand the SQL underneath.
- Phase 3's tool is **SQLAlchemy 2.0**.

---

## ➡️ Next Lesson

**Lesson 21 — SQLAlchemy 2.0 (Sync)**
- `Engine`, `Session`, `Base`
- Defining models (tables as Python classes)
- Relationships (One-to-Many, Many-to-Many)
- Your first real database-backed Python code
