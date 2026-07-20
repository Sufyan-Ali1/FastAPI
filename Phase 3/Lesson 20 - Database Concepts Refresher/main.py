"""
Lesson 20 - Database Concepts Refresher
---------------------------------------
A runnable SQLite demo. This is a CONCEPTS lesson, so there is NO FastAPI here.

We use Python's built-in `sqlite3` module (nothing to install) to touch every
idea from theory.md with REAL SQL:

    - opening a CONNECTION
    - CREATE TABLE                     (DDL)
    - INSERT / SELECT / UPDATE / DELETE (DML = CRUD)
    - a JOIN across two related tables  (foreign key)
    - a TRANSACTION with COMMIT and a deliberate ROLLBACK
    - a tiny hand-written "mini-ORM" to show what an ORM does conceptually

How to run (from inside this folder):

    python main.py

It creates a real database file called `shop.db` next to this script.
Delete that file and re-run to start fresh.
"""

import os
import sqlite3


DB_FILE = os.path.join(os.path.dirname(__file__), "shop.db")


def banner(title: str) -> None:
    """Just prints a nice section header so the output is easy to read."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def fresh_start() -> None:
    """Delete any existing DB file so every run starts clean."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)


# ---------------------------------------------------------------------------
# 1. CONNECTION  - open a live session to the database
# ---------------------------------------------------------------------------
def demo_connection() -> sqlite3.Connection:
    banner("1. CONNECTION")
    # sqlite3.connect() opens (or creates) the database file and returns a
    # live connection. For a server DB like PostgreSQL this step also does a
    # network handshake + authentication - which is exactly why we later reuse
    # connections via a POOL instead of opening one per request.
    conn = sqlite3.connect(DB_FILE)
    # Return rows as dict-like objects (access columns by name, not position).
    conn.row_factory = sqlite3.Row
    # Make SQLite actually enforce FOREIGN KEY constraints (off by default).
    conn.execute("PRAGMA foreign_keys = ON;")
    print(f"Opened a connection to: {DB_FILE}")
    return conn


# ---------------------------------------------------------------------------
# 2. DDL  - define the SCHEMA (tables, columns, keys, constraints)
# ---------------------------------------------------------------------------
def demo_create_schema(conn: sqlite3.Connection) -> None:
    banner("2. DDL - CREATE TABLE (defining the schema)")
    conn.executescript(
        """
        CREATE TABLE suppliers (
            id   INTEGER PRIMARY KEY,          -- PRIMARY KEY: unique row id
            name TEXT    NOT NULL
        );

        CREATE TABLE products (
            id          INTEGER PRIMARY KEY,
            name        TEXT    NOT NULL,
            sku         TEXT    NOT NULL UNIQUE,   -- UNIQUE: no duplicate SKUs
            price       REAL    NOT NULL,
            supplier_id INTEGER NOT NULL,
            -- FOREIGN KEY: supplier_id must point to a real suppliers.id
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );
        """
    )
    conn.commit()
    print("Created tables: suppliers, products")
    print("Note the UNIQUE(sku) and FOREIGN KEY constraints - the DB enforces")
    print("the same rules we hand-wrote with loops in the Phase 1 assignment.")


# ---------------------------------------------------------------------------
# 3. INSERT  - CREATE (the C in CRUD)
# ---------------------------------------------------------------------------
def demo_insert(conn: sqlite3.Connection) -> None:
    banner("3. DML - INSERT (Create)")
    # The "?" placeholders are PARAMETERS. Never build SQL with string
    # formatting/f-strings - parameters prevent SQL injection.
    conn.executemany(
        "INSERT INTO suppliers (name) VALUES (?)",
        [("Acme Inc",), ("Globex",)],
    )
    conn.executemany(
        "INSERT INTO products (name, sku, price, supplier_id) VALUES (?, ?, ?, ?)",
        [
            ("Keyboard", "KB-001", 25.00, 1),
            ("Mouse",    "MS-002", 15.00, 1),
            ("Monitor",  "MN-003", 199.00, 2),
        ],
    )
    conn.commit()
    print("Inserted 2 suppliers and 3 products.")

    # Show what a UNIQUE constraint does: a duplicate SKU is rejected by the DB.
    try:
        conn.execute(
            "INSERT INTO products (name, sku, price, supplier_id) VALUES (?, ?, ?, ?)",
            ("Fake Keyboard", "KB-001", 9.99, 1),  # KB-001 already exists
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        print(f"Duplicate SKU rejected automatically -> {exc}")


# ---------------------------------------------------------------------------
# 4. SELECT  - READ (the R in CRUD) + WHERE / ORDER BY
# ---------------------------------------------------------------------------
def demo_select(conn: sqlite3.Connection) -> None:
    banner("4. DML - SELECT (Read) with WHERE and ORDER BY")
    print("All products:")
    for row in conn.execute("SELECT id, name, sku, price FROM products"):
        print(f"  {row['id']}: {row['name']} ({row['sku']}) ${row['price']:.2f}")

    print("\nProducts priced over $20, most expensive first:")
    query = "SELECT name, price FROM products WHERE price > ? ORDER BY price DESC"
    for row in conn.execute(query, (20,)):
        print(f"  {row['name']} -> ${row['price']:.2f}")
    print("\nThe DB did the filtering + sorting - not Python loops over a JSON file.")


# ---------------------------------------------------------------------------
# 5. UPDATE and DELETE  - the U and D in CRUD
# ---------------------------------------------------------------------------
def demo_update_delete(conn: sqlite3.Connection) -> None:
    banner("5. DML - UPDATE and DELETE")
    conn.execute("UPDATE products SET price = ? WHERE sku = ?", (29.99, "KB-001"))
    conn.execute("DELETE FROM products WHERE sku = ?", ("MS-002",))
    conn.commit()

    print("After UPDATE (Keyboard price) and DELETE (Mouse removed):")
    for row in conn.execute("SELECT name, price FROM products ORDER BY id"):
        print(f"  {row['name']} -> ${row['price']:.2f}")


# ---------------------------------------------------------------------------
# 6. JOIN  - follow the foreign key to combine two tables in ONE query
# ---------------------------------------------------------------------------
def demo_join(conn: sqlite3.Connection) -> None:
    banner("6. JOIN - combining related tables via the foreign key")
    query = """
        SELECT products.name AS product, suppliers.name AS supplier
        FROM products
        JOIN suppliers ON products.supplier_id = suppliers.id
        ORDER BY products.id
    """
    for row in conn.execute(query):
        print(f"  {row['product']:<10} is supplied by {row['supplier']}")
    print("\nJSON files could never do this in a single step.")


# ---------------------------------------------------------------------------
# 7. TRANSACTION  - all-or-nothing (COMMIT vs ROLLBACK)
# ---------------------------------------------------------------------------
def demo_transaction(conn: sqlite3.Connection) -> None:
    banner("7. TRANSACTION - COMMIT vs ROLLBACK (atomicity)")

    # Success case: two related changes committed together.
    print("Committing a price change for the Monitor...")
    conn.execute("UPDATE products SET price = ? WHERE sku = ?", (179.00, "MN-003"))
    conn.commit()
    print("  Committed. Change is now durable (survives a restart).")

    # Failure case: start changes, then decide to ROLLBACK - nothing is saved.
    print("\nStarting another change, then rolling it back...")
    conn.execute("UPDATE products SET price = ? WHERE sku = ?", (0.01, "MN-003"))
    price_before_rollback = conn.execute(
        "SELECT price FROM products WHERE sku = 'MN-003'"
    ).fetchone()["price"]
    print(f"  Inside the transaction the price looks like: ${price_before_rollback:.2f}")

    conn.rollback()  # undo everything since the last commit
    price_after_rollback = conn.execute(
        "SELECT price FROM products WHERE sku = 'MN-003'"
    ).fetchone()["price"]
    print(f"  After ROLLBACK the price is back to: ${price_after_rollback:.2f}")
    print("  Atomicity: the bad change never happened. This is why we ditch JSON.")


# ---------------------------------------------------------------------------
# 8. MINI-ORM  - what an ORM does, in ~20 lines, so the concept is concrete
# ---------------------------------------------------------------------------
class Product:
    """A plain Python class that MAPS to a row in the `products` table.

    A real ORM (SQLAlchemy) does all of this for you and far more. This tiny
    version just shows the core idea: a TABLE becomes a CLASS, a ROW becomes an
    OBJECT, and COLUMNS become ATTRIBUTES - so you write Python, not SQL strings.
    """

    def __init__(self, id: int, name: str, sku: str, price: float, supplier_id: int):
        self.id = id
        self.name = name
        self.sku = sku
        self.price = price
        self.supplier_id = supplier_id

    @classmethod
    def get(cls, conn: sqlite3.Connection, product_id: int) -> "Product | None":
        """SELECT one row and turn it into a Product object."""
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            return None
        return cls(row["id"], row["name"], row["sku"], row["price"], row["supplier_id"])

    def save(self, conn: sqlite3.Connection) -> None:
        """Write this object's attributes back as an UPDATE."""
        conn.execute(
            "UPDATE products SET name = ?, price = ? WHERE id = ?",
            (self.name, self.price, self.id),
        )
        conn.commit()

    def __repr__(self) -> str:
        return f"Product(id={self.id}, name={self.name!r}, price={self.price})"


def demo_mini_orm(conn: sqlite3.Connection) -> None:
    banner("8. MINI-ORM - mapping a table to a Python class")

    # Instead of reading a tuple and indexing row[1], we get a real object.
    product = Product.get(conn, 1)
    print(f"Loaded as a Python object: {product}")
    print(f"  Access columns as attributes: product.name = {product.name!r}")

    # Change an attribute, then let the object write the SQL for us.
    product.price = 34.50
    product.save(conn)
    print(f"  Changed price via attribute + .save() -> now ${product.price:.2f}")

    reloaded = Product.get(conn, 1)
    print(f"  Re-read from DB to prove it persisted: {reloaded}")
    print("\nSQLAlchemy (Lesson 21) gives you this pattern, properly, for free.")


def main() -> None:
    fresh_start()
    conn = demo_connection()
    try:
        demo_create_schema(conn)
        demo_insert(conn)
        demo_select(conn)
        demo_update_delete(conn)
        demo_join(conn)
        demo_transaction(conn)
        demo_mini_orm(conn)
    finally:
        conn.close()  # 9. always close the connection when done
        banner("DONE")
        print(f"Explore the database yourself - the file is: {DB_FILE}")
        print("Try: sqlite3.connect(DB_FILE) then run your own SELECT queries.")


if __name__ == "__main__":
    main()
