"""
Lesson 23 - Pydantic + SQLAlchemy Together
------------------------------------------
The SAME Products API as Lesson 22, rebuilt the CLEAN way. The manual
`to_dict()` helpers are gone. Instead we use:

    - from_attributes=True   -> Pydantic can read SQLAlchemy objects directly
    - response_model=...     -> FastAPI serializes + FILTERS + validates output
    - schema separation      -> ProductCreate / ProductRead / ProductUpdate

To PROVE response_model filtering, the Product MODEL has an internal `cost`
column that is deliberately NOT on any Read schema - so it never leaks into a
response, automatically.

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
from pydantic import BaseModel, ConfigDict, Field
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
# DATABASE SETUP (created once)
# ===========================================================================
DB_FILE = os.path.join(os.path.dirname(__file__), "shop.db")

engine = create_engine(
    f"sqlite:///{DB_FILE}",
    echo=False,
    connect_args={"check_same_thread": False},  # SQLite + FastAPI (Lesson 22)
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# ===========================================================================
# MODELS (SQLAlchemy = database tables)
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
    # INTERNAL field - what we paid the supplier. Must NEVER reach a customer.
    # It exists on the model but is absent from every Read schema below, so
    # response_model strips it from all responses automatically.
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    supplier: Mapped["Supplier"] = relationship(back_populates="products")


# ===========================================================================
# get_db DEPENDENCY (one Session per request - Lesson 22)
# ===========================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


# ===========================================================================
# SCHEMAS (Pydantic) - the Create / Read / Update separation pattern
# ===========================================================================

# ---- Suppliers ----
class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # ORM mode
    id: int
    name: str


# ---- Products ----
class ProductCreate(BaseModel):
    """INPUT for POST. Note: no `id` (server generates it) and no `cost`
    exposure rules here - this is what a client is allowed to send."""
    name: str = Field(..., min_length=2, max_length=100)
    sku: str = Field(..., min_length=3, max_length=30)
    price: float = Field(..., gt=0)
    cost: float = Field(0, ge=0)  # accepted on input, but never returned
    supplier_id: int = Field(..., ge=1)


class ProductRead(BaseModel):
    """OUTPUT. Only these fields are ever returned. `cost` is intentionally
    absent, so it can never leak into a response."""
    model_config = ConfigDict(from_attributes=True)  # ORM mode
    id: int
    name: str
    sku: str
    price: float
    supplier_id: int


class ProductWithSupplier(ProductRead):
    """OUTPUT with the related supplier nested (relationship serialization)."""
    supplier: SupplierRead


class ProductUpdate(BaseModel):
    """PARTIAL update for PATCH. Every field optional."""
    name: str | None = Field(None, min_length=2, max_length=100)
    price: float | None = Field(None, gt=0)
    cost: float | None = Field(None, ge=0)
    supplier_id: int | None = Field(None, ge=1)


# ===========================================================================
# APP + LIFESPAN
# ===========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Lesson 23 - Products API (schemas + response_model)",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": "See /docs. Responses use Pydantic schemas + ORM mode."}


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------
@app.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: DB):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier  # <-- ORM object; response_model converts it


@app.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(db: DB):
    return db.scalars(select(Supplier).order_by(Supplier.id)).all()


@app.get("/suppliers/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: int, db: DB):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return supplier


# ---------------------------------------------------------------------------
# PRODUCTS - full CRUD, now with schemas
# ---------------------------------------------------------------------------
@app.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: DB):
    if db.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"SKU '{payload.sku}' already exists"
        )
    db.refresh(product)
    return product


@app.get("/products", response_model=list[ProductRead])
def list_products(
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
    return db.scalars(stmt.order_by(Product.id)).all()


@app.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: DB):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


@app.get("/products/{product_id}/full", response_model=ProductWithSupplier)
def get_product_full(product_id: int, db: DB):
    """Same product, but with the related supplier nested in the response."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product  # FastAPI reads product.supplier and nests it


@app.patch("/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: DB):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    updates = payload.model_dump(exclude_unset=True)  # only fields client sent
    if "supplier_id" in updates and db.get(Supplier, updates["supplier_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    for field, value in updates.items():
        setattr(product, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "SKU already exists")
    db.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: DB):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    db.delete(product)
    db.commit()
