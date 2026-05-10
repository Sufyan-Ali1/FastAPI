# Lesson 5 — Query Parameters

> **Goal of this lesson:** Learn how to accept **optional inputs** through the URL using query parameters — for filtering, sorting, pagination, and search.

---

## 1. What is a query parameter?

A **query parameter** is a key–value pair that appears in the URL **after the `?`**.

```
        path                  query string
    ┌───────────────┐ ┌──────────────────────────┐
GET /products/laptops?color=red&page=2&sort=price
                      └───────┘ └────┘ └─────────┘
                       param 1 param 2  param 3
```

- Multiple params are separated by `&`
- Each is a `key=value` pair
- They are **always strings** when they arrive (FastAPI converts them based on type hints)

---

## 2. Why use query parameters?

Use them when the value is **optional** or describes **how** to fetch the data, not **which specific resource** you want.

| Need | Type | Example |
|------|------|---------|
| Identify a specific resource | Path param | `/users/42` |
| Filter, sort, paginate, search | **Query param** | `/users?role=admin&page=2` |

> 🔑 **Path = which resource. Query = how / which subset.**

Real examples you've seen 1,000 times:
- `https://google.com/search?q=fastapi`
- `https://youtube.com/results?search_query=python`
- `https://github.com/issues?state=open&label=bug`

---

## 3. How FastAPI detects query parameters

The rule is simple:

> **Any function parameter that is NOT in the URL path becomes a query parameter automatically.**

```python
@app.get("/products")
def list_products(category: str, page: int = 1):
    # category & page are NOT in the URL path
    # → FastAPI treats them as query params
    return {"category": category, "page": page}
```

Try:
- `/products?category=shoes&page=2` ✅
- `/products?category=shoes` ✅ (page defaults to 1)
- `/products` ❌ 422 — `category` is required

---

## 4. Required vs optional query parameters

The rule is **the same as Python defaults**:

```python
def list_products(
    category: str,            # NO default → REQUIRED
    page: int = 1,            # has default → optional
    sort: str | None = None,  # default None → optional, can be missing
):
    ...
```

| Declaration | Required? | Behavior |
|-------------|-----------|----------|
| `category: str` | ✅ Yes | Must be in the URL |
| `page: int = 1` | ❌ No | Defaults to 1 |
| `sort: str | None = None` | ❌ No | If missing → `None` |
| `active: bool = False` | ❌ No | Defaults to False |

---

## 5. Type conversion (just like path params)

```python
@app.get("/items")
def list_items(limit: int = 10, in_stock: bool = True, price: float = 0.0):
    return {"limit": limit, "in_stock": in_stock, "price": price}
```

URL: `/items?limit=5&in_stock=false&price=19.99`
→ FastAPI converts `"5"` → `5`, `"false"` → `False`, `"19.99"` → `19.99`.

For `bool` values, FastAPI accepts: `1`, `true`, `True`, `yes`, `on` (truthy) and `0`, `false`, `False`, `no`, `off` (falsy).

---

## 6. Validation with `Query()`

Just like `Path()` for path params, FastAPI gives you `Query()` for query params:

```python
from fastapi import FastAPI, Query

app = FastAPI()

@app.get("/search")
def search(
    q: str = Query(
        ...,                # required
        min_length=3,
        max_length=50,
        title="Search term",
        description="Text to search for",
    ),
    page: int = Query(1, ge=1, le=1000),
):
    return {"q": q, "page": page}
```

Common `Query()` validators:

| Param | Meaning | Works on |
|-------|---------|----------|
| `min_length` / `max_length` | string length | str |
| `pattern` | regex (e.g. `^[A-Z]+$`) | str |
| `gt` / `ge` / `lt` / `le` | numeric bounds | int, float |
| `title` / `description` | docs metadata | all |
| `deprecated=True` | marks param as deprecated in docs | all |
| `include_in_schema=False` | hide from Swagger UI | all |

Just like before, validation failure → **422 error**, function never runs.

---

## 7. Optional with no default → use `None`

```python
@app.get("/users")
def list_users(role: str | None = None):
    if role:
        return {"filter": role}
    return {"filter": "everyone"}
```

- `/users` → `role = None`
- `/users?role=admin` → `role = "admin"`

`str | None = None` is the modern Python way (Python 3.10+).
Older syntax: `Optional[str] = None` from `typing`.

---

## 8. Lists / multiple values for one parameter

URL: `/items?tag=python&tag=fastapi&tag=async`

To accept this, declare the param as a **list**:

```python
from typing import Annotated
from fastapi import Query

@app.get("/items")
def list_items(tags: Annotated[list[str] | None, Query()] = None):
    return {"tags": tags}
```

→ `tags = ["python", "fastapi", "async"]`

> 💡 `Annotated[...]` is the modern FastAPI style for advanced parameters.
> You'll see it everywhere in real codebases. We'll use it more later.

---

## 9. Combining path + query parameters

You can mix them freely:

```python
@app.get("/users/{user_id}/posts")
def list_user_posts(
    user_id: int,                      # path param (in URL)
    published: bool = True,            # query param (?published=...)
    limit: int = 10,                   # query param (?limit=...)
):
    return {"user_id": user_id, "published": published, "limit": limit}
```

URL: `/users/5/posts?published=false&limit=20`
- `user_id = 5` (from path)
- `published = False` (from query)
- `limit = 20` (from query)

This is the standard CRUD-with-filters pattern — every real REST API does this.

---

## 10. Path vs Query — quick comparison

| | Path Parameter | Query Parameter |
|---|----------------|-----------------|
| Position in URL | Before `?` | After `?` |
| Syntax | `/users/{id}` | `/users?role=admin` |
| Required by default? | ✅ Always required | ❌ Only if no default |
| Best for | Identifying ONE resource | Filtering / sorting / paging / search |
| Example | `/posts/42` | `/posts?author=john&page=2` |
| Validator | `Path()` | `Query()` |

---

## 11. Real-World Use Case

Almost every public API uses query parameters for **filtering, sorting, pagination, and search**:

```
GET /products?category=shoes&min_price=20&max_price=100&sort=price&page=2

GET /github.com/repos/openai/gpt/issues?state=open&labels=bug&per_page=50

GET /api/users?search=ali&role=admin&active=true&page=1&limit=20
```

Pattern you'll write hundreds of times in real backends:

```python
@app.get("/users")
def list_users(
    search: str | None = None,
    role: str | None = None,
    active: bool = True,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    ...
```

---

## 12. Mini Task

Open `main.py` in this lesson folder and:

1. Run: `uvicorn main:app --reload`
2. Test in `/docs`:
   - `/search?q=fa` → 422 (too short, min_length=3)
   - `/search?q=fastapi` → ✅ works
   - `/items?limit=5&in_stock=false` → returns the values
   - `/users` → returns "everyone"
   - `/users?role=admin` → returns the role
   - `/items-by-tags?tag=python&tag=fastapi` → returns the list
   - `/users/5/posts?published=false&limit=20` → mix of path + query
3. **Bonus:** Add an endpoint `/products` with these query params:
   - `category` (required, str)
   - `min_price` (optional, float, ≥ 0)
   - `max_price` (optional, float, ≤ 100000)
   - `page` (default 1, ≥ 1)

---

## 13. Key Takeaways

- Query params live **after `?`** in the URL: `/path?key=value`.
- Any function arg **not in the path** becomes a query param.
- **No default → required.** **Has default → optional.**
- Use `Query()` for length, regex, numeric, and docs metadata.
- Use `list[str]` (with `Query()`) for multi-value params.
- **Path = which resource. Query = how / which subset.**

---

## ➡️ Next Lesson

**Lesson 6 — Request Body with Pydantic Models**
- Replacing `dict` with proper `BaseModel`
- Field types & nested models
- `Field()` validation
- Why this is FastAPI's killer feature
