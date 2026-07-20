"""
Lesson 24 - Models + Base (the source of truth Alembic compares against)
------------------------------------------------------------------------
Alembic works by comparing THIS file's `Base.metadata` (what your models say
the schema SHOULD be) against the ACTUAL database, then generating the SQL to
close the gap.

Keep this the single place your tables are defined. `alembic/env.py` imports
`Base` and `engine` from here.
"""

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# The database this project migrates. Alembic reads the same file.
DATABASE_URL = "sqlite:///shop.db"

engine = create_engine(DATABASE_URL, echo=False)


class Base(DeclarativeBase):
    pass


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="supplier")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[str] = mapped_column(String(30), unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    supplier: Mapped["Supplier"] = relationship(back_populates="products")

    # --- Lesson step 2: this column was ADDED after the initial migration, to
    #     demonstrate `alembic revision --autogenerate` detecting a model change.
    #     (Comment it back out and re-run to reproduce the "before" state.)
    description: Mapped[str | None] = mapped_column(String(300))
