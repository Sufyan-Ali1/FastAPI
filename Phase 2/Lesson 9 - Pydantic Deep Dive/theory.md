# Lesson 9 — Pydantic Deep Dive

> **Goal of this lesson:** Go beyond basic `Field()` validation. Write **custom validators** using decorators, configure model behaviour with `model_config`, and understand Pydantic v1 vs v2 differences so you're future-proof.

---

## 1. What's Wrong with Just `Field()`?

Until now, we've validated individual fields:

```python
class User(BaseModel):
    password: str = Field(..., min_length=8)
    age: int = Field(..., ge=0, le=120)
```

But many real rules span **multiple fields**:
- Password and password-confirm must **match**
- If `is_premium=True`, then `subscription_date` must be **set**
- If age < 18, then `parental_consent` must be **true**
- Email domain must **not** be on a blocklist

For these, plain `Field()` isn't enough. You need **custom validators**.

---

## 2. `@field_validator` — Validate a Single Field

The simplest custom validator runs **after** Pydantic parses a field, letting you add arbitrary logic:

```python
from pydantic import BaseModel, Field, field_validator

class User(BaseModel):
    username: str = Field(..., min_length=3)
    
    @field_validator("username")
    @classmethod
    def username_no_spaces(cls, v):
        if " " in v:
            raise ValueError("Username cannot contain spaces")
        return v
```

**Rules:**
1. Decorator: `@field_validator("field_name")`
2. Always `@classmethod` (Pydantic requirement)
3. Always take `cls` and `v` (value)
4. **Raise `ValueError`** if validation fails (Pydantic catches it)
5. **Return the (possibly modified) value** if valid

### Multiple fields at once

```python
@field_validator("email", "backup_email")
@classmethod
def emails_valid(cls, v):
    if "@" not in v:
        raise ValueError("Invalid email")
    return v.lower()  # normalize to lowercase
```

### Access other fields during validation

Use the `info` parameter to check other fields:

```python
from pydantic import ValidationInfo

class User(BaseModel):
    password: str
    password_confirm: str
    
    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v, info: ValidationInfo):
        if v != info.data.get("password"):
            raise ValueError("Passwords do not match")
        return v
```

> 💡 `info.data` contains all fields validated **so far**. Be careful about field order if you need this.

---

## 3. `@model_validator` — Validate the Entire Model

After *all* fields are validated, `@model_validator` runs on the whole model. Perfect for cross-field rules:

```python
from pydantic import BaseModel, model_validator

class Event(BaseModel):
    start_date: datetime
    end_date: datetime
    
    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
```

**Two modes:**
- `mode="after"` — runs **after** all field validators
- `mode="before"` — runs **before** field parsing (rare; gets raw input)

> 🔑 Use `mode="after"` 99% of the time.

---

## 4. `model_config` — Control Model Behaviour

Pydantic v2 uses a `model_config` class variable to set options. (Pydantic v1 used a `Config` inner class — more on that later.)

```python
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,        # auto-trim strings
        validate_default=True,            # validate default values too
        json_schema_extra={"example": {}},  # docs
    )
    
    name: str
    age: int = 18
```

### Common `ConfigDict` options

| Option | What it does | Use when |
|--------|--------------|----------|
| `str_strip_whitespace=True` | Auto `.strip()` all strings | User input often has accidental spaces |
| `validate_default=True` | Even defaults go through validators | Safety-critical fields |
| `frozen=True` | Model instances are immutable | Prevent accidental mutations |
| `use_enum_values=True` | Serialize `Enum` to its `.value`, not name | JSON needs the raw value |
| `populate_by_name=True` | Accept both field name AND alias | API needs both `user_id` and `userId` |

---

## 5. Field Aliases — Accept Multiple Names

Sometimes the API consumer's naming doesn't match your Python style:

```python
class Product(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    product_id: int = Field(..., alias="id")
    product_name: str = Field(..., alias="name")
```

Client can send **either**:
```json
{ "id": 1, "name": "Laptop" }          // use alias
or
{ "product_id": 1, "product_name": "Laptop" }  // use field name
```

But your Python code always uses `product_id`, `product_name`.

---

## 6. Custom Serialization with `field_serializer`

By default, Pydantic serializes fields as-is. Sometimes you need to transform **on output**:

```python
from pydantic import field_serializer

class User(BaseModel):
    password: str
    created_at: datetime
    
    @field_serializer("password")
    def hide_password(self, v):
        return "***"
    
    @field_serializer("created_at")
    def format_datetime(self, v):
        return v.strftime("%Y-%m-%d")
```

When you call `.model_dump()` or return the model from an endpoint, `password` and `created_at` are transformed.

---

## 7. Pydantic v1 vs v2 — Key Differences

If you're migrating v1 code or reading old docs, watch for:

| Feature | Pydantic v1 | Pydantic v2 |
|---------|------------|------------|
| **Validator decorator** | `@validator` | `@field_validator` |
| **Model validator** | `@root_validator` | `@model_validator` |
| **Config** | Inner `class Config:` | `model_config = ConfigDict(...)` |
| **Serialization** | `.dict()` | `.model_dump()` |
| **Serialization (JSON)** | `.json()` | `.model_dump_json()` |
| **ORM mode** | `class Config: orm_mode = True` | `ConfigDict(from_attributes=True)` |
| **Validator mode** | N/A | `@field_validator(mode="...")` |

**v1 to v2 migration tip:** Search and replace is **not** safe — read Pydantic docs carefully. The validator logic is the same, but decorator names and config syntax changed.

---

## 8. `mode` Parameter in Validators

`@field_validator` can also take a `mode`:

```python
@field_validator("age", mode="before")
@classmethod
def coerce_age(cls, v):
    # v might be "25" (string), convert before Pydantic parses it
    return int(v)
```

- `mode="after"` — default, runs after type parsing
- `mode="before"` — runs on raw input, before parsing
- `mode="wrap"` — runs around the normal validator (advanced)

---

## 9. Combining Validators with Dependencies

Validators run *inside* Pydantic, **before** your endpoint function. So they're your first line of defence:

```python
class SignupForm(BaseModel):
    email: str
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    
    @field_validator("email")
    @classmethod
    def email_unique(cls, v):
        if db.email_exists(v):
            raise ValueError("Email already registered")
        return v
    
    @field_validator("username")
    @classmethod
    def username_unique(cls, v):
        if db.username_exists(v):
            raise ValueError("Username taken")
        return v

@app.post("/signup", status_code=201)
def signup(form: SignupForm):
    # If we reach here, email and username are guaranteed unique
    return db.create_user(form.email, form.username, form.password)
```

---

## 10. Real-World Use Case — User Registration

A full signup form with cascading validation:

```python
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from datetime import datetime

class SignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-z0-9_]+$")
    password: str = Field(..., min_length=8)
    password_confirm: str
    age: int = Field(..., ge=13, le=120)
    terms_accepted: bool
    
    @field_validator("email")
    @classmethod
    def email_not_blocked(cls, v):
        blocked_domains = ["spam.com", "fake.net"]
        domain = v.split("@")[1]
        if domain in blocked_domains:
            raise ValueError(f"Email domain {domain} not allowed")
        return v
    
    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*" for c in v)
        if not (has_digit and has_special):
            raise ValueError("Password must contain digit and special char")
        return v
    
    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v, info: ValidationInfo):
        if v != info.data.get("password"):
            raise ValueError("Passwords do not match")
        return v
    
    @model_validator(mode="after")
    def check_age_and_terms(self):
        if self.age < 18 and not self.terms_accepted:
            raise ValueError("Users under 18 must accept parental consent terms")
        return self

@app.post("/signup", status_code=201)
def signup(req: SignupRequest):
    """By this point, every rule has been checked."""
    user = db.create_user(
        email=req.email,
        username=req.username,
        password_hash=hash_password(req.password),
        age=req.age,
    )
    return {"id": user.id, "email": user.email}
```

Every field is **thoroughly validated** before your code runs. Swagger UI shows them all in `/docs`.

---

## 11. Mini Task

Open `main.py` and:

1. Run: `uvicorn main:app --reload`
2. Test in `/docs`:
   - POST `/users` with matching passwords → **201**
   - POST `/users` with mismatched passwords → **422** saying they don't match
   - POST `/users` with `password: "abc"` (too short) → **422** caught by `Field()`
   - POST `/users` with `password: "abcdefgh"` (no digits) → **422** caught by validator
   - POST `/users` with username `"123abc"` (starts with digit) → **422**
3. **Bonus:** Add a `POST /events` endpoint that:
   - Takes `start: datetime`, `end: datetime`
   - Uses `@model_validator` to ensure `end > start`
   - Returns the event or a 422 if times are backwards

---

## 12. Key Takeaways

- **`@field_validator`** for single-field rules beyond `Field()` constraints.
- **`@model_validator(mode="after")`** for cross-field rules.
- **`model_config`** controls parsing, serialization, and aliasing.
- **Validators run before your endpoint** — they're your first defence.
- **Pydantic v1 → v2** changed decorator names and config syntax — watch for migration gotchas.
- **Raise `ValueError`** in validators — Pydantic converts it to 422.

---

## ➡️ Next Lesson

**Lesson 10 — Response Models**
- `response_model=` on the decorator
- Filtering output fields
- `response_model_exclude_unset`, `exclude_none`
- Separate input & output models
