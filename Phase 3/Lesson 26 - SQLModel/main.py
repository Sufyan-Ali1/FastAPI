"""
Lesson 26 - SQLModel
--------------------
The SAME Products API one more time, now built with SQLModel - the library by
FastAPI's author that FUSES SQLAlchemy + Pydantic into one class.

The headline: fields are declared ONCE. A shared `ProductBase` (a plain schema)
feeds the `table=True` model AND the Create/Read/Update schemas. Compare the
field repetition here to Lesson 23's main.py.

Key SQLModel ideas shown:
    - SQLModel base class (both a table AND a Pydantic model)
    - table=True  -> real database table
    - table=False (default) -> request/response schema
    - one Field() carries validation + column options
    - session.exec(select(...)) returns objects directly
    - no from_attributes needed - table classes serialize as-is

Install once:

    pip install fastapi uvicorn sqlmodel

How to run (from inside this folder):

    uvicorn main:app --reload

Then open:
    http://127.0.0.1:8000/docs
"""

import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select


# ===========================================================================
# DATABASE SETUP - SQLModel wraps the same SQLAlchemy engine/session
# ===========================================================================
DB_FILE = os.path.join(os.path.dirname(__file__), "shop.db")

engine = create_engine(
    f"sqlite:///{DB_FILE}",
    echo=False,
    connect_args={"check_same_thread": False},  # SQLite + FastAPI (Lesson 22)
)


def get_session():
    with Session(engine) as session:  # SQLModel's Session (thin subclass)
        yield session


DB = Annotated[Session, Depends(get_session)]


# ===========================================================================
# SUPPLIERS - shared base -> table + schemas, all from one field list
# ===========================================================================
class SupplierBase(SQLModel):
    name: str = Field(min_length=2, max_length=80)


class Supplier(SupplierBase, table=True):  # table=True => real DB table
    __tablename__ = "suppliers"
    id: int | None = Field(default=None, primary_key=True)


class SupplierCreate(SupplierBase):  # no table= => plain schema (input)
    pass


class SupplierRead(SupplierBase):  # plain schema (output) - adds id
    id: int


# ===========================================================================
# PRODUCTS - the same one-base pattern
# ===========================================================================
class ProductBase(SQLModel):
    name: str = Field(min_length=2, max_length=100)
    sku: str = Field(min_length=3, max_length=30)
    price: float = Field(gt=0)
    supplier_id: int = Field(foreign_key="suppliers.id", ge=1)


class Product(ProductBase, table=True):
    __tablename__ = "products"
    id: int | None = Field(default=None, primary_key=True)
    # sku is unique + indexed at the DB level (Field carries column options too)
    sku: str = Field(min_length=3, max_length=30, unique=True, index=True)


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    id: int


class ProductUpdate(SQLModel):  # partial update - every field optional
    name: str | None = Field(default=None, min_length=2, max_length=100)
    price: float | None = Field(default=None, gt=0)
    supplier_id: int | None = Field(default=None, ge=1)


# ===========================================================================
# APP + LIFESPAN (create tables from every table=True class)
# ===========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)  # Alembic still applies in real apps
    yield


app = FastAPI(title="Lesson 26 - Products API (SQLModel)", lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "See /docs. Built with SQLModel (SQLAlchemy + Pydantic)."}


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------
@app.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, session: DB):
    supplier = Supplier.model_validate(payload)  # schema -> table object
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier  # a table object; serialized as SupplierRead (no from_attributes)


@app.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(session: DB):
    return session.exec(select(Supplier).order_by(Supplier.id)).all()


@app.get("/suppliers/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: int, session: DB):
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return supplier


# ---------------------------------------------------------------------------
# PRODUCTS - full CRUD
# ---------------------------------------------------------------------------
@app.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, session: DB):
    if session.get(Supplier, payload.supplier_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    product = Product.model_validate(payload)
    session.add(product)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"SKU '{payload.sku}' already exists"
        )
    session.refresh(product)
    return product


@app.get("/products", response_model=list[ProductRead])
def list_products(
    session: DB,
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
    return session.exec(stmt.order_by(Product.id)).all()


@app.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, session: DB):
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


@app.patch("/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, session: DB):
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    updates = payload.model_dump(exclude_unset=True)  # only fields client sent
    if "supplier_id" in updates and session.get(Supplier, updates["supplier_id"]) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    for field, value in updates.items():
        setattr(product, field, value)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "SKU already exists")
    session.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, session: DB):
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    session.delete(product)
    session.commit()
