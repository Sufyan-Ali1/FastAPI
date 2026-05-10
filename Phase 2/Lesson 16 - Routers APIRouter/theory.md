# Lesson 16 — Routers (APIRouter)

> **Goal of this lesson:** Break a monolithic `main.py` into clean, maintainable modules using `APIRouter`. This is the structural foundation every real FastAPI project is built on.

---

## 1. The Problem with One Big `main.py`

At 50+ endpoints, a single file becomes impossible to navigate:

```
main.py — 1200 lines
  GET  /users
  POST /users
  GET  /users/{id}
  PUT  /users/{id}
  DELETE /users/{id}
  GET  /products
  POST /products
  ... 45 more endpoints ...
```

Every developer touches the same file. Merge conflicts. No clear ownership. No way to test one feature in isolation.

**Solution:** split by resource or feature into separate router files.

---

## 2. `APIRouter` — The Building Block

```python
# routers/users.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
def list_users(): ...

@router.post("/users")
def create_user(): ...
```

`APIRouter` works exactly like `app` — same decorators, same `Depends()`, same `response_model`. The only difference: it doesn't run standalone. You include it into `app`.

---

## 3. Including a Router in `main.py`

```python
# main.py
from fastapi import FastAPI
from routers import users, products

app = FastAPI()

app.include_router(users.router)
app.include_router(products.router)
```

All routes defined on `users.router` and `products.router` are now registered on `app`.

---

## 4. Prefix and Tags

Instead of writing `/users` in every route, set it once on `include_router`:

```python
# routers/users.py
router = APIRouter()

@router.get("/")         # just "/"
def list_users(): ...

@router.get("/{user_id}")
def get_user(user_id: int): ...
```

```python
# main.py
app.include_router(
    users.router,
    prefix="/users",        # prepends /users to every route
    tags=["Users"],         # groups them in Swagger UI
)
```

Result:
- `GET /users/`
- `GET /users/{user_id}`
- All appear under the "Users" section in `/docs`

You can also set prefix/tags on the router itself — whichever style you prefer:

```python
# routers/users.py  — self-contained prefix
router = APIRouter(prefix="/users", tags=["Users"])
```

---

## 5. Router-Level Dependencies

Apply a dependency to every route in a router at once:

```python
from fastapi import Depends
from dependencies import require_auth

# Option A — on include_router (in main.py)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_auth)],
)

# Option B — on the router itself
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_auth)],
)
```

Every single route in that router now requires auth — zero per-endpoint boilerplate.

---

## 6. Default Response Model and Status Code

Set defaults for the whole router:

```python
router = APIRouter(
    prefix="/items",
    tags=["Items"],
    responses={
        404: {"description": "Item not found"},
        401: {"description": "Not authenticated"},
    },
)
```

These extra responses appear in the Swagger docs for every endpoint in the router.

---

## 7. Production Folder Structure

The pattern used in real FastAPI projects:

```
app/
├── main.py              ← creates FastAPI(), includes all routers
├── dependencies.py      ← shared Depends() functions
├── models.py            ← Pydantic models (or split per resource)
├── database.py          ← DB session setup
└── routers/
    ├── __init__.py
    ├── users.py         ← /users routes
    ├── products.py      ← /products routes
    └── admin.py         ← /admin routes (protected)
```

`main.py` becomes very short — its only job is to assemble the pieces.

---

## 8. Nested Routers

Routers can include other routers for hierarchical APIs:

```python
# routers/admin.py
from fastapi import APIRouter
from routers.admin_users import router as admin_users_router
from routers.admin_items import router as admin_items_router

router = APIRouter(prefix="/admin", tags=["Admin"])
router.include_router(admin_users_router, prefix="/users")
router.include_router(admin_items_router, prefix="/items")
```

Result:
- `GET /admin/users`
- `GET /admin/items`

```python
# main.py
app.include_router(router)  # everything under /admin is included
```

---

## 9. Overriding at Each Level

You can set prefix, tags, and dependencies at three levels. They compose:

```python
# router definition
router = APIRouter(prefix="/users", tags=["Users"])

# include_router in main.py — adds more tags or dependencies
app.include_router(
    router,
    tags=["Public"],         # merged with router's own tags
    dependencies=[Depends(require_api_key)],
)
```

---

## 10. Real-World Example — The Shape of This Lesson

This lesson's files look like:

```
Lesson 16/
├── main.py              ← app setup + router registration
├── dependencies.py      ← shared auth + pagination deps
├── models.py            ← Pydantic models
└── routers/
    ├── __init__.py
    ├── users.py         ← GET/POST/PATCH/DELETE /users
    ├── items.py         ← GET/POST/DELETE /items
    └── admin.py         ← /admin routes (protected)
```

`main.py` is under 40 lines. Each router file focuses on one resource.

---

## 11. Mini Task

1. Run: `uvicorn main:app --reload`
2. Open `/docs` — notice the endpoints are grouped under "Users", "Items", and "Admin" sections.
3. Try:
   - `GET /users` → public
   - `GET /admin/stats?token=admin` → admin only
   - `GET /admin/stats?token=user` → 403
4. **Bonus:** Add a new router `routers/orders.py` with:
   - `POST /orders` (create an order)
   - `GET /orders/{id}` (get one order)
   Include it in `main.py` with prefix `/orders` and tag "Orders".

---

## 12. Key Takeaways

- `APIRouter` is a mini `app` — same decorators, same `Depends()`.
- Include it with `app.include_router(router, prefix=..., tags=...)`.
- `prefix` avoids repeating the resource name in every route.
- `tags` groups routes in Swagger UI.
- `dependencies=[Depends(...)]` on a router = auth for all its routes.
- Keep `main.py` short — just app creation + router registration.
- Use a `routers/` subfolder with one file per resource.

---

## ➡️ Next Lesson

**Lesson 17 — Form Data & File Uploads**
- `Form()` for HTML form fields
- `UploadFile` for single and multiple file uploads
- Reading file contents
- Combining forms and files
