"""
Lesson 25 - Async SQLAlchemy
----------------------------
The SAME Products API as Lesson 23, converted to be fully ASYNC. Compare the
two files side by side: the MODELS and SCHEMAS are identical - only the engine,
session, and the `await`ed DB calls change.

Async plumbing used here:
    - create_async_engine + async_sessionmaker -> AsyncSession
    - async def get_db() with `async with`
    - async def endpoints that `await` every DB round-trip
    - selectinload(...) to eager-load a relationship (async can't lazy-load)

Install once:

    pip install fastapi uvicorn sqlalchemy aiosqlite

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
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, Numeric, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
)


# ===========================================================================
# ASYNC DATABASE SETUP (created once)
# ===========================================================================
DB_FILE = os.path.join(os.path.dirname(__file__), "shop.db")

# Note the async driver in the URL: sqlite + aiosqlite.
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_FILE}", echo=False)

# async_sessionmaker builds AsyncSession objects.
# expire_on_commit=False keeps attributes loaded after commit (see theory §4).
AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=False
)


class Base(DeclarativeBase):
    pass


# ===========================================================================
# MODELS - IDENTICAL to the sync lessons. Async changes nothing here.
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
    sku: Mapped[str] = mapped_column(String(30), unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    supplier: Mapped["Supplier"] = relationship(back_populates="products")


# ===========================================================================
# ASYNC get_db DEPENDENCY - one AsyncSession per request
# ===========================================================================
async def get_db():
    async with AsyncSessionLocal() as db:  # async context manager -> auto-close
        yield db


DB = Annotated[AsyncSession, Depends(get_db)]


# ===========================================================================
# SCHEMAS (Pydantic) - IDENTICAL to Lesson 23
# ===========================================================================
class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    sku: str = Field(..., min_length=3, max_length=30)
    price: float = Field(..., gt=0)
    supplier_id: int = Field(..., ge=1)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sku: str
    price: float
    supplier_id: int


class ProductWithSupplier(ProductRead):
    supplier: SupplierRead


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    price: float | None = Field(None, gt=0)
    supplier_id: int | None = Field(None, ge=1)


# ===========================================================================
# APP + ASYNC LIFESPAN (create tables via run_sync; dispose pool on shutdown)
# ===========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # bridge sync create_all
    yield
    await engine.dispose()  # cleanly close pooled connections


app = FastAPI(title="Lesson 25 - Products API (async)", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "See /docs. This API uses async SQLAlchemy + aiosqlite."}


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------
@app.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(payload: SupplierCreate, db: DB):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)  # staging only - not awaited
    await db.commit()  # DB round-trip - awaited
    await db.refresh(supplier)
    return supplier


@app.get("/suppliers", response_model=list[SupplierRead])
async def list_suppliers(db: DB):
    result = await db.execute(select(Supplier).order_by(Supplier.id))
    return result.scalars().all()


@app.get("/suppliers/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: int, db: DB):
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return supplier


# ---------------------------------------------------------------------------
# PRODUCTS - full async CRUD
# ---------------------------------------------------------------------------
@app.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, db: DB):
    if await db.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    product = Product(**payload.model_dump())
    db.add(product)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"SKU '{payload.sku}' already exists"
        )
    await db.refresh(product)
    return product


@app.get("/products", response_model=list[ProductRead])
async def list_products(
    db: DB,
    q: str | None = Query(None, description="Search by product name"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
):
    stmt = select(Product)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    result = await db.execute(stmt.order_by(Product.id))
    return result.scalars().all()


@app.get("/products/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, db: DB):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


@app.get("/products/{product_id}/full", response_model=ProductWithSupplier)
async def get_product_full(product_id: int, db: DB):
    # ASYNC can't lazy-load relationships, so we EAGER-load supplier here.
    # Remove selectinload(...) and this endpoint will error on product.supplier.
    stmt = (
        select(Product)
        .options(selectinload(Product.supplier))
        .where(Product.id == product_id)
    )
    product = (await db.execute(stmt)).scalars().first()
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


@app.patch("/products/{product_id}", response_model=ProductRead)
async def update_product(product_id: int, payload: ProductUpdate, db: DB):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    updates = payload.model_dump(exclude_unset=True)
    if "supplier_id" in updates and await db.get(Supplier, updates["supplier_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    for field, value in updates.items():
        setattr(product, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "SKU already exists")
    await db.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, db: DB):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    await db.delete(product)
    await db.commit()
