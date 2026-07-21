"""
Lesson 36 - Pagination
----------------------
A SQLite-backed API implementing BOTH pagination styles over the same data:

    GET /items?page=&limit=          -> limit/offset (page numbers + total)
    GET /items/cursor?cursor=&limit= -> cursor / keyset (fast + stable)

The seed data lets you see the trade-offs: offset supports page numbers and a
total; cursor gives a stable "next" token that does not drift when rows are
inserted mid-pagination.

No extra installs beyond SQLAlchemy.

    pip install fastapi uvicorn sqlalchemy

How to run (from inside this folder):

    uvicorn main:app --reload
"""

import base64
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import String, create_engine, func, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

DB_FILE = os.path.join(os.path.dirname(__file__), "items.db")
engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


# --- opaque cursor helpers (base64 so clients treat it as a token) ----------
def encode_cursor(value: int) -> str:
    return base64.urlsafe_b64encode(str(value).encode()).decode()


def decode_cursor(token: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(token.encode()).decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Item)) == 0:
            db.add_all([Item(name=f"item-{i:03d}") for i in range(1, 43)])  # 42 rows
            db.commit()
    yield


app = FastAPI(title="Lesson 36 - Pagination", lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "Compare /items (offset) vs /items/cursor (keyset)."}


# ===========================================================================
# LIMIT/OFFSET pagination - page numbers + total. Supports random page jumps.
# ===========================================================================
@app.get("/items")
def list_offset(
    db: DB,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),   # bounded - never trust a huge limit
):
    total = db.scalar(select(func.count()).select_from(Item))
    offset = (page - 1) * limit
    # ORDER BY a unique key is mandatory for a well-defined page.
    rows = db.scalars(select(Item).order_by(Item.id).offset(offset).limit(limit)).all()
    total_pages = (total + limit - 1) // limit
    return {
        "items": [{"id": r.id, "name": r.name} for r in rows],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


# ===========================================================================
# CURSOR / KEYSET pagination - "rows after this point". Fast + stable.
# ===========================================================================
@app.get("/items/cursor")
def list_cursor(
    db: DB,
    cursor: str | None = Query(None, description="Opaque token from next_cursor"),
    limit: int = Query(10, ge=1, le=100),
):
    stmt = select(Item).order_by(Item.id).limit(limit)
    if cursor is not None:
        last_id = decode_cursor(cursor)
        stmt = stmt.where(Item.id > last_id)   # start AFTER the cursor - index seek
    rows = db.scalars(stmt).all()

    next_cursor = encode_cursor(rows[-1].id) if rows else None
    # There is more if this page came back full (a cheap heuristic).
    has_more = len(rows) == limit
    return {
        "items": [{"id": r.id, "name": r.name} for r in rows],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
