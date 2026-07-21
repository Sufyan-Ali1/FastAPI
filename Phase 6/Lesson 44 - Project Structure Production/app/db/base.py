"""db/base.py - database plumbing: engine, Session factory, Base, get_db.

Everything about HOW we connect to the database lives here, so models and
services never worry about connection setup.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """The DB session dependency (Lesson 22) - injected into routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
