# Lesson 40 — Testing Fundamentals

> **Goal of this lesson:** Start testing your APIs automatically instead of poking them by hand. Learn **`pytest`** basics, FastAPI's **`TestClient`** (sync) for endpoint tests, and **`httpx.AsyncClient`** (async) for async apps. This is the foundation of Phase 5 — and it's exactly the verification I've been doing on every lesson, now formalized.
>
> This lesson's "code" is **test files**. `main.py` is a small app; `test_main.py` and `test_async.py` are the real content. Run them with `pytest`.

---

## 1. Why Automated Tests?

Until now you've verified endpoints by hand — opening `/docs`, running `curl`, eyeballing responses. That doesn't scale:

- You can't re-check 50 endpoints by hand after every change.
- You'll forget edge cases you already fixed (they **regress**).
- Refactoring is scary because nothing tells you what broke.

**Automated tests** are code that calls your API and **asserts** the results. Run them in a second, after every change, and get instant confidence that everything still works.

| Without tests | With tests |
|---|---|
| Manually click through `/docs` | `pytest` runs everything in seconds |
| Fear refactoring | Refactor freely; tests catch breakage |
| Bugs return silently | A regression fails a test immediately |
| "Works on my machine" | Reproducible, documented behavior |

> 🔑 Tests are **living documentation + a safety net.** They describe exactly how your API is supposed to behave, and they scream the moment it stops behaving that way.

---

## 2. `pytest` Basics

**`pytest`** is the standard Python test framework. The essentials:

- A **test** is a function named `test_*` in a file named `test_*.py`.
- You check things with the plain **`assert`** statement — no special methods.
- Run everything with the `pytest` command; it discovers and runs all tests.

```python
# test_math.py
def test_addition():
    assert 1 + 1 == 2

def test_string():
    result = "hello".upper()
    assert result == "HELLO"
```

```bash
pytest                 # run all tests
pytest -v              # verbose: show each test name + PASS/FAIL
pytest test_main.py    # run one file
pytest -k "login"      # run tests whose name matches "login"
pytest -x              # stop at the first failure
```

When an `assert` fails, pytest shows you **exactly what the values were** — no need for print debugging.

> 🔑 pytest's whole model: functions named `test_*`, plain `assert`, auto-discovery. That simplicity is why it won.

---

## 3. The AAA Pattern

A good test has three clear phases — **Arrange, Act, Assert**:

```python
def test_create_item():
    # Arrange: set up inputs / state
    payload = {"name": "Widget", "price": 9.99}

    # Act: do the one thing under test
    response = client.post("/items", json=payload)

    # Assert: verify the outcome
    assert response.status_code == 201
    assert response.json()["name"] == "Widget"
```

Keep each test focused on **one behavior**. A test named `test_create_item_rejects_negative_price` should test exactly that — not five other things.

> 🔑 One test = one behavior, in Arrange → Act → Assert order. Small, focused tests pinpoint failures; giant tests hide them.

---

## 4. `TestClient` — Testing FastAPI Endpoints

FastAPI's **`TestClient`** (built on `httpx`, wrapping Starlette's) lets you call your app **in-process** — no running server, no network. You've seen me use it all along:

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello"}

def test_create_item():
    response = client.post("/items", json={"name": "Pen", "price": 1.5})
    assert response.status_code == 201
    assert response.json()["name"] == "Pen"
```

- `TestClient(app)` wraps your FastAPI app.
- Call it like a requests/httpx client: `.get()`, `.post(json=...)`, `.put()`, `.delete()`, with `params=`, `headers=`, `data=` (form), etc.
- The response has `.status_code`, `.json()`, `.text`, `.headers` — assert against them.
- It's **fast** (in-process) and needs no `uvicorn`.

### 4.1 Testing the whole surface

Real tests cover success **and** failure paths:

```python
def test_get_missing_item_returns_404():
    assert client.get("/items/9999").status_code == 404

def test_create_item_invalid_body_returns_422():
    assert client.post("/items", json={"name": ""}).status_code == 422
```

> 🔑 Test the **contract**: status codes, response shape, validation errors (422), not-found (404), conflicts (409). The failure paths matter as much as the happy path.

---

## 5. Lifespan and the `with` Block

If your app uses a **lifespan** handler (Lesson 22+: creating tables, initializing a cache) those run only when the app "starts up." To trigger lifespan in tests, use `TestClient` as a **context manager**:

```python
def test_with_lifespan():
    with TestClient(app) as client:      # runs startup (and shutdown on exit)
        response = client.get("/products")
        assert response.status_code == 200
```

- `TestClient(app)` **without** `with` → lifespan does **not** run (fine for apps that don't need it).
- `with TestClient(app) as client:` → lifespan startup runs on enter, shutdown on exit.

> 🔑 If your app initializes anything in **lifespan** (DB tables, cache, connections), test it inside `with TestClient(app) as client:` — otherwise that setup never happens and tests fail confusingly.

---

## 6. `httpx.AsyncClient` — Testing Async Apps

`TestClient` runs synchronously (it drives async apps under the hood, which is fine for most tests). But sometimes you want a genuinely **async** test — to `await` inside it, test async dependencies, or exercise concurrency. For that, use **`httpx.AsyncClient`** with an ASGI transport:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_root_async():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
```

- **`ASGITransport(app=app)`** points httpx straight at your FastAPI app (no network).
- The test is **`async def`** and you **`await`** the request.
- **`@pytest.mark.asyncio`** tells pytest to run the coroutine (needs the `pytest-asyncio` plugin).

### 6.1 Enabling async tests

Install and configure the plugin:

```bash
pip install pytest-asyncio
```

```ini
# pytest.ini (or pyproject.toml)
[pytest]
asyncio_mode = auto        # treat async test functions as asyncio tests automatically
```

With `asyncio_mode = auto`, you can even drop the `@pytest.mark.asyncio` decorator.

> 🔑 Use **`TestClient`** for most endpoint tests (simpler, sync). Reach for **`httpx.AsyncClient` + `ASGITransport`** when you specifically need to `await` inside the test or exercise async behavior. Both call your app in-process.

---

## 7. `TestClient` vs `httpx.AsyncClient`

| | `TestClient` | `httpx.AsyncClient` |
|---|---|---|
| Test function | Normal `def` | `async def` (+ pytest-asyncio) |
| Call style | `client.get(...)` | `await ac.get(...)` |
| Setup | `TestClient(app)` | `AsyncClient(transport=ASGITransport(app=app))` |
| Runs the app | In-process | In-process |
| Best for | Most endpoint tests | Async-specific tests, `await` in test |
| Simplicity | Simplest | A bit more setup |

Both are **in-process** — no real HTTP, no `uvicorn`, blazing fast. Neither hits the network.

---

## 8. Organizing Tests

- Put tests in a `tests/` folder or `test_*.py` files next to your code.
- One test file per module/router is a common convention (`test_auth.py`, `test_items.py`).
- Name tests **descriptively**: `test_login_with_wrong_password_returns_401` reads like a spec.
- Keep tests **independent** — each should pass on its own, in any order, without relying on another test's leftovers. (Lesson 42 covers test databases and fixtures for clean isolation.)

```
project/
├── main.py
├── tests/
│   ├── test_auth.py
│   ├── test_items.py
│   └── ...
└── pytest.ini
```

> 🔑 Independent, descriptively-named tests are the goal. A test that only passes when run after another is a **flaky** test — the bane of test suites.

---

## 9. Real-World Use Case — Confidence to Ship

You've built the Phase 4 auction API. Before every deploy you want to know: does register→login→place-bid still work? Is a bid below the current price still rejected with `409`? Can a non-seller still not create auctions?

A `pytest` suite answers all of that in **two seconds**, automatically, every time. Instead of manually clicking through `/docs` and hoping, you run `pytest` and see `47 passed`. That's the difference between "I think it works" and "I know it works" — and it's why every professional backend has a test suite.

---

## 10. Mini Task

This lesson ships a small app plus real test files.

1. Install: `pip install fastapi uvicorn httpx pytest pytest-asyncio`
2. Run the tests:
   ```bash
   pytest -v
   ```
   Watch every test pass, each named for the behavior it checks.
3. Read `test_main.py` (TestClient) and `test_async.py` (`httpx.AsyncClient`) side by side.
4. **Make a test fail on purpose:** change an expected status code in a test and re-run — see how pytest reports the mismatch.
5. **Break the app on purpose:** change `main.py` so an endpoint returns the wrong thing, run `pytest`, and watch the relevant test catch it. Revert.
6. **Experiment:**
   - Add a test for a 404 path and a 422 validation path.
   - Add an async test that posts an item and asserts the response.
   - Run `pytest -k "create"` to run only creation tests.
7. **Bonus:** Add a test that exercises the lifespan (`with TestClient(app) as client:`) and asserts an endpoint that depends on startup state.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Test file/function not named `test_*` | pytest won't discover it; follow the naming. |
| Forgetting `with TestClient(app)` for lifespan apps | Startup never runs; use the context manager. |
| Async test without `pytest-asyncio` | Install it and set `asyncio_mode = auto` (or decorate). |
| Tests that depend on each other's order | Make each test independent and self-contained. |
| Only testing the happy path | Test 404/409/422 and auth failures too. |
| Using a real running server / network | `TestClient`/`AsyncClient` call the app in-process — no server needed. |
| Asserting on huge response blobs | Assert the specific fields that matter. |

---

## 12. Key Takeaways

- **Automated tests** replace manual `/docs` clicking with a fast, repeatable safety net and living documentation.
- **`pytest`**: functions named `test_*` in `test_*.py`, plain `assert`, auto-discovery; run with `pytest -v`.
- Structure tests as **Arrange → Act → Assert**, one behavior per test.
- **`TestClient(app)`** calls your FastAPI app **in-process** (no server); assert on `status_code`, `json()`, `headers`.
- Test the **whole contract** — success, `404`, `409`, `422`, auth failures.
- Use **`with TestClient(app) as client:`** to trigger **lifespan** startup/shutdown.
- **`httpx.AsyncClient` + `ASGITransport`** (with `pytest-asyncio`) tests apps the async way when you need to `await` in the test.
- Keep tests **independent** and **descriptively named**.

---

## ➡️ Next Lesson

**Lesson 41 — Testing Endpoints**
- Testing GET/POST with data and auth headers
- Overriding dependencies with `app.dependency_overrides`
- Mocking external calls and testing protected routes
