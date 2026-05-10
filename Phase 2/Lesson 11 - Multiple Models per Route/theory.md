# Lesson 11 — Multiple Models per Route

> **Goal of this lesson:** Design a clean **family of models** for the same resource — one for input, one for output, one for updates — without duplicating fields everywhere. This is the pattern you'll repeat for every real resource in every real API.

---

## 1. Why One Model Is Never Enough

Consider a `User` resource. The data it carries changes depending on *who's asking and when*:

| Situation | Fields needed |
|-----------|--------------|
| **Client creates a user** (POST) | email, name, password |
| **Client sees a user** (GET) | id, email, name, created_at |
| **Client updates a user** (PUT/PATCH) | name, email (no id, no password) |
| **Database stores a user** | id, email, name, password_hash, created_at |
| **Admin sees a user** | everything including internal flags |

One model can't serve all five shapes cleanly. Using a single `User` model everywhere either:
- **Leaks sensitive fields** (password_hash in GET response)
- **Forces required fields when they should be optional** (id on create)
- **Breaks auto-docs** (Swagger shows wrong fields for each endpoint)

---

## 2. The Standard 4-Model Pattern

```
UserBase       ← shared fields (email, name)
  ├── UserCreate    ← +password            (POST body)
  ├── UserUpdate    ← all optional         (PATCH body)
  └── UserOut       ← +id, +created_at     (GET response)

UserDB         ← UserOut + password_hash   (internal only)
```

This is the pattern used by virtually every production FastAPI codebase.

---

## 3. Building the Pattern Step by Step

### Step 1 — `UserBase` (shared fields)

```python
from pydantic import BaseModel, Field

class UserBase(BaseModel):
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    name: str = Field(..., min_length=2, max_length=100)
```

Fields every model shares. No duplication.

### Step 2 — `UserCreate` (POST body)

```python
class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
```

Inherits `email` + `name`. Adds `password`. Used as the POST body.

### Step 3 — `UserOut` (GET response)

```python
from datetime import datetime

class UserOut(UserBase):
    id: int
    created_at: datetime
```

Inherits `email` + `name`. Adds `id` + `created_at`. Used as `response_model`.

### Step 4 — `UserUpdate` (PATCH body)

```python
class UserUpdate(BaseModel):
    email: str | None = Field(None, pattern=r"^[^@]+@[^@]+\.[^@]+$")
    name: str | None = Field(None, min_length=2, max_length=100)
```

**Does NOT inherit `UserBase`** — because `UserBase` has required fields, but `UserUpdate` needs all optional. Every field is `| None = None`.

### Step 5 — `UserDB` (internal only)

```python
class UserDB(UserOut):
    password_hash: str
```

Inherits everything in `UserOut`. Adds `password_hash`. Never used as `response_model`.

---

## 4. Inheritance Rules

**When to inherit:**
- The child needs the *same required fields* as the parent, plus more.
- `UserCreate(UserBase)` — email and name are still required.
- `UserOut(UserBase)` — email and name are still required.

**When NOT to inherit:**
- The child makes parent's required fields optional.
- `UserUpdate` — DO NOT inherit `UserBase`. Write it independently with `| None`.

**The trap:**
```python
# ❌ WRONG
class UserUpdate(UserBase):
    pass
# Now email and name are REQUIRED in PATCH — defeats the whole point
```

---

## 5. Full Working CRUD with the Pattern

```python
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime

app = FastAPI()
db: dict[int, dict] = {}

class UserBase(BaseModel):
    email: str
    name: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserOut(UserBase):
    id: int
    created_at: datetime

class UserUpdate(BaseModel):
    email: str | None = None
    name: str | None = None

class UserDB(UserOut):
    password_hash: str


@app.post("/users", response_model=UserOut, status_code=201)
def create_user(user: UserCreate):
    new_id = len(db) + 1
    record = {
        "id": new_id,
        "email": user.email,
        "name": user.name,
        "created_at": datetime.now(),
        "password_hash": f"hashed_{user.password}",
    }
    db[new_id] = record
    return record

@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    user = db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    return user

@app.patch("/users/{user_id}", response_model=UserOut, response_model_exclude_unset=True)
def update_user(user_id: int, updates: UserUpdate):
    user = db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    changed = updates.model_dump(exclude_unset=True)
    user.update(changed)
    return user

@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    if user_id not in db:
        raise HTTPException(status_code=404, detail="Not found")
    del db[user_id]
```

---

## 6. The `model_dump(exclude_unset=True)` Trick for PATCH

PATCH should only modify what the client sends. If the client sends `{"name": "Sufyan"}`, only `name` should change — `email` must stay untouched.

```python
# PATCH body: { "name": "Sufyan" }
updates = UserUpdate(name="Sufyan")

# Without exclude_unset: {"email": None, "name": "Sufyan"}
# → email would be set to None in the DB!
print(updates.model_dump())

# With exclude_unset: {"name": "Sufyan"}
# → only name is updated, email stays unchanged
print(updates.model_dump(exclude_unset=True))
```

Always use `model_dump(exclude_unset=True)` in PATCH handlers.

---

## 7. Composition vs Inheritance

Inheritance works well for simple hierarchies. For complex resources, **composition** (embedding one model into another) is cleaner:

```python
# Composition
class Address(BaseModel):
    street: str
    city: str
    country: str

class UserWithAddress(UserBase):
    address: Address          # composed, not inherited

class UserWithAddressCreate(UserWithAddress):
    password: str
    address: Address          # same embedded model reused
```

**Rule of thumb:**
- Use **inheritance** for "is-a" relationships (`UserCreate` IS-A `UserBase`).
- Use **composition** for "has-a" relationships (`User` HAS-A `Address`).

---

## 8. Advanced: `model_validator` Across Model Family

If your `UserCreate` needs cross-field validation that `UserUpdate` doesn't need, put the validator on `UserCreate` only — not on `UserBase`:

```python
class UserCreate(UserBase):
    password: str
    password_confirm: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self
```

`UserUpdate` inherits nothing of this — it's isolated exactly where it belongs.

---

## 9. Real-World Use Case — Product Catalogue

```
ProductBase     → name, description, price
ProductCreate   → +stock, +category_id
ProductOut      → +id, +created_at, +category_name
ProductUpdate   → all optional (name, description, price, stock)
ProductDB       → ProductOut + cost_price (internal margin data)
```

```python
class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    price: float = Field(..., gt=0)

class ProductCreate(ProductBase):
    stock: int = Field(0, ge=0)
    category_id: int

class ProductOut(ProductBase):
    id: int
    stock: int
    category_name: str

class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    description: str | None = None
    price: float | None = Field(None, gt=0)
    stock: int | None = Field(None, ge=0)

class ProductDB(ProductOut):
    cost_price: float          # internal, never sent to clients
    category_id: int
```

This design means:
- Clients POST with `ProductCreate` (no id, has stock + category_id)
- Clients GET a `ProductOut` (has id, has category_name — joined from DB, no cost_price)
- Clients PATCH with `ProductUpdate` (all optional)
- DB layer works with `ProductDB` (has cost_price for margin calculation)

---

## 10. Mini Task

Open `main.py`:

1. Run: `uvicorn main:app --reload`
2. In `/docs`:
   - **POST `/users`** — verify `password_hash` and `created_at` format in response
   - **PATCH `/users/1`** with just `{"name": "New Name"}` → confirm email didn't change
   - **PATCH `/users/1`** with `{}` (empty body) → confirm nothing changes
   - **GET `/products`** → confirm `cost_price` is absent from the response
3. **Bonus:** Add a `PUT /users/{id}` (full replacement) that uses `UserCreate` as the body and returns `UserOut`. Explain in a comment why `PUT` takes `UserCreate` but `PATCH` takes `UserUpdate`.

---

## 11. Key Takeaways

- Every resource needs at least **3 models**: Create, Out, Update.
- `UserBase` holds shared required fields — subclasses inherit them.
- `UserUpdate` does **NOT** inherit `UserBase` — all its fields are `| None`.
- `model_dump(exclude_unset=True)` in PATCH handlers is essential.
- Use inheritance for "is-a", composition for "has-a".
- Keep `DB` models internal — never use them as `response_model`.

---

## ➡️ Next Lesson

**Lesson 12 — Status Codes & HTTP Exceptions**
- `HTTPException` in depth
- Custom exception handlers
- `status` module
- Returning structured error responses
