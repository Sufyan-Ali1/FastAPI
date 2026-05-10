"""
Lesson 9 — Pydantic Deep Dive
----------------------------
Demonstrates:
  - @field_validator for single-field custom logic
  - @field_validator with info.data for cross-field validation
  - @model_validator(mode="after") for entire-model rules
  - model_config for auto-strip, validation defaults, etc.
  - field_serializer for output transformation
  - Real-world signup form with password + username checks

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, status
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    field_serializer,
    ConfigDict,
    ValidationInfo,
)
from datetime import datetime

app = FastAPI(title="Lesson 9 - Pydantic Deep Dive")


# ----------------------------------------------------
# 1. Simple @field_validator example
# (username can't have spaces)
# ----------------------------------------------------
class SimpleUser(BaseModel):
    name: str
    username: str = Field(..., min_length=3)

    @field_validator("username")
    @classmethod
    def username_no_spaces(cls, v):
        if " " in v:
            raise ValueError("Username cannot contain spaces")
        return v


@app.post("/simple-user")
def create_simple_user(user: SimpleUser):
    return user


# ----------------------------------------------------
# 2. Multiple fields with @field_validator
# (both emails must be valid)
# ----------------------------------------------------
class MultiField(BaseModel):
    primary_email: str
    backup_email: str

    @field_validator("primary_email", "backup_email")
    @classmethod
    def emails_must_have_at(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()


@app.post("/multi-field")
def multi_field_example(data: MultiField):
    return data


# ----------------------------------------------------
# 3. Cross-field validation with info.data
# (password and password_confirm must match)
# ----------------------------------------------------
class PasswordReset(BaseModel):
    password: str = Field(..., min_length=8)
    password_confirm: str

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v, info: ValidationInfo):
        password = info.data.get("password")
        if v != password:
            raise ValueError("Passwords do not match")
        return v


@app.post("/reset-password")
def reset_password(reset: PasswordReset):
    return {"message": "Password changed"}


# ----------------------------------------------------
# 4. @model_validator(mode="after")
# (validate entire model as a unit)
# ----------------------------------------------------
class Event(BaseModel):
    name: str
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end <= self.start:
            raise ValueError("Event end must be after start")
        return self


@app.post("/events")
def create_event(event: Event):
    return event


# ----------------------------------------------------
# 5. model_config — auto-strip whitespace
# and populate_by_name (accept both field & alias names)
# ----------------------------------------------------
class Product(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    product_id: int = Field(..., alias="id")
    product_name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)


@app.post("/products")
def create_product(product: Product):
    # Client can send either {"id": 1, "name": "..."}
    # or {"product_id": 1, "product_name": "..."}
    return {
        "product_id": product.product_id,
        "product_name": product.product_name,
        "price": product.price,
    }


# ----------------------------------------------------
# 6. field_serializer — hide sensitive data on output
# ----------------------------------------------------
class UserWithPassword(BaseModel):
    username: str
    email: str
    password: str
    created_at: datetime

    @field_serializer("password")
    def hide_password(self, v):
        return "***"

    @field_serializer("created_at")
    def format_datetime(self, v):
        return v.strftime("%Y-%m-%d %H:%M:%S")


@app.post("/user-with-serializer")
def create_user_serializer(user: UserWithPassword):
    # When returned, password is hidden and created_at is formatted
    return user


# ----------------------------------------------------
# 7. Real-world signup form
# (comprehensive validation)
# ----------------------------------------------------
class SignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    username: str = Field(
        ..., min_length=3, max_length=20, pattern=r"^[a-z0-9_]+$"
    )
    password: str = Field(..., min_length=8)
    password_confirm: str
    age: int = Field(..., ge=13, le=120)

    @field_validator("password")
    @classmethod
    def password_has_digit_and_special(cls, v):
        """Password must have at least one digit and one special char."""
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*-_=+" for c in v)
        if not (has_digit and has_special):
            raise ValueError(
                "Password must contain at least one digit and one special character"
            )
        return v

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v, info: ValidationInfo):
        if v != info.data.get("password"):
            raise ValueError("Passwords do not match")
        return v

    @model_validator(mode="after")
    def check_age_and_username(self):
        """Cross-field validation: if age < 18, username restrictions."""
        if self.age < 18 and self.username.startswith("_"):
            raise ValueError("Users under 18 cannot use usernames starting with '_'")
        return self


@app.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest):
    """
    Full signup with multi-layer validation:
    - Pydantic Field() constraints
    - @field_validator for password strength & matches
    - @model_validator for age-based rules
    """
    return {
        "message": "Signup successful",
        "user": {
            "email": req.email,
            "username": req.username,
            "age": req.age,
        },
    }
