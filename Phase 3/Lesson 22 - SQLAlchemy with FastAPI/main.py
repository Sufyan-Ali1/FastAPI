"""
Lesson 22 - SQLAlchemy with FastAPI
-----------------------------------
The ORM from Lesson 21, now inside a real FastAPI app. This is where we STOP
using JSON files and start using a real database.

Key ideas demonstrated:
    - engine + SessionLocal (created ONCE, app-wide)
    - get_db dependency (one Session per request, using the yield pattern)
    - tables created at startup via a lifespan handler
    - full CRUD endpoints for Products and Suppliers
    - the database enforces UNIQUE(sku) -> IntegrityError -> 409
    - a One-to-Many relationship (Supplier -> Products)

NOTE: Responses are shaped by hand with `to_dict()` ON PURPOSE. Returning a
SQLAlchemy model directly does not serialize automatically. Lesson 23 fixes
this properly with `from_attributes=True` + `response_model`. Here we keep the
spotlight on the SESSION + CRUD mechanics.

Install once:

    pip install fastapi uvicorn sqlalchemy

How to run (from inside this folder):

    uvicorn main:app --reload

Then open:
    http://127.0.0.1:8000/docs
"""

import os
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, Numeric, String, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


# ===========================================================================
# DATABASE SETUP  (created ONCE - in a bigger app this lives in database.py)
# ===========================================================================
DB_FILE = os.path.join(os.path.dirname(__file__), "shop.db")

engine = create_engine(
    f"sqlite:///{DB_FILE}",
    echo=False,  # set True to watch every SQL statement in the console
    # SQLite-only: FastAPI runs sync endpoints in a threadpool, so a session
    # may touch the DB from another thread. PostgreSQL/MySQL do NOT need this.
    connect_args={"check_same_thread": False},
)

# The Session FACTORY. Call SessionLocal() to make a new short-lived Session.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# ===========================================================================
# MODELS  (SQLAlchemy = database tables) - same style as Lesson 21
# ===========================================================================
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="supplier")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[str] = mapped_column(String(30), unique=True)  # UNIQUE constraint
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    supplier: Mapped["Supplier"] = relationship(back_populates="products")


# ===========================================================================
# THE get_db DEPENDENCY  (the heart of this lesson)
# One Session per request: open it, yield it, always close it.
# ===========================================================================
def get_db():
    db = SessionLocal()  # borrow a pooled connection, wrap it in a Session
    try:
        yield db  # hand the session to the endpoint
    finally:
        db.close()  # ALWAYS runs -> return the connection to the pool


# `Annotated` alias so endpoint signatures stay short and readable.
DB = Annotated[Session, Depends(get_db)]


# ===========================================================================
# PYDANTIC SCHEMAS  (request validation) - Pydantic = NOT a database table
# ===========================================================================
class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    sku: str = Field(..., min_length=3, max_length=30)
    price: float = Field(..., gt=0)
    supplier_id: int = Field(..., ge=1)


# ===========================================================================
# SMALL HELPERS to shape responses by hand (Lesson 23 automates this).
# ===========================================================================
def supplier_to_dict(s: Supplier) -> dict:
    return {"id": s.id, "name": s.name}


def product_to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "price": float(p.price),
        "supplier_id": p.supplier_id,
    }


# ===========================================================================
# APP + LIFESPAN  (create tables once at startup)
# ===========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # CREATE TABLE IF NOT EXISTS
    yield
    # (shutdown logic could go here)


app = FastAPI(
    title="Lesson 22 - Products API (database-backed)",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": "See /docs. This API is backed by SQLite via SQLAlchemy."}


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------
@app.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: DB):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier_to_dict(supplier)


@app.get("/suppliers")
def list_suppliers(db: DB):
    suppliers = db.scalars(select(Supplier).order_by(Supplier.id)).all()
    return [supplier_to_dict(s) for s in suppliers]


@app.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int, db: DB):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return supplier_to_dict(supplier)


# ---------------------------------------------------------------------------
# PRODUCTS - full CRUD
# ---------------------------------------------------------------------------
@app.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: DB):
    # The referenced supplier must exist (we check explicitly for a clean 404).
    if db.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    product = Product(**payload.model_dump())  # schema -> model
    db.add(product)
    try:
        db.commit()  # INSERT; UNIQUE(sku) is enforced by the database
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"SKU '{payload.sku}' already exists"
        )
    db.refresh(product)  # load the DB-generated id
    return product_to_dict(product)


@app.get("/products")
def list_products(
    db: DB,
    q: str | None = Query(None, description="Search by product name"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
):
    stmt = select(Product)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))  # case-insensitive
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)

    products = db.scalars(stmt.order_by(Product.id)).all()
    return [product_to_dict(p) for p in products]


@app.get("/products/{product_id}")
def get_product(product_id: int, db: DB):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product_to_dict(product)


@app.put("/products/{product_id}")
def update_product(product_id: int, payload: ProductCreate, db: DB):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    if db.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    for field, value in payload.model_dump().items():
        setattr(product, field, value)  # mutate attributes
    try:
        db.commit()  # ORM writes the UPDATE
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"SKU '{payload.sku}' already exists"
        )
    db.refresh(product)
    return product_to_dict(product)


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: DB):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    db.delete(product)
    db.commit()
    # 204 -> no response body
