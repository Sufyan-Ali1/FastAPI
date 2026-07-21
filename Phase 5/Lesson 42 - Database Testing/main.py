"""
Lesson 42 - Database Testing (the app under test)
-------------------------------------------------
A database-backed items API. In normal use it runs against a real SQLite file;
in tests, conftest.py OVERRIDES get_db to point at an isolated test database.

The tests live in:

    conftest.py   - builds an isolated test database per test (fixtures)
    test_db.py    - CRUD tests + proof of isolation

Run with:

    pip install fastapi uvicorn httpx pytest sqlalchemy
    pytest -v
"""

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Numeric, String, create_engine, func, select
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
    name: Mapped[str] = mapped_column(String(50))
    price: Mapped[float] = mapped_column(Numeric(10, 2))


# The dependency the tests will OVERRIDE to use a test database.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


class ItemIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    price: float = Field(..., gt=0)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: float


app = FastAPI(title="Lesson 42 - Database Testing")

# Create tables for normal (non-test) runs. Tests build their own schema
# against a separate test engine (see conftest.py).
Base.metadata.create_all(bind=engine)


@app.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemIn, db: DB):
    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/items")
def list_items(db: DB):
    items = db.scalars(select(Item).order_by(Item.id)).all()
    total = db.scalar(select(func.count()).select_from(Item))
    return {"items": [ItemOut.model_validate(i).model_dump() for i in items],
            "total": total}


@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: DB):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: DB):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    db.delete(item)
    db.commit()
