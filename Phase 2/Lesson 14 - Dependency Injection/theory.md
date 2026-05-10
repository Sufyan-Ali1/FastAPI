# Lesson 14 — Dependency Injection

> **Goal of this lesson:** Master `Depends()` — FastAPI's most powerful feature. Extract shared logic (auth, DB sessions, pagination, permissions) into reusable dependencies that are automatically injected, cached per-request, and trivially testable.

---

## 1. The Problem DI Solves

Every real endpoint has repeated boilerplate:

```python
@app.get("/posts")
def list_posts(page: int = 1, limit: int = 10, token: str = Header(...)):
    user = verify_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    if page < 1 or limit > 100:
        raise HTTPException(400, "Bad pagination")
    # ... actual logic

@app.get("/comments")
def list_comments(page: int = 1, limit: int = 10, token: str = Header(...)):
    user = verify_token(token)              # same
    if not user:
        raise HTTPException(401, "...")    # same
    if page < 1 or limit > 100:           # same
        raise HTTPException(400, "...")    # same
    # ... actual logic
```

Every endpoint duplicates auth + pagination. With 50 endpoints, that's 50 copies to maintain. **Dependency Injection (DI) eliminates this.**

---

## 2. What `Depends()` Does

`Depends(callable)` tells FastAPI: *"call this function first, give me its return value, and handle any exceptions it raises."*

```python
from fastapi import Depends

def get_pagination(page: int = 1, limit: int = Query(10, le=100)):
    return {"page": page, "limit": limit}

@app.get("/posts")
def list_posts(pagination: dict = Depends(get_pagination)):
    return {"posts": [], **pagination}

@app.get("/comments")
def list_comments(pagination: dict = Depends(get_pagination)):
    return {"comments": [], **pagination}
```

`get_pagination` runs once per request, returns a dict, and FastAPI injects it as `pagination`. The query params `page` and `limit` still come from the URL — FastAPI resolves them automatically inside the dependency.

---

## 3. Dependencies Are Normal Functions

A dependency function looks exactly like an endpoint function — it can have:
- Path parameters
- Query parameters
- Body parameters
- Headers
- Cookies
- **Other dependencies** (sub-dependencies)

```python
from fastapi import Header, HTTPException, status

def require_auth(authorization: str = Header(...)):
    """Extracts and validates a Bearer token from the Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

@app.get("/me")
def get_profile(current_user = Depends(require_auth)):
    return current_user   # only runs if require_auth didn't raise
```

---

## 4. Sub-Dependencies

A dependency can itself depend on another dependency:

```python
def get_db():
    """Opens a DB connection and returns it."""
    db = open_db_connection()
    return db

def get_current_user(db = Depends(get_db), token: str = Query(...)):
    """Needs a DB connection to look up the user."""
    user = db.find_user_by_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

def require_admin(user = Depends(get_current_user)):
    """Needs the current user to check admin status."""
    if not user.is_admin:
        raise HTTPException(403, "Admin only")
    return user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, admin = Depends(require_admin)):
    """Three levels of dependencies, all resolved automatically."""
    db.delete(user_id)
```

FastAPI builds the full **dependency graph** and resolves it in the right order.

---

## 5. Dependency Caching

Within a single request, FastAPI calls each dependency **only once** — even if it appears in multiple places.

```python
def get_db():
    print("Opening DB")          # runs exactly once per request
    return Database()

def get_user(db = Depends(get_db)):   # uses the cached db instance
    ...

def log_request(db = Depends(get_db)):   # same cached db instance!
    ...

@app.get("/data")
def read_data(
    user = Depends(get_user),
    _    = Depends(log_request),
):
    # get_db() was called ONCE — both dependencies share the same db object
    ...
```

To **disable** caching (force a fresh call):

```python
Depends(get_db, use_cache=False)
```

---

## 6. Class-Based Dependencies

For dependencies with **configuration**, classes are cleaner than functions:

```python
class Paginator:
    def __init__(self, max_limit: int = 100):
        self.max_limit = max_limit
    
    def __call__(
        self,
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1),
    ) -> dict:
        if limit > self.max_limit:
            raise HTTPException(400, f"Limit cannot exceed {self.max_limit}")
        return {"page": page, "limit": limit, "offset": (page - 1) * limit}

# Create configured instances
standard_pagination = Paginator(max_limit=100)
admin_pagination    = Paginator(max_limit=1000)

@app.get("/posts")
def list_posts(pagination = Depends(standard_pagination)):
    return pagination

@app.get("/admin/posts")
def admin_list(pagination = Depends(admin_pagination)):
    return pagination
```

`Paginator(max_limit=100)` creates a *callable* object. `Depends(standard_pagination)` calls `__call__` on each request.

---

## 7. `yield` Dependencies — Setup and Teardown

For resources that need cleanup (DB sessions, file handles, locks), use `yield`:

```python
def get_db():
    db = SessionLocal()    # SETUP: open the connection
    try:
        yield db           # hand it to the endpoint
    finally:
        db.close()         # TEARDOWN: always runs, even if the endpoint raised

@app.post("/users")
def create_user(user: UserCreate, db = Depends(get_db)):
    # db is open here
    db.add(user)
    db.commit()
    return user
# db.close() runs automatically after the response is sent
```

**The flow:**
```
Request arrives
  → get_db() runs up to yield  (setup)
    → endpoint function runs
  → get_db() runs after yield  (teardown, in finally block)
Response sent
```

This is how **every real FastAPI app** manages database sessions.

---

## 8. Dependencies at Different Scopes

### On a single endpoint
```python
@app.get("/items", dependencies=[Depends(require_auth)])
def list_items(): ...
```
`dependencies=[...]` runs the dependency but discards its return value — useful for auth/permission checks only.

### On a router (Lesson 16)
```python
router = APIRouter(dependencies=[Depends(require_auth)])
# All routes in this router require auth
```

### On the whole app
```python
app = FastAPI(dependencies=[Depends(verify_api_key)])
# Every single endpoint requires the API key
```

---

## 9. Testing with Dependency Overrides

This is why DI is so powerful — you can **swap dependencies** in tests:

```python
# In tests
def fake_db():
    return TestDatabase()

app.dependency_overrides[get_db] = fake_db
# Now every endpoint uses the test DB instead of the real one

# After tests
app.dependency_overrides = {}
```

No monkey-patching, no mocks of internal modules. Just clean substitution.

---

## 10. Real-World Use Case — Auth + DB + Pagination

A complete pattern you'll use in every real API:

```python
# ---- dependencies.py ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: str = Header(..., alias="Authorization"),
    db = Depends(get_db),
):
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(401, "Invalid credentials")
    return user

def require_active(user = Depends(get_current_user)):
    if not user.is_active:
        raise HTTPException(403, "Account suspended")
    return user

class Paginator:
    def __call__(self, page: int = 1, limit: int = Query(20, le=100)):
        return {"skip": (page - 1) * limit, "limit": limit}

paginate = Paginator()

# ---- posts.py ----
@router.get("/posts")
def list_posts(
    pagination = Depends(paginate),
    user       = Depends(require_active),
    db         = Depends(get_db),
):
    posts = db.query(Post).offset(pagination["skip"]).limit(pagination["limit"]).all()
    return posts
```

Three dependencies, zero boilerplate in the endpoint.

---

## 11. Mini Task

Open `main.py`:

1. Run: `uvicorn main:app --reload`
2. In `/docs`:
   - **GET `/items`** without token → 401
   - **GET `/items`** with `token=user` → returns items
   - **DELETE `/items/1`** with `token=user` → 403 (not admin)
   - **DELETE `/items/1`** with `token=admin` → 204
   - **GET `/items?page=0`** → 422 (pagination validates ge=1)
   - **GET `/items?limit=200`** → 400 (Paginator max_limit=100)
3. **Bonus:** Create a dependency `require_owner(item_id: int, user = Depends(get_current_user))` that checks whether the current user owns the item. Use it on a `DELETE /my-items/{item_id}` endpoint.

---

## 12. Key Takeaways

- `Depends(fn)` injects a dependency's return value; exceptions propagate naturally.
- Dependencies can have all the same parameters as endpoints (path, query, body, headers).
- **Caching:** each dependency runs once per request by default.
- **Sub-dependencies:** FastAPI resolves the full graph automatically.
- **Class-based:** use `__call__` for configurable dependencies.
- **`yield`:** the cleanest way to manage setup/teardown (DB sessions, locks, files).
- **`dependencies=[...]`:** run a dep for side-effects (auth check) without injecting its value.
- **`app.dependency_overrides`:** makes testing trivial.

---

## ➡️ Next Lesson

**Lesson 15 — Middleware**
- What middleware is and when to use it vs dependencies
- Built-in middleware (CORS, GZip, TrustedHost)
- Writing custom middleware
- Request/response logging middleware
