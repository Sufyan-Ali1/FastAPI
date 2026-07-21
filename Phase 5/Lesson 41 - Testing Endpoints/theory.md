# Lesson 41 — Testing Endpoints

> **Goal of this lesson:** Test **realistic** endpoints — ones that take data, require **authentication**, enforce **roles**, and call **external services**. The star technique is **`app.dependency_overrides`**: swapping a dependency (auth, DB, an email sender) for a fake **in tests**, so you can test protected routes without real logins and without hitting real external systems.
>
> Builds on Lesson 40. `main.py` is an auth-protected app; the test files show both testing with a **real token** and **overriding** the auth/service dependencies.

---

## 1. Where We Are

Lesson 40 tested simple, open endpoints. Real APIs have **protected** endpoints (need a token), **role checks** (admin only), and **dependencies** on databases and external services (email, payment, another API). Testing those raises two questions:

1. How do I test an endpoint that requires `Depends(get_current_user)`?
2. How do I test code that calls a real database or emails a real user — **without** doing either for real?

The answer to both is FastAPI's **dependency override** system.

---

## 2. Testing Endpoints With Data

First, the straightforward part — endpoints that take query params, bodies, and headers. `TestClient` mirrors an HTTP client:

```python
client.get("/items", params={"q": "wireless", "limit": 5})     # query params
client.post("/items", json={"name": "Widget", "price": 9.99})  # JSON body
client.post("/login", data={"username": "a", "password": "b"}) # form data
client.get("/me", headers={"Authorization": "Bearer <token>"}) # headers
```

| You send | `TestClient` argument |
|---|---|
| Query params | `params={...}` |
| JSON body | `json={...}` |
| Form data (OAuth2 login) | `data={...}` |
| Headers | `headers={...}` |

> 🔑 Login (OAuth2 password flow) uses **`data=`** (form), not `json=`. A very common test bug is sending the login as JSON and getting a 422.

---

## 3. Two Ways to Test Protected Endpoints

Say `/me` needs a valid token. You have two legitimate strategies:

### Approach A — Use a real token (integration-style)

Actually log in through the API, grab the token, and send it:

```python
def test_me_with_real_token():
    # log in to get a real token
    tokens = client.post("/login", data={"username": "alice", "password": "pw"}).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = client.get("/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == "alice"
```

- ✅ Tests the **real auth flow** end to end (register → login → protected route).
- ❌ Every protected test must log in first (slower, repetitive).

### Approach B — Override the auth dependency (unit-style)

Replace `get_current_user` with a function that just returns a fake user — **no login needed**:

```python
def fake_current_user():
    return User(id=1, username="tester", role="member")

app.dependency_overrides[get_current_user] = fake_current_user

def test_me_overridden():
    response = client.get("/me")          # no token needed!
    assert response.json()["username"] == "tester"
```

- ✅ Fast, no login boilerplate, and you control exactly who the "current user" is (member, admin, disabled…).
- ❌ Skips the real auth flow (so also keep a few Approach-A tests for the auth itself).

> 🔑 Use **Approach A** to test that auth *works*; use **Approach B** (overrides) to test everything *behind* auth without re-logging-in every time. A good suite has both.

---

## 4. `app.dependency_overrides` — The Core Technique

FastAPI keeps a dictionary, **`app.dependency_overrides`**, mapping a real dependency → a replacement. During a request, if a dependency is in that dict, FastAPI calls the **override** instead of the real one.

```python
app.dependency_overrides[real_dependency] = fake_dependency   # install
del app.dependency_overrides[real_dependency]                 # remove
app.dependency_overrides.clear()                              # remove all
```

- The **key** is the actual dependency function/object you used in `Depends(...)`.
- The **value** is any callable with a compatible signature (it can even take `Depends` of its own).
- It affects **only** requests made after it's installed — perfect for tests.

This one mechanism lets you swap out **auth, the database session, or any external service** for a test double.

> 🔑 `app.dependency_overrides[dep] = fake` tells FastAPI "for now, call `fake` wherever `dep` was injected." It's the single most important testing tool in FastAPI.

---

## 5. Overriding External Services (Mocking)

The other big use: don't call the real email/payment/3rd-party service in tests. Inject a **fake** and assert how it was used.

```python
# real dependency provides an email sender
def get_email_service() -> EmailService:
    return RealEmailService()   # would actually send email

# in the test, a fake that just records calls
class FakeEmailService:
    def __init__(self): self.sent = []
    def send(self, to, subject): self.sent.append((to, subject))

def test_signup_sends_welcome_email():
    fake = FakeEmailService()
    app.dependency_overrides[get_email_service] = lambda: fake

    client.post("/signup", json={"email": "a@b.com", ...})

    assert len(fake.sent) == 1                      # the endpoint tried to send
    assert fake.sent[0][0] == "a@b.com"
```

Now the test is **fast, deterministic, and offline** — no real email leaves your machine — yet you still verify the endpoint *attempted* the right action.

| Why override external deps | |
|---|---|
| **Speed** | No network round trips |
| **Determinism** | No flaky external failures |
| **Safety** | No real emails/charges/data changes |
| **Assertability** | Inspect exactly what your code tried to do |

---

## 6. The Golden Rule — Always Clean Up Overrides

Overrides live on the **app object**, so they **persist across tests** unless you remove them. Forgetting to clean up means one test's fake leaks into the next → mysterious failures. Always reset:

```python
def test_something():
    app.dependency_overrides[get_current_user] = fake_user
    try:
        ...
    finally:
        app.dependency_overrides.clear()     # ALWAYS clean up
```

Better: do it once in a **fixture** (next section) so you never forget.

> 🔑 Overrides are global to the app and **sticky**. Clear them after each test (ideally via a fixture) or tests will contaminate each other — a classic source of "passes alone, fails in the suite" bugs.

---

## 7. pytest Fixtures — Reusable Setup/Teardown

A **fixture** is a function that provides setup (and optional teardown) to tests. Declare it with `@pytest.fixture`; a test **requests** it by naming it as a parameter. Common fixtures: a `client`, and one that auto-clears overrides.

```python
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    with TestClient(app) as c:      # setup (runs lifespan)
        yield c                     # the test runs here
    app.dependency_overrides.clear()  # teardown: always clean overrides

def test_root(client):              # 'client' is injected by the fixture
    assert client.get("/").status_code == 200
```

- Code **before `yield`** = setup; code **after `yield`** = teardown (runs even if the test fails).
- Put shared fixtures in **`conftest.py`** and pytest makes them available to every test file automatically — no import needed.

> 🔑 A `client` fixture with `yield` gives you clean setup/teardown and guarantees overrides are cleared after **every** test. Fixtures are how professional test suites stay isolated. (Lesson 42 uses fixtures for a fresh test database per test.)

---

## 8. Testing Authorization (RBAC)

With overrides you can easily test every role path. Override `get_current_user` to return users of different roles and assert the outcome:

```python
def test_admin_route_forbidden_for_member(client):
    app.dependency_overrides[get_current_user] = lambda: member_user
    assert client.get("/admin/stats").status_code == 403

def test_admin_route_ok_for_admin(client):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    assert client.get("/admin/stats").status_code == 200

def test_protected_route_without_token_returns_401(client):
    # no override -> the real dependency runs -> no token -> 401
    assert client.get("/me").status_code == 401
```

You get all three cases — `401` (no auth), `403` (wrong role), `200` (allowed) — cheaply and clearly.

> 🔑 Overriding the current user lets you test **every authorization branch** (`401`/`403`/`200`) without minting real tokens for each role.

---

## 9. Real-World Use Case — Testing the Auction API

Testing the Phase 4 auction API's `POST /auctions` (sellers only) and `POST /auctions/{id}/bids`:

- A few **Approach-A** tests confirm the real login and token validation work.
- The bulk of tests **override `get_current_user`** to be a seller, a bidder, or nobody — verifying sellers can create auctions (`201`), bidders can't (`403`), and anonymous callers get `401`.
- The email/notification service is **overridden with a fake**, so "outbid notification sent" is asserted without sending real emails.
- The whole suite runs in seconds, offline, deterministically — testing real behavior without real side effects.

---

## 10. Mini Task

This lesson ships an auth-protected app and tests using both approaches.

1. Install: `pip install fastapi uvicorn httpx pytest pytest-asyncio`
2. Run: `pytest -v` — see tests for real-token auth, overridden auth, RBAC, and a mocked service.
3. Read `conftest.py` (the `client` fixture that clears overrides) and `test_endpoints.py`.
4. **Experiment:**
   - Add a test that overrides `get_current_user` to a **disabled** user and asserts the expected error.
   - Add a test that a member is `403` on the admin route and an admin is `200`.
   - Remove the `app.dependency_overrides.clear()` from the fixture, add two tests that set different users, and watch them contaminate each other — then put it back.
5. **Bonus:** Override the notifier dependency and assert it was **not** called on a validation-failed request (the endpoint should reject before notifying).

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Not clearing overrides between tests | Clear in a fixture (`app.dependency_overrides.clear()`). |
| Sending login as `json=` | OAuth2 password flow uses `data=` (form). |
| Overriding the wrong callable | The key must be the exact function used in `Depends(...)`. |
| Only testing with overrides (never the real auth) | Keep a few real-token tests so auth itself is covered. |
| Calling real external services in tests | Override them with fakes; assert usage. |
| Forgetting `Authorization` header format | It's `Bearer <token>`. |
| Shared mutable state leaking between tests | Reset state / use fresh fixtures. |

---

## 12. Key Takeaways

- Send data in tests with `params=` (query), `json=` (body), `data=` (form/login), `headers=` (auth).
- Test protected routes two ways: **real token** (Approach A, tests auth itself) and **dependency override** (Approach B, tests behind auth).
- **`app.dependency_overrides[dep] = fake`** swaps any dependency — **auth, DB, external services** — for a test double.
- Override **external services** with fakes for speed, determinism, safety, and assertability.
- **Always clear overrides** after each test (they persist on the app) — ideally in a **fixture**.
- **pytest fixtures** (`@pytest.fixture` + `yield`, shared via `conftest.py`) provide reusable setup/teardown and keep tests isolated.
- Overriding the current user lets you test every **RBAC** branch (`401`/`403`/`200`) easily.

---

## ➡️ Next Lesson

**Lesson 42 — Database Testing**
- A separate test database (never test against production data)
- Fixtures for a fresh schema per test
- Transactions and rollbacks for fast test isolation
