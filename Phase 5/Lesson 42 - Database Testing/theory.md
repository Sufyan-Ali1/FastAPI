# Lesson 42 — Database Testing

> **Goal of this lesson:** Test endpoints that use a **real database** — safely. Never touch production data: spin up a **separate test database**, override the DB session dependency (Lesson 41), and give **every test a clean slate** using **fixtures** with either fresh-schema or **transaction rollback** isolation.
>
> `main.py` is a database-backed app; `conftest.py` builds an isolated test database per test, and `test_db.py` proves the isolation.

---

## 1. The Problem — Tests Must Not Touch Real Data

A test that creates, updates, and deletes rows **cannot** run against your real database. It would:

- **Corrupt real data** (a test that deletes users… deletes real users).
- Be **non-deterministic** — results depend on whatever data happens to be there.
- **Leak between tests** — one test's rows change another test's outcome.

So database testing has two requirements: a **separate test database**, and **isolation** so each test starts from a known, clean state.

> 🔑 Golden rule: **tests get their own database**, and **each test starts clean.** Never run tests against production or shared dev data.

---

## 2. Choosing a Test Database

| Option | Notes |
|---|---|
| **In-memory SQLite** (`sqlite://`) | Fastest; created fresh, vanishes after. Great for most tests. |
| **Temporary SQLite file** | Like in-memory but on disk; survives across connections easily. |
| **A dedicated Postgres/MySQL test DB** | Most faithful if production uses that DB (SQLite ≠ Postgres in some behaviors). |

A common, pragmatic setup: **in-memory SQLite** for speed during development, and a **real database matching production** in CI for fidelity. Because you use SQLAlchemy, switching is just the connection URL.

> 💡 SQLite is convenient but not identical to Postgres (types, constraints, concurrency). If your app relies on Postgres-specific behavior, run at least some tests against a real Postgres test database.

---

## 3. Overriding the DB Session (the key move)

Your app injects a database session via `Depends(get_db)` (Lesson 22). In tests you **override** `get_db` to hand endpoints a session pointed at the **test** database — exactly the `app.dependency_overrides` technique from Lesson 41:

```python
def override_get_db():
    db = TestingSessionLocal()      # bound to the TEST engine
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
```

Now every endpoint uses the test database, and your real database is never touched.

> 🔑 Database testing = **override `get_db`** to point at a test database. The same override mechanism you used for auth now swaps the whole persistence layer.

---

## 4. In-Memory SQLite Needs `StaticPool`

In-memory SQLite has a catch: each new connection normally gets its **own separate** empty database. Your test session and the app's session would see *different* in-memory DBs. Fix it with a **`StaticPool`** (one shared connection) plus the threading arg:

```python
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite://",                                  # in-memory
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,                         # share ONE in-memory DB
)
```

With `StaticPool`, the test's direct session and the app's overridden session both see the **same** in-memory database — so data created via the API is visible to your assertions.

> 🔑 For **in-memory** SQLite tests, use `poolclass=StaticPool` (and `check_same_thread=False`), or your test and your app will silently use two different empty databases.

---

## 5. Isolation Strategy 1 — Fresh Schema Per Test

The simplest, bulletproof approach: **create all tables before each test, drop them after** (or use a brand-new in-memory engine per test). Each test begins with an empty schema.

```python
@pytest.fixture
def db_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)     # build schema
    yield engine
    Base.metadata.drop_all(engine)       # tear it down
    engine.dispose()
```

- **Function-scoped** → a fresh, empty database for **every** test.
- Simple to reason about; guaranteed clean.
- Slightly slower (rebuilds the schema per test), but fine for most suites — and with in-memory SQLite it's very fast.

---

## 6. Isolation Strategy 2 — Transaction Rollback Per Test

The faster approach for large suites: create the schema **once**, then wrap **each test in a transaction that is rolled back** at the end. Nothing a test does is ever committed permanently.

```python
@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()          # open a transaction
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()                    # undo EVERYTHING the test did
    connection.close()
```

- The schema is built once; each test's changes are **rolled back**, restoring a clean state instantly — no rebuild.
- Much faster for big suites.
- Subtlety: if the code under test **commits**, you must bind everything to the **same connection** and use a **SAVEPOINT** (nested transaction) so the outer rollback still undoes it. This is more fiddly than Strategy 1.

| | Strategy 1: fresh schema | Strategy 2: rollback |
|---|---|---|
| Speed | Rebuilds schema each test | Fastest (rollback only) |
| Simplicity | Very simple | More setup (commits + savepoints) |
| Isolation | Guaranteed | Guaranteed |
| Best for | Most suites, SQLite | Large suites, real Postgres |

> 🔑 **Fresh schema per test** is the easy, reliable default (this lesson uses it). **Transaction rollback** is the performance optimization for big suites — same isolation, faster, but trickier when the app commits.

---

## 7. Wiring the Fixtures Together

Put a `db_engine`, a `db_session` (for direct assertions), and a `client` (with `get_db` overridden) in `conftest.py`. All three share the same per-test engine, so API writes are visible to direct reads:

```python
@pytest.fixture
def client(db_engine):
    TestingSessionLocal = sessionmaker(bind=db_engine)
    def override_get_db():
        db = TestingSessionLocal()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()          # always reset
```

A test then requests whichever fixtures it needs:

```python
def test_create_item(client, db_session):
    client.post("/items", json={"name": "Widget", "price": 9.99})
    # assert via a DIRECT database read, not just the API response:
    assert db_session.query(Item).count() == 1
```

---

## 8. Two Ways to Assert

Database tests can check results two ways — use both where it adds confidence:

- **Through the API** — assert on the response (`status_code`, `json()`). Tests the endpoint's contract.
- **Directly in the database** — query the test session and assert rows exist/changed. Tests that the data actually persisted correctly.

```python
def test_delete_removes_the_row(client, db_session):
    created = client.post("/items", json={"name": "Temp", "price": 1.0}).json()
    client.delete(f"/items/{created['id']}")
    assert client.get(f"/items/{created['id']}").status_code == 404   # via API
    assert db_session.get(Item, created["id"]) is None                # via DB
```

> 🔑 Asserting **both** the API response **and** the database state catches bugs where the endpoint *says* success but didn't persist correctly (or vice versa).

---

## 9. Proving Isolation

The whole point: tests must not leak into each other. With per-test databases, a test that creates 3 items and a test that asserts an empty database both pass **regardless of run order**:

```python
def test_a_creates_items(client):
    client.post("/items", json={"name": "X", "price": 1})
    client.post("/items", json={"name": "Y", "price": 2})
    assert client.get("/items").json()["total"] == 2

def test_b_starts_empty(client):
    # A fresh database - test_a's items are NOT here.
    assert client.get("/items").json()["total"] == 0
```

If these both pass no matter the order, your isolation works. If `test_b` sees `test_a`'s data, your fixtures are leaking.

---

## 10. Seeding Test Data With Fixtures

Often a test needs pre-existing rows. A fixture can seed them into the fresh database:

```python
@pytest.fixture
def sample_items(db_session):
    items = [Item(name="Seed A", price=1.0), Item(name="Seed B", price=2.0)]
    db_session.add_all(items)
    db_session.commit()
    return items

def test_list_shows_seeded_items(client, sample_items):
    assert client.get("/items").json()["total"] == 2
```

Fixtures compose: `sample_items` depends on `db_session`, which depends on `db_engine`. Each test that requests `sample_items` gets its own freshly-seeded, isolated database.

> 🔑 Use fixtures to **seed** the exact data a test needs. Because each test's database is fresh, seed data never bleeds into other tests.

---

## 11. Real-World Use Case — Testing the Auction API

Testing the Phase 4 auction API's bidding:

- A `client` fixture points `get_db` at an **in-memory test database** — real auctions and bids never touched.
- A `sample_auction` fixture seeds a live auction with a starting price.
- Tests: placing a valid bid returns `201` **and** a direct DB query shows the new highest bid; a too-low bid returns `409` **and** the DB is unchanged; a seller bidding on their own auction is rejected.
- Every test runs against a **fresh** database, so bid history from one test never affects another. The suite runs in a second, deterministically, with zero risk to real data.

---

## 12. Mini Task

This lesson ships a DB-backed app with isolation fixtures.

1. Install: `pip install fastapi uvicorn httpx pytest sqlalchemy`
2. Run: `pytest -v` — watch the isolation tests pass in any order.
3. Read `conftest.py`: the `db_engine`, `db_session`, and `client` fixtures, and how `get_db` is overridden with `StaticPool` in-memory SQLite.
4. **Prove isolation:** note that `test_a` creates items and `test_b` asserts an empty database — both pass because each gets a fresh DB. Run `pytest -p no:randomly` or reorder them; they still pass.
5. **Experiment:**
   - Add a `sample_items` fixture that seeds two rows and a test that lists them.
   - Add a test that asserts **both** the API response and the database row after a create.
   - Temporarily change `db_engine` to **module** scope and watch tests start leaking into each other — then revert to function scope.
6. **Bonus:** Implement the transaction-rollback fixture (Strategy 2) and compare its speed on a larger set of tests.

---

## 13. Common Mistakes

| Mistake | Fix |
|---|---|
| Testing against the real/dev database | Use a separate test database; override `get_db`. |
| In-memory SQLite without `StaticPool` | Test and app see different empty DBs; add `StaticPool`. |
| Sharing one database across all tests | Use function-scoped fixtures so each test is isolated. |
| Forgetting to clear `dependency_overrides` | Clear in the `client` fixture teardown. |
| Only asserting the API response | Also assert the database state for persistence bugs. |
| Committing test data that leaks | Fresh schema per test, or rollback per test. |
| Assuming SQLite behaves like Postgres | Run some tests against a real Postgres test DB. |

---

## 14. Key Takeaways

- **Never test against real data.** Give tests their own database and start each test clean.
- **Override `get_db`** to point endpoints at a **test database** (the Lesson 41 override technique applied to persistence).
- For **in-memory SQLite**, use `poolclass=StaticPool` + `check_same_thread=False` so test and app share one DB.
- **Isolation Strategy 1 — fresh schema per test** (`create_all`/`drop_all`, function-scoped): simple and reliable.
- **Isolation Strategy 2 — transaction rollback per test**: faster for big suites, but trickier when the app commits (needs savepoints).
- Wire **fixtures** (`db_engine`, `db_session`, `client`) in `conftest.py`; each test gets an isolated database.
- Assert **both** the API response **and** the database state; **seed** data with fixtures.
- Isolation means tests pass in **any order** — that's the proof it works.

---

## ➡️ Next Lesson

**Lesson 43 — Coverage & CI**
- Measuring test coverage with `pytest-cov`
- What coverage does (and doesn't) tell you
- Running tests automatically with GitHub Actions
