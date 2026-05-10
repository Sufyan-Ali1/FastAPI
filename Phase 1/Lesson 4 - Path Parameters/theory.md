# Lesson 4 — Path Parameters

> **Goal of this lesson:** Learn how to capture **dynamic values from the URL** (like `/users/42`), convert them to the right type, validate them, and avoid common routing mistakes.

---

## 1. What is a path parameter?

A **path parameter** is a part of the URL that **changes** depending on what the client wants.

Look at this URL:
```
/users/42
```

Here `42` is not a fixed string — it's a **variable** that identifies which user we want.
We say that `42` is a **path parameter** named `user_id`.

In FastAPI, you declare it with **curly braces** in the route:

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}
```

Now:
- `GET /users/42` → `user_id = 42`
- `GET /users/100` → `user_id = 100`
- `GET /users/abc` → ❌ FastAPI returns 422 error (because `abc` is not an int)

---

## 2. Why path parameters?

Without them, you'd need a separate endpoint for every single user. Imagine:

```python
@app.get("/users/1") ...
@app.get("/users/2") ...
@app.get("/users/3") ...
```

That's insane. Path parameters let **one endpoint handle infinite values**.

✅ Use a path parameter when the value **identifies a specific resource**:
- `/products/15` → product 15
- `/articles/python-tutorial` → article with that slug
- `/orders/2024/06/123` → order from June 2024

---

## 3. How does FastAPI handle them internally?

When a request like `GET /users/42` arrives:

```
1. URL pattern in code:  /users/{user_id}
2. URL from client:      /users/42
3. FastAPI extracts:     user_id = "42"   (always a string at first)
4. FastAPI looks at the function signature: user_id: int
5. FastAPI converts:     "42" → 42 (int)
6. If conversion fails → automatic 422 validation error
7. The function runs with user_id = 42
```

> 🔑 The **type hint** in the function signature drives **automatic conversion + validation**.

---

## 4. Type conversion examples

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):       # /users/42  → 42 (int)
    return {"user_id": user_id}

@app.get("/products/{name}")
def get_product(name: str):       # /products/laptop → "laptop"
    return {"name": name}

@app.get("/scores/{score}")
def get_score(score: float):      # /scores/3.14 → 3.14 (float)
    return {"score": score}

@app.get("/active/{flag}")
def is_active(flag: bool):        # /active/true → True (bool)
    return {"flag": flag}
```

Supported types: `int`, `float`, `str`, `bool`, `UUID`, `datetime`, `Enum`, …

---

## 5. Validation with `Path()`

Sometimes you want **stricter rules** — e.g., "user_id must be ≥ 1 and ≤ 1000".

For that, use `Path()` from FastAPI:

```python
from fastapi import FastAPI, Path

@app.get("/users/{user_id}")
def get_user(
    user_id: int = Path(
        ...,                # `...` means required
        ge=1,               # greater than or equal to 1
        le=1000,            # less than or equal to 1000
        title="User ID",
        description="The ID of the user (1–1000)",
    )
):
    return {"user_id": user_id}
```

Common `Path()` validators:

| Param | Meaning | Works on |
|-------|---------|----------|
| `gt` | greater than | numbers |
| `ge` | greater or equal | numbers |
| `lt` | less than | numbers |
| `le` | less or equal | numbers |
| `min_length` | minimum string length | str |
| `max_length` | maximum string length | str |
| `pattern` | regex pattern | str |
| `title` | docs title | all |
| `description` | docs description | all |

If validation fails → FastAPI returns **422 Unprocessable Entity** with a clear error message. No manual checks needed.

---

## 6. Multiple path parameters

You can have as many as you want, in any order:

```python
@app.get("/users/{user_id}/posts/{post_id}")
def get_user_post(user_id: int, post_id: int):
    return {"user_id": user_id, "post_id": post_id}
```

The URL `GET /users/42/posts/7` → `user_id=42, post_id=7`.

This is the standard REST way to express **"a post that belongs to a user"**.

---

## 7. Route order matters! ⚠️

This is one of the most common bugs beginners hit.

FastAPI matches routes **in the order you define them, top to bottom**.

❌ **Wrong order** — `/items/me` will never run:
```python
@app.get("/items/{item_id}")    # this catches EVERYTHING
def get_item(item_id: str):
    return {"item_id": item_id}

@app.get("/items/me")           # never reached!
def read_me():
    return {"name": "current user"}
```

When you visit `/items/me`, FastAPI matches the **first** route and treats `"me"` as `item_id`.

✅ **Correct order** — specific routes go FIRST:
```python
@app.get("/items/me")           # specific FIRST
def read_me():
    return {"name": "current user"}

@app.get("/items/{item_id}")    # generic LAST
def get_item(item_id: str):
    return {"item_id": item_id}
```

> 🔑 **Rule of thumb:** static (fixed) paths must be declared **before** dynamic (parameterized) paths that could match them.

This is exactly why your `main.py` from Lesson 3 places `/items/count` **before** `/items/{item_id}`.

---

## 8. Predefined values with `Enum`

Sometimes a path parameter must be one of a fixed set of values (e.g., `small`, `medium`, `large`).
Use a Python `Enum`:

```python
from enum import Enum
from fastapi import FastAPI

class Size(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"

app = FastAPI()

@app.get("/sizes/{size}")
def get_size(size: Size):
    return {"size": size, "label": size.value.upper()}
```

- `/sizes/small` ✅ works
- `/sizes/huge` ❌ 422 error
- Swagger UI even shows a **dropdown** of valid values automatically.

---

## 9. Path containing slashes (`:path` converter)

What if the parameter itself contains `/` (like a file path)?
Use the `:path` converter:

```python
@app.get("/files/{file_path:path}")
def read_file(file_path: str):
    return {"file_path": file_path}
```

- `/files/home/user/notes.txt` → `file_path = "home/user/notes.txt"`

Without `:path`, the slashes would be treated as separators and the route wouldn't match.

---

## 10. Real-World Use Case

Almost every REST API uses path parameters everywhere:

| URL | Meaning |
|-----|---------|
| `GET /users/{id}` | Get one user |
| `GET /users/{id}/orders` | All orders of a user |
| `GET /orders/{id}/items` | Items in a specific order |
| `DELETE /products/{slug}` | Delete by slug |
| `GET /repos/{owner}/{repo}/issues/{number}` | GitHub-style nesting |

> 🔥 In real projects, path parameters are how you point to **a specific resource**.
> Query parameters (next lesson) are for **filtering or options**.

---

## 11. Mini Task

Open `main.py` in this lesson folder and:

1. Run it: `uvicorn main:app --reload`
2. Test in `/docs`:
   - `/users/5` → should work
   - `/users/abc` → should fail with 422
   - `/users/0` → should fail (we set `ge=1`)
   - `/users/me` → should return the "current user" route, **not** the generic one
   - `/sizes/small` → ok
   - `/sizes/extra-large` → 422 (not in enum)
   - `/users/3/posts/9` → should return both IDs
3. **Bonus:** Add an endpoint `/products/{product_id}` where `product_id` is `int`, must be between **100 and 9999**.

---

## 12. Key Takeaways

- Path parameters are **variables** in the URL declared with `{name}`.
- The **type hint** drives automatic conversion + validation.
- `Path(...)` adds extra rules: `ge`, `le`, `min_length`, `pattern`, etc.
- **Route order matters** — put static paths before dynamic ones.
- Use `Enum` when only a fixed set of values is allowed.
- Use `{name:path}` when the value can contain slashes.

---

## ➡️ Next Lesson

**Lesson 5 — Query Parameters**
- Optional vs required query params
- Default values
- `Query()` validation (length, regex, lists)
- Difference between path and query parameters
