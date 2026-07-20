"""
Lesson 21 - SQLAlchemy 2.0 (Sync)
---------------------------------
Your first REAL database-backed Python code. Still NO FastAPI (that is Lesson
22) - we focus entirely on SQLAlchemy so the ORM clicks.

This one script demonstrates all three pillars and both relationship types:

    - ENGINE       (connection pool + database dialect)
    - BASE         (DeclarativeBase - the model registry)
    - MODELS       (Supplier, Product, Tag = tables as classes)
    - SESSION      (unit of work: add / commit / query)
    - One-to-Many  (Supplier -> Products)
    - Many-to-Many (Product <-> Tag via an association table)

Install once:

    pip install sqlalchemy

How to run (from inside this folder):

    python main.py

It creates a real database file `shop.db` next to this script. Delete it and
re-run to start fresh. `echo=True` prints the actual SQL SQLAlchemy generates.
"""

import os
from decimal import Decimal

from sqlalchemy import (
    Column,
    ForeignKey,
    Numeric,
    String,
    Table,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)


DB_FILE = os.path.join(os.path.dirname(__file__), "shop.db")


# ---------------------------------------------------------------------------
# PILLAR 1: THE ENGINE  - created ONCE, owns the connection pool
# ---------------------------------------------------------------------------
# Connection URL format: dialect+driver://user:pass@host:port/database
# For PostgreSQL you would write e.g.:
#     postgresql+psycopg://user:pass@localhost:5432/shop
# The ORM code below stays identical - only this URL changes.
engine = create_engine(f"sqlite:///{DB_FILE}", echo=True)


# ---------------------------------------------------------------------------
# PILLAR 2: THE BASE  - every model inherits from this; it collects the tables
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# The Many-to-Many association table (just two foreign keys).
# Declared with Core's Table() because it holds no data of its own.
# ---------------------------------------------------------------------------
product_tags = Table(
    "product_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


# ---------------------------------------------------------------------------
# MODELS  - a class is a table, an attribute is a column
# ---------------------------------------------------------------------------
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    # One-to-Many: one supplier has many products.
    products: Mapped[list["Product"]] = relationship(back_populates="supplier")

    def __repr__(self) -> str:
        return f"Supplier(id={self.id}, name={self.name!r})"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[str] = mapped_column(String(30), unique=True)  # UNIQUE constraint
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # Numeric for money
    notes: Mapped[str | None] = mapped_column(String(200))  # nullable (optional)

    # The foreign key column (the real DB constraint).
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    # Many-to-One side of the relationship (navigate FK backwards).
    supplier: Mapped["Supplier"] = relationship(back_populates="products")

    # Many-to-Many: products <-> tags through the association table.
    tags: Mapped[list["Tag"]] = relationship(
        secondary=product_tags, back_populates="products"
    )

    def __repr__(self) -> str:
        return f"Product(id={self.id}, name={self.name!r}, price={self.price})"


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)

    products: Mapped[list["Product"]] = relationship(
        secondary=product_tags, back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"Tag(id={self.id}, name={self.name!r})"


def banner(title: str) -> None:
    print("\n" + "#" * 62)
    print("#  " + title)
    print("#" * 62)


def seed(session: Session) -> None:
    """Create suppliers, products, and tags, wiring up both relationships."""
    banner("SEED - creating objects and committing (watch the INSERTs)")

    acme = Supplier(name="Acme Inc")
    globex = Supplier(name="Globex")

    # Shared tags.
    electronics = Tag(name="electronics")
    office = Tag(name="office")
    gaming = Tag(name="gaming")

    # One-to-Many: attach products by appending to supplier.products, OR by
    # setting product.supplier - both keep the two sides in sync.
    keyboard = Product(
        name="Keyboard", sku="KB-001", price=Decimal("25.00"), supplier=acme
    )
    mouse = Product(
        name="Mouse", sku="MS-002", price=Decimal("15.00"), supplier=acme
    )
    monitor = Product(
        name="Monitor", sku="MN-003", price=Decimal("199.00"), supplier=globex
    )

    # Many-to-Many: just assign Python lists; the ORM fills product_tags.
    keyboard.tags = [electronics, office, gaming]
    mouse.tags = [electronics, office]
    monitor.tags = [electronics]

    # Adding the suppliers cascades to their products (and tags) automatically.
    session.add_all([acme, globex])
    session.commit()
    print("Committed 2 suppliers, 3 products, 3 tags.")


def product_by_sku(session: Session, sku: str) -> Product:
    """Look a product up by its unique SKU.

    NOTE: we deliberately do NOT use session.get(Product, 1) here. The database
    assigns primary keys in the order rows are INSERTed, and SQLAlchemy's
    unit-of-work may not insert them in the order you created the objects. So
    hardcoding ids like 1/2/3 is fragile. A stable natural key (the SKU) is
    always safe.
    """
    return session.scalars(select(Product).where(Product.sku == sku)).one()


def read_examples(session: Session) -> None:
    banner("READ - session.get, select().where, order_by")

    # Simplest read: by primary key. (The Keyboard's id, whatever it turned out
    # to be, is fetched via its SKU first - see product_by_sku's note.)
    keyboard = product_by_sku(session, "KB-001")
    same = session.get(Product, keyboard.id)
    print(f"session.get(Product, {keyboard.id}) -> {same}")

    # Filtered + sorted query, 2.0 style.
    stmt = (
        select(Product).where(Product.price > 20).order_by(Product.price.desc())
    )
    expensive = session.scalars(stmt).all()
    print(f"Products over $20 (desc): {expensive}")

    # Find one by a non-PK column.
    stmt = select(Supplier).where(Supplier.name == "Globex")
    globex = session.scalars(stmt).first()
    print(f"Supplier named 'Globex' -> {globex}")


def relationship_examples(session: Session) -> None:
    banner("RELATIONSHIPS - navigate FKs as Python attributes (no manual JOINs)")

    # One-to-Many: supplier -> its products.
    acme = session.scalars(
        select(Supplier).where(Supplier.name == "Acme Inc")
    ).one()
    print(f"{acme.name} supplies: {acme.products}")

    # Many-to-One: product -> its supplier.
    monitor = product_by_sku(session, "MN-003")
    print(f"{monitor.name} is supplied by: {monitor.supplier.name}")

    # Many-to-Many: product -> its tags, and tag -> its products.
    keyboard = product_by_sku(session, "KB-001")
    print(f"{keyboard.name} tags: {[t.name for t in keyboard.tags]}")

    electronics = session.scalars(
        select(Tag).where(Tag.name == "electronics")
    ).first()
    print(f"'electronics' tag is on: {[p.name for p in electronics.products]}")


def update_and_delete(session: Session) -> None:
    banner("UPDATE & DELETE - change attributes, let the ORM write the SQL")

    # UPDATE: mutate the attribute, then commit.
    keyboard = product_by_sku(session, "KB-001")
    keyboard.price = Decimal("29.99")
    keyboard.notes = "Price adjusted for Q3"
    session.commit()
    session.refresh(keyboard)  # reload from DB to prove it persisted
    print(f"Updated -> {keyboard} (notes: {keyboard.notes!r})")

    # Reassign a relationship: move the Mouse to Globex.
    mouse = product_by_sku(session, "MS-002")
    globex = session.scalars(
        select(Supplier).where(Supplier.name == "Globex")
    ).one()
    mouse.supplier = globex
    session.commit()
    print(f"Mouse now supplied by: {mouse.supplier.name}")

    # DELETE a row.
    session.delete(mouse)
    session.commit()
    remaining = session.scalars(select(Product).order_by(Product.id)).all()
    print(f"After deleting Mouse, products are: {remaining}")


def main() -> None:
    # Start clean every run so output is predictable.
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    # Create every table registered on Base (CREATE TABLE IF NOT EXISTS).
    banner("CREATE TABLES - Base.metadata.create_all(engine)")
    Base.metadata.create_all(engine)

    # A Session is one unit of work. The 'with' block closes it (and returns
    # its connection to the pool) automatically.
    with Session(engine) as session:
        seed(session)
        read_examples(session)
        relationship_examples(session)
        update_and_delete(session)

    banner("DONE")
    print(f"Database file: {DB_FILE}")
    print("Re-read the SQL above (echo=True) and match it to Lesson 20's concepts.")


if __name__ == "__main__":
    main()
