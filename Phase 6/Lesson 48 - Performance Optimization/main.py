"""
Lesson 48 - Performance Optimization
------------------------------------
Makes the N+1 query problem VISIBLE by counting the SQL statements each endpoint
fires. Both endpoints return identical data:

    GET /authors/n-plus-1   -> query_count = 1 + N  (lazy loading, the bug)
    GET /authors/optimized  -> query_count = 2      (selectinload, the fix)

A SQLAlchemy event listener counts every statement the engine executes.

    pip install fastapi uvicorn sqlalchemy

How to run (from inside this folder):

    uvicorn main:app --reload

Then compare:
    curl http://127.0.0.1:8000/authors/n-plus-1
    curl http://127.0.0.1:8000/authors/optimized
"""

import contextvars
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import ForeignKey, String, create_engine, event, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    selectinload,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

# StaticPool shares ONE in-memory DB across connections (so the startup seed and
# request handlers see the same data - the Lesson 42 gotcha).
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    books: Mapped[list["Book"]] = relationship(back_populates="author")


class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
    author: Mapped["Author"] = relationship(back_populates="books")


# ---------------------------------------------------------------------------
# A per-request SQL query COUNTER via a SQLAlchemy event listener.
# ---------------------------------------------------------------------------
query_count_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    "query_count", default=0
)


@event.listens_for(engine, "before_cursor_execute")
def _count_queries(conn, cursor, statement, parameters, context, executemany):
    query_count_var.set(query_count_var.get() + 1)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]

app = FastAPI(title="Lesson 48 - Performance")


@app.on_event("startup")
def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Author).limit(1)) is None:
            for a in range(1, 11):  # 10 authors, 3 books each
                author = Author(name=f"Author {a}")
                author.books = [Book(title=f"Book {a}-{b}") for b in range(1, 4)]
                db.add(author)
            db.commit()


# ---------------------------------------------------------------------------
# N+1: accessing author.books lazily inside the loop fires one query per author.
# ---------------------------------------------------------------------------
@app.get("/authors/n-plus-1")
def authors_n_plus_1(db: DB):
    query_count_var.set(0)
    authors = db.scalars(select(Author).order_by(Author.id)).all()  # 1 query
    result = []
    for author in authors:
        # Lazy load -> +1 query PER author (this is the N+1 bug)
        result.append({"name": author.name, "book_count": len(author.books)})
    return {"query_count": query_count_var.get(), "authors": result}


# ---------------------------------------------------------------------------
# FIXED: selectinload eager-loads all books up front -> 2 queries total.
# ---------------------------------------------------------------------------
@app.get("/authors/optimized")
def authors_optimized(db: DB):
    query_count_var.set(0)
    stmt = select(Author).options(selectinload(Author.books)).order_by(Author.id)
    authors = db.scalars(stmt).all()  # 2 queries: authors + all their books
    result = [
        {"name": author.name, "book_count": len(author.books)} for author in authors
    ]
    return {"query_count": query_count_var.get(), "authors": result}
