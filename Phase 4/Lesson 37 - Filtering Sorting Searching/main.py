"""
Lesson 37 - Filtering, Sorting, Searching
-----------------------------------------
A SQLite-backed product catalog with ONE powerful GET /products endpoint that
combines filtering, searching, whitelisted sorting, and pagination on a single
dynamically-built query.

    filter:  category, min_price, max_price, in_stock
    search:  q  (case-insensitive, matches name OR description)
    sort:    sort_by (WHITELISTED) + order (asc|desc)
    page:    page + limit

Install once:

    pip install fastapi uvicorn sqlalchemy

How to run (from inside this folder):

    uvicorn main:app --reload

Try:
    /products?q=wireless&in_stock=true&min_price=20&sort_by=price&order=asc
    /products?sort_by=secret        -> 400 (not a whitelisted sort field)
"""

import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import Boolean, Date, Numeric, String, create_engine, func, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

DB_FILE = os.path.join(os.path.dirname(__file__), "catalog.db")
engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(50))
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    in_stock: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[date] = mapped_column(Date)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


# The ONLY fields a client may sort by. Client sends a key; we map it to a real
# column. Never put client text directly into ORDER BY.
SORTABLE = {
    "name": Product.name,
    "price": Product.price,
    "created_at": Product.created_at,
}

SEED = [
    ("Wireless Mouse", "Ergonomic wireless mouse", "electronics", 25.0, True, "2026-01-05"),
    ("Wireless Keyboard", "Compact wireless keyboard", "electronics", 45.0, True, "2026-02-10"),
    ("USB-C Cable", "Durable braided cable", "accessories", 9.5, True, "2026-03-01"),
    ("4K Monitor", "27-inch 4K display", "electronics", 320.0, False, "2026-01-20"),
    ("Desk Lamp", "LED desk lamp with dimmer", "home", 34.0, True, "2026-04-02"),
    ("Notebook", "A5 dotted notebook", "stationery", 6.0, True, "2026-02-18"),
    ("Standing Desk", "Adjustable standing desk", "furniture", 480.0, False, "2026-03-15"),
    ("Wireless Earbuds", "Noise-cancelling earbuds", "electronics", 89.0, True, "2026-04-22"),
    ("Coffee Mug", "Ceramic 350ml mug", "home", 12.0, True, "2026-01-30"),
    ("Mechanical Keyboard", "RGB mechanical keyboard", "electronics", 110.0, True, "2026-03-28"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Product)) == 0:
            db.add_all([
                Product(name=n, description=d, category=c, price=p,
                        in_stock=s, created_at=date.fromisoformat(dt))
                for (n, d, c, p, s, dt) in SEED
            ])
            db.commit()
    yield


app = FastAPI(title="Lesson 37 - Filter/Sort/Search", lifespan=lifespan)


@app.get("/products")
def list_products(
    db: DB,
    # --- search ---
    q: str | None = Query(None, description="Search name or description"),
    # --- filters ---
    category: str | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    in_stock: bool | None = None,
    # --- sort ---
    sort_by: str = Query("created_at", description="One of: name, price, created_at"),
    order: Literal["asc", "desc"] = "desc",
    # --- pagination ---
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(400, "min_price cannot be greater than max_price")

    stmt = select(Product)

    # 1. FILTER - apply each condition only if the client supplied it.
    if category is not None:
        stmt = stmt.where(Product.category == category)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if in_stock is not None:
        stmt = stmt.where(Product.in_stock == in_stock)

    # 2. SEARCH - case-insensitive partial match across multiple fields.
    if q:
        term = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(term) | Product.description.ilike(term))

    # 3. COUNT the filtered/searched set (before sorting/paginating).
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    # 4. SORT - WHITELISTED. Client sends a key; we map it to a real column.
    column = SORTABLE.get(sort_by)
    if column is None:
        raise HTTPException(
            400, f"Cannot sort by '{sort_by}'. Allowed: {list(SORTABLE)}"
        )
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc())

    # 5. PAGINATE
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    rows = db.scalars(stmt).all()

    return {
        "items": [
            {"id": r.id, "name": r.name, "category": r.category,
             "price": float(r.price), "in_stock": r.in_stock,
             "created_at": r.created_at.isoformat()}
            for r in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "filters_applied": {
            "q": q, "category": category, "min_price": min_price,
            "max_price": max_price, "in_stock": in_stock,
            "sort_by": sort_by, "order": order,
        },
    }
