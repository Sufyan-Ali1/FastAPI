"""
conftest.py - fixtures that give every test its own isolated database.

Strategy used here: FRESH SCHEMA PER TEST (Strategy 1). Each test gets a brand
new in-memory SQLite database, so tests are fully isolated and order-independent.

Key detail: in-memory SQLite normally gives each connection its OWN empty
database. `poolclass=StaticPool` makes all connections share ONE in-memory DB,
so the app's overridden session and the test's direct session see the same data.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import Base, app, get_db


@pytest.fixture
def db_engine():
    # A fresh in-memory database for EACH test (function-scoped).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,           # share one in-memory DB across connections
    )
    Base.metadata.create_all(engine)    # build the schema
    yield engine
    Base.metadata.drop_all(engine)      # tear it down
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    # A direct session for asserting database state inside tests.
    TestingSessionLocal = sessionmaker(bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine):
    # A TestClient whose get_db points at the TEST engine (not the real DB).
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()    # always reset overrides


@pytest.fixture
def sample_items(db_session):
    # Seed data into the fresh test database for tests that need existing rows.
    from main import Item

    items = [Item(name="Seed A", price=1.0), Item(name="Seed B", price=2.0)]
    db_session.add_all(items)
    db_session.commit()
    return items
