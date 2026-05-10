# Lesson 8 — Response Basics

> **Goal of this lesson:** Understand exactly **how FastAPI sends data back** to the client — JSON conversion, status codes, headers, and when to use `JSONResponse` vs returning a plain dict.

---

## 1. The Default Behavior

When you `return` something from an endpoint, FastAPI **automatically**:

1. Converts it to JSON
2. Sets `Content-Type: application/json`
3. Sends it with status code **200 OK**

```python
@app.get("/")
def root():
    return {"message": "hello"}
```

The client receives:
```
HTTP/1.1 200 OK
Content-Type: application/json

{"message":"hello"}
```

You did nothing — FastAPI did everything.

---

## 2. What Can You Return?

FastAPI knows how to serialize a wide range of Python types:

| You return | Sent as JSON |
|------------|--------------|
| `dict` | object `{...}` |
| `list` / `tuple` | array `[...]` |
| `str` | `"..."` |
| `int` / `float` | number |
| `bool` | `true` / `false` |
| `None` | `null` |
| **Pydantic model** | object (auto `.model_dump()`) |
| `datetime`, `date`, `UUID`, `Decimal` | ISO string / string |
| `Enum` | its `.value` |

```python
from datetime import datetime
from pydantic import BaseModel

class Post(BaseModel):
    title: str
    created_at: datetime

@app.get("/posts/1")
def get_post():
    return Post(title="Hello", created_at=datetime.now())
```

→ FastAPI runs `model_dump()`, converts `datetime` → ISO string, sends JSON.

---

## 3. Setting a Custom Status Code

By default, every response is **200 OK**. To change it, pass `status_code=` to the decorator:

```python
from fastapi import FastAPI, status

app = FastAPI()

@app.post("/items", status_code=201)
def create_item(name: str):
    return {"name": name}
```

The response is now `201 Created` — exactly what REST recommends for resource creation.

### Use the `status` module (recommended)

Hardcoded numbers like `201` work but are unclear. The `status` module gives you readable constants:

```python
from fastapi import status

@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(...): ...

@app.delete("/items/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(...): ...
```

### Common status codes

| Code | Meaning | Use when |
|------|---------|----------|
| **200** | OK | Default GET / PUT / PATCH success |
| **201** | Created | After successful POST that created something |
| **202** | Accepted | Request queued (will process later) |
| **204** | No Content | Successful DELETE / PUT with empty body |
| **400** | Bad Request | Malformed input you detected manually |
| **401** | Unauthorized | Missing/invalid auth |
| **403** | Forbidden | Authenticated but not allowed |
| **404** | Not Found | Resource doesn't exist |
| **409** | Conflict | Duplicate / conflicting state |
| **422** | Unprocessable Entity | Validation failed (FastAPI sends this automatically) |
| **500** | Internal Server Error | Bug / unhandled exception |

---

## 4. Returning a Pydantic Model

Just return the model — FastAPI handles the JSON conversion:

```python
class User(BaseModel):
    id: int
    name: str
    email: str

@app.get("/users/1")
def get_user() -> User:
    return User(id=1, name="Sufyan", email="x@y.com")
```

The `-> User` return type hint also helps your editor and Swagger UI. We'll use **`response_model=`** in Lesson 10 for even more control (filtering fields, exclude_none, etc.).

---

## 5. `JSONResponse` — When You Need Full Control

Returning a dict is **shorthand**. FastAPI internally wraps it in a `JSONResponse`. Sometimes you need to do that wrapping yourself — for example to set custom headers, set the status code dynamically, or return raw bytes.

```python
from fastapi.responses import JSONResponse

@app.get("/custom")
def custom():
    return JSONResponse(
        content={"message": "hi"},
        status_code=202,
        headers={"X-Custom-Header": "abc"},
    )
```

### When should you use `JSONResponse`?

| Situation | What to do |
|-----------|------------|
| Normal endpoint | **Return a dict / model.** That's it. |
| Need custom headers | Use `JSONResponse` (or use `Response` parameter — see §7) |
| Status code depends on logic | `JSONResponse(..., status_code=...)` |
| Return raw bytes / non-JSON | `Response(content=..., media_type=...)` |
| Stream large data | `StreamingResponse` (Lesson 32) |
| Send a file | `FileResponse` |

> 🔑 **Default to returning a dict / Pydantic model.** Reach for `JSONResponse` only when you actually need its features.

---

## 6. Returning Different Status Codes Conditionally

If you need to **return** a different status code depending on logic (e.g. created vs already-existed), there are two clean ways:

### Option A — `JSONResponse`
```python
from fastapi.responses import JSONResponse

@app.post("/users")
def create_user(name: str):
    if user_already_exists(name):
        return JSONResponse(
            content={"message": "User already exists"},
            status_code=409,
        )
    return JSONResponse(
        content={"message": "Created"},
        status_code=201,
    )
```

### Option B — inject `Response` and mutate it
```python
from fastapi import Response, status

@app.post("/users")
def create_user(name: str, response: Response):
    if user_already_exists(name):
        response.status_code = status.HTTP_409_CONFLICT
        return {"message": "User already exists"}
    response.status_code = status.HTTP_201_CREATED
    return {"message": "Created"}
```

Both are valid. Option B is shorter when you still want JSON. Option A is clearer when you want to change headers too.

---

## 7. Setting Headers and Cookies

### Headers via the injected `Response`
```python
from fastapi import Response

@app.get("/hello")
def hello(response: Response):
    response.headers["X-Powered-By"] = "FastAPI"
    return {"message": "hi"}
```

### Cookies
```python
@app.get("/login")
def login(response: Response):
    response.set_cookie(key="session_id", value="abc123", httponly=True)
    return {"ok": True}
```

We'll go deep on cookies & headers in **Lesson 18**. For now, just know it's possible without `JSONResponse`.

---

## 8. Returning `None` / Empty Body

For `204 No Content`, the body **must** be empty:

```python
from fastapi import status

@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    db.delete(item_id)
    # return nothing — FastAPI will send an empty body
```

Even if you `return None`, FastAPI will respect the `204` and send no body.

---

## 9. Raising Errors with `HTTPException`

When something goes wrong, **don't** return an error dict manually. Use `HTTPException` — it handles status code, headers, and the JSON shape for you:

```python
from fastapi import HTTPException, status

@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = db.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
```

The client receives:
```
HTTP/1.1 404 Not Found
Content-Type: application/json

{"detail": "User not found"}
```

We'll go deeper on exceptions in **Lesson 12**.

---

## 10. Real-World Use Case — A Clean POST

```python
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI()
db: dict[int, dict] = {}

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)

class ItemOut(BaseModel):
    id: int
    name: str
    price: float

@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate) -> ItemOut:
    if any(i["name"] == item.name for i in db.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item with that name already exists",
        )
    new_id = len(db) + 1
    saved = {"id": new_id, **item.model_dump()}
    db[new_id] = saved
    return saved
```

Notice:
- `status_code=201` declared once, on the decorator
- Validation comes from Pydantic — automatic 422
- Conflict raised cleanly with `HTTPException`
- Return type is a clean Pydantic model

This is the **standard FastAPI POST pattern** you'll write hundreds of times.

---

## 11. Mini Task

Open `main.py`:

1. Run: `uvicorn main:app --reload`
2. In `/docs`:
   - **POST `/items`** — note the **201** status code
   - **DELETE `/items/{id}`** — note the **204** with empty body
   - **GET `/items/{id}`** — try `0` to see a clean **404**
   - **GET `/with-headers`** — inspect the `X-Powered-By` header in the network tab
   - **GET `/conditional`** — try `?lucky=true` (200) vs `?lucky=false` (418)
3. **Bonus:** Add a **PATCH `/items/{id}`** that:
   - Returns **200** on success
   - Returns **404** via `HTTPException` if the id doesn't exist
   - Sets a custom header `X-Patched-By: fastapi-learner`

---

## 12. Key Takeaways

- Return a dict / Pydantic model — FastAPI converts to JSON automatically.
- Set the success status with `status_code=` on the decorator (use `status.HTTP_*`).
- Use `HTTPException` for errors, not manual error dicts.
- Reach for `JSONResponse` only when you need custom headers, dynamic status, or non-JSON output.
- For `204`, return nothing — the body must be empty.

---

## ➡️ Next Lesson

**Lesson 9 — Pydantic Deep Dive**
- Custom validators (`@field_validator`, `@model_validator`)
- `model_config`
- Pydantic v1 vs v2
- Strict mode, aliases, computed fields
