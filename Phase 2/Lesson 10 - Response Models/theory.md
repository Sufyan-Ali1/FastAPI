# Lesson 10 — Response Models

> **Goal of this lesson:** Control exactly **what gets sent back** to the client. Hide sensitive fields, strip empty values, and declare separate input vs output shapes — all without writing a single manual filter.

---

## 1. The Problem Without `response_model`

Without it, **everything** in your return value goes to the client:

```python
class User(BaseModel):
    id: int
    email: str
    password_hash: str   # 🔴 should NEVER be sent out

@app.get("/users/1")
def get_user():
    return User(id=1, email="x@y.com", password_hash="$2b$...")
```

The client sees `password_hash`. That's a security bug.

**Option 1 — manually pop the field:** fragile, easy to forget.  
**Option 2 — `response_model=`:** FastAPI enforces it for you, always.

---

## 2. `response_model=` — The Declaration

Pass a Pydantic model to the decorator. FastAPI will:
1. Serialize the return value **through** that model
2. Strip any fields NOT in the model
3. Document the response shape in Swagger UI

```python
class UserOut(BaseModel):
    id: int
    email: str
    # password_hash is NOT here — it will be stripped

@app.get("/users/1", response_model=UserOut)
def get_user():
    # You can return a User with password_hash — it won't reach the client
    return {"id": 1, "email": "x@y.com", "password_hash": "$2b$..."}
```

The response the client receives:
```json
{ "id": 1, "email": "x@y.com" }
```

`password_hash` never made it out. FastAPI filtered it before serializing.

---

## 3. The Pattern: Separate Input & Output Models

The real-world pattern used in every production FastAPI app:

```
UserCreate  →  used for POST body (has password)
UserOut     →  used for response   (no password_hash)
UserDB      →  internal / DB shape (has password_hash)
```

```python
from pydantic import BaseModel, Field

# What the client sends when creating a user
class UserCreate(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    name: str

# What the client sees in the response
class UserOut(BaseModel):
    id: int
    email: str
    name: str

# What lives in the DB / internal code
class UserDB(UserCreate):
    id: int
    password_hash: str

@app.post("/users", response_model=UserOut, status_code=201)
def create_user(user: UserCreate):
    # Hash the password, save, then return — FastAPI filters to UserOut
    db_user = save_to_db(user)
    return db_user     # even if db_user has password_hash, client won't see it
```

---

## 4. `response_model_exclude_unset`

By default, optional fields with defaults are **always included** in the response, even if you didn't set them:

```python
class Item(BaseModel):
    id: int
    name: str
    description: str | None = None
    discount: float = 0.0

@app.get("/items/1", response_model=Item)
def get_item():
    return {"id": 1, "name": "Laptop"}
    # Response: {"id": 1, "name": "Laptop", "description": null, "discount": 0.0}
    # Those defaults are noisy — client gets fields they never asked about
```

Add `response_model_exclude_unset=True` to only send what was explicitly set:

```python
@app.get("/items/1", response_model=Item, response_model_exclude_unset=True)
def get_item():
    return {"id": 1, "name": "Laptop"}
    # Response: {"id": 1, "name": "Laptop"}   ← clean!
```

**When to use it:** PATCH endpoints (partial updates) where you want to return only the changed fields.

---

## 5. `response_model_exclude_none`

Similar — strips only fields whose value is `None`:

```python
@app.get("/items/1", response_model=Item, response_model_exclude_none=True)
def get_item():
    return {"id": 1, "name": "Laptop", "description": None, "discount": 0.0}
    # Response: {"id": 1, "name": "Laptop", "discount": 0.0}
    # (description is gone because it was None)
    # (discount stays because 0.0 is not None)
```

**Difference:**

| Option | What gets stripped |
|--------|-------------------|
| `exclude_unset=True` | Fields never explicitly set (even if they have defaults) |
| `exclude_none=True` | Fields whose final value is `None` |

---

## 6. `response_model_include` and `response_model_exclude`

Fine-grained control — pick which fields to include/exclude by name:

```python
@app.get("/users/1", response_model=UserOut, response_model_include={"id", "email"})
def get_user():
    return db.get_user(1)
    # Even if UserOut has 10 fields, only id and email are sent

@app.get("/users/1/public", response_model=UserOut, response_model_exclude={"internal_notes"})
def get_user_public():
    return db.get_user(1)
```

Use sparingly — it's usually cleaner to have a dedicated response model than to exclude ad-hoc.

---

## 7. `response_model=List[Model]`

For list endpoints:

```python
from typing import List

@app.get("/users", response_model=List[UserOut])
def list_users():
    return db.get_all_users()   # each user is filtered through UserOut
```

Or modern Python 3.9+ syntax:

```python
@app.get("/users", response_model=list[UserOut])
def list_users():
    return db.get_all_users()
```

---

## 8. Return Type Hint vs `response_model=`

Python 3.10+ allows using a return type hint directly:

```python
@app.get("/users/1")
def get_user() -> UserOut:   # same effect as response_model=UserOut
    return db.get_user(1)
```

Both work. The difference:

| | `response_model=UserOut` | `-> UserOut` return hint |
|---|---|---|
| FastAPI uses it? | ✅ Yes | ✅ Yes |
| Can override with `exclude_unset`? | ✅ Yes | ❌ No (only via `response_model=`) |
| Editor type checking? | ❌ Limited | ✅ Full |

**Recommendation:** Use `response_model=` when you need options like `exclude_unset`. Use `-> ReturnType` for simple cases where editor hints matter more.

---

## 9. Returning Models That Don't Match the `response_model`

FastAPI validates the *response* through the response model. So you can return:
- A **dict** that matches the model's fields
- A **Pydantic model** of a different class (it just needs the right attributes)
- An **ORM object** (if `from_attributes=True` is set — covered in Lesson 23)

```python
class UserDB(BaseModel):
    id: int
    email: str
    name: str
    password_hash: str   # will be stripped

@app.get("/users/1", response_model=UserOut)
def get_user():
    db_user: UserDB = fetch_from_db()
    return db_user   # FastAPI re-serializes through UserOut, stripping password_hash
```

---

## 10. Real-World Use Case — Full CRUD with Separated Models

```python
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status

app = FastAPI()

# ---- Models ----
class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    draft: bool = True

class PostOut(BaseModel):
    id: int
    title: str
    content: str
    draft: bool

class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    draft: bool | None = None

# ---- In-memory DB ----
db: dict[int, dict] = {}

# ---- Endpoints ----
@app.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(post: PostCreate):
    new_id = len(db) + 1
    db[new_id] = {"id": new_id, **post.model_dump()}
    return db[new_id]

@app.get("/posts", response_model=list[PostOut])
def list_posts():
    return list(db.values())

@app.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int):
    post = db.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.patch("/posts/{post_id}", response_model=PostOut, response_model_exclude_unset=True)
def update_post(post_id: int, updates: PostUpdate):
    post = db.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    # Only update fields that were actually sent
    updates_dict = updates.model_dump(exclude_unset=True)
    post.update(updates_dict)
    return post
```

Notice:
- `PostCreate` is the input model (for POST body)
- `PostOut` is the response model (controls what clients see)
- `PostUpdate` is for PATCH — all fields optional
- `response_model_exclude_unset=True` on PATCH returns only changed fields

---

## 11. Mini Task

Open `main.py` in this lesson:

1. Run: `uvicorn main:app --reload`
2. Test in `/docs`:
   - **POST `/users`** → verify `password_hash` is NOT in the response
   - **GET `/users/1`** → same check
   - **GET `/items/1`** with and without `exclude_none`
   - **PATCH `/posts/1`** with only `{"draft": false}` → confirm only the changed field returns (if `exclude_unset=True`)
3. **Bonus:** Add a `GET /users/{id}/admin` endpoint that uses `response_model_include={"id", "email", "role"}` and returns a user with an `admin_notes` field that should be hidden.

---

## 12. Key Takeaways

- `response_model=` on the decorator is the primary way to control output shape.
- Separate input model (`UserCreate`) from output model (`UserOut`) — standard pattern.
- `response_model_exclude_unset=True` is ideal for PATCH endpoints.
- `response_model_exclude_none=True` cleans up sparse responses.
- FastAPI filters the response *through* the model automatically — no manual `.pop()`.
- The return type hint (`-> Model`) works too, but can't use `exclude_unset` options.

---

## ➡️ Next Lesson

**Lesson 11 — Multiple Models per Route**
- `UserCreate`, `UserResponse`, `UserUpdate` pattern in detail
- When to inherit vs compose models
- Keeping your models DRY without creating a tangled hierarchy
