# Lesson 6 — Request Body with Pydantic Models

> **Goal of this lesson:** Replace flimsy `dict` parameters with **proper data models** that automatically validate, document, and convert JSON request bodies. This is FastAPI's killer feature.

---

## 1. What is a "request body"?

When the client sends data **inside** a request (not in the URL), it's called the **request body**.

- **GET / DELETE** → usually no body. Data comes through path/query.
- **POST / PUT / PATCH** → body contains the actual data (usually JSON).

Example POST request:
```
POST /users
Content-Type: application/json

{
  "name": "Sufyan",
  "email": "sufyan@example.com",
  "age": 22
}
```

That JSON object is the **request body**.

---

## 2. The problem with using `dict`

In Lesson 3, we did this:
```python
@app.post("/items")
def create_item(item: dict):
    return item
```

It works, but has **5 big problems**:

| Problem | Example |
|---------|---------|
| ❌ No validation | Client can send `{"foo": "bar"}` and it's accepted |
| ❌ No documentation | Swagger UI shows just "object" — no fields |
| ❌ No autocomplete | Your editor has no idea what `item["name"]` is |
| ❌ No type safety | `item["age"]` might be int, str, missing… |
| ❌ Manual checks everywhere | You'd have to write `if "name" not in item: ...` |

**Solution → Pydantic models.**

---

## 3. What is Pydantic?

**Pydantic** is the data validation library that ships with FastAPI.

You define a **class** that describes what your data should look like, and Pydantic:
1. **Validates** incoming JSON against it
2. **Converts** raw types ("22" → 22) automatically
3. **Documents** your API in Swagger UI
4. **Serializes** outputs back to JSON

One class → all four jobs done. ✨

---

## 4. Your first Pydantic model

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    email: str
    age: int
```

That's it. Just a class with type hints. Now use it as the function parameter:

```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/users")
def create_user(user: User):
    return {"received": user}
```

What happens automatically when a client POSTs JSON:

```
1. FastAPI reads the request body
2. Parses JSON into a Python dict
3. Hands it to Pydantic, which:
     - checks all required fields exist
     - converts types
     - applies validation
4. If valid → calls your function with `user` (a User object)
5. If invalid → returns 422 with a clear error message
```

> 🔑 You access fields with **dot notation**: `user.name`, `user.email`, `user.age`. No more `user["name"]`.

---

## 5. Common field types

```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class Product(BaseModel):
    id: int
    name: str
    price: float
    in_stock: bool
    tags: list[str]                    # ["new", "sale"]
    metadata: dict[str, str]           # {"color": "red"}
    description: str | None = None     # optional, default None
    created_at: datetime               # ISO 8601 string → datetime
    sku: UUID                          # validated UUID
```

Pydantic handles every standard type for you, including:
- `int`, `float`, `str`, `bool`
- `list`, `dict`, `tuple`, `set`
- `datetime`, `date`, `time`
- `UUID`, `EmailStr`, `HttpUrl` (with `pip install email-validator`)

---

## 6. Required vs optional fields

Same rule as function arguments:

| Declaration | Required? |
|-------------|-----------|
| `name: str` | ✅ Yes |
| `name: str = "anonymous"` | ❌ No (default value) |
| `name: str | None = None` | ❌ No (truly optional) |

```python
class User(BaseModel):
    name: str                      # required
    email: str                     # required
    age: int = 18                  # optional, defaults to 18
    bio: str | None = None         # optional, can be missing or null
```

---

## 7. Validation with `Field()`

Want to add **rules**? Use `Field()`:

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    age: int = Field(..., ge=0, le=120)
    email: str = Field(..., pattern=r"^[\w.]+@[\w.]+\.\w+$")
    password: str = Field(..., min_length=8)
    bio: str | None = Field(None, max_length=500)
```

`Field()` accepts the **same** validators as `Path()` and `Query()`:

| Param | Meaning |
|-------|---------|
| `...` | required (Python "Ellipsis") |
| `default value` | optional with default |
| `min_length` / `max_length` | string length |
| `pattern` | regex |
| `gt` / `ge` / `lt` / `le` | numeric bounds |
| `description` | shown in Swagger docs |
| `examples=[...]` | example values in docs |

If validation fails → FastAPI returns **422** with the exact field that failed.

---

## 8. Nested models

Real data is rarely flat. Pydantic handles nesting beautifully:

```python
class Address(BaseModel):
    street: str
    city: str
    country: str

class User(BaseModel):
    name: str
    email: str
    address: Address                  # ← nested model
    friends: list[Address] = []       # ← list of nested models
```

JSON the client sends:
```json
{
  "name": "Sufyan",
  "email": "sufyan@example.com",
  "address": {
    "street": "123 Main St",
    "city": "Karachi",
    "country": "PK"
  },
  "friends": []
}
```

Pydantic validates the inner `Address` recursively. Access via `user.address.city`.

---

## 9. Combining Pydantic with `Field` for docs metadata

Add `description` and `examples` so Swagger UI looks great:

```python
class Product(BaseModel):
    name: str = Field(..., description="Product name", examples=["Laptop"])
    price: float = Field(..., gt=0, description="Price in USD")
    tags: list[str] = Field(default=[], description="Tag list")
```

This makes `/docs` actually useful for frontend devs and API consumers.

---

## 10. Returning a Pydantic model

You can also **return** a model from your function. FastAPI converts it to JSON automatically:

```python
@app.post("/users")
def create_user(user: User) -> User:
    # ... save to DB ...
    return user      # FastAPI serializes the User object to JSON
```

> 💡 We'll go deeper into **response models** in Lesson 10 — but you can already see how clean it is.

---

## 11. Real-World Use Case

In a production user-registration API:

```python
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    email: str = Field(..., pattern=r"^[\w.]+@[\w.]+\.\w+$")
    password: str = Field(..., min_length=8)
    full_name: str | None = None
    age: int = Field(..., ge=13, le=120)

@app.post("/register")
def register(data: UserRegister):
    # data is fully validated by the time we reach this line
    return {"message": f"Welcome, {data.username}!"}
```

You wrote the rules **once**, and now:
- ✅ Every field is validated
- ✅ Swagger docs show every field with constraints
- ✅ Frontend devs know exactly what to send
- ✅ No manual `if`-checks needed in your function

---

## 12. Mini Task

Open `main.py` in this lesson folder and:

1. Run: `uvicorn main:app --reload`
2. Test in `/docs`:
   - **POST `/users`** with valid JSON → ✅ should return your data
   - Send `{"name": "X"}` → ❌ should fail (`min_length=2`)
   - Send `{"name": "Sufyan", "age": 200}` → ❌ should fail (`le=120`)
   - **POST `/products`** with a nested `details` object → see nested model in action
3. **Bonus:** Add an endpoint `POST /signup` that accepts a model with:
   - `username` (str, 3–20 chars, regex `^[a-z0-9_]+$`)
   - `email` (str)
   - `password` (str, min 8 chars)
   - `age` (int, ≥ 13)

---

## 13. Key Takeaways

- **Don't use `dict`** for request bodies. Use Pydantic `BaseModel`.
- One class → validation + docs + autocomplete + serialization.
- Type hints define field types; **defaults** decide required vs optional.
- `Field()` adds validators (`min_length`, `pattern`, `ge`, etc.) and docs metadata.
- **Nested models** work out of the box.
- Validation failures → automatic **422** responses, no manual code.

---

## ➡️ Next Lesson

**Lesson 7 — Combining Path + Query + Body**
- Mixing all three in one endpoint
- Order of parameters
- Multiple body parameters in one request
