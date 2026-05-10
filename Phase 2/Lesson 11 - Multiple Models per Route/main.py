"""
Lesson 11 — Multiple Models per Route
--------------------------------------
Demonstrates:
  - UserBase / UserCreate / UserOut / UserUpdate / UserDB pattern
  - Inheritance (Create, Out extend Base) vs standalone (Update)
  - model_dump(exclude_unset=True) for correct PATCH behaviour
  - Product model family as a second real-world example
  - response_model filtering out internal DB fields

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

from datetime import datetime
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, model_validator

app = FastAPI(title="Lesson 11 - Multiple Models per Route")


# ============================================================
# USER resource — 5-model family
# ============================================================

class UserBase(BaseModel):
    """Shared required fields. Every user-related model inherits these."""
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    name: str = Field(..., min_length=2, max_length=100)


class UserCreate(UserBase):
    """POST body — inherits email+name, adds password + confirm."""
    password: str = Field(..., min_length=8)
    password_confirm: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self


class UserOut(UserBase):
    """GET response — inherits email+name, adds server-generated fields."""
    id: int
    created_at: datetime


class UserUpdate(BaseModel):
    """PATCH body — standalone, all optional. Does NOT inherit UserBase."""
    email: str | None = Field(None, pattern=r"^[^@]+@[^@]+\.[^@]+$")
    name: str | None = Field(None, min_length=2, max_length=100)


class UserDB(UserOut):
    """Internal DB model — never exposed as response_model."""
    password_hash: str


# Fake in-memory store
users_db: dict[int, dict] = {}


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    new_id = len(users_db) + 1
    record = {
        "id": new_id,
        "email": user.email,
        "name": user.name,
        "created_at": datetime.now(),
        "password_hash": f"hashed_{user.password}",
    }
    users_db[new_id] = record
    return record   # FastAPI filters through UserOut — password_hash stripped


@app.get("/users", response_model=list[UserOut])
def list_users():
    return list(users_db.values())


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@app.patch("/users/{user_id}", response_model=UserOut, response_model_exclude_unset=True)
def update_user(user_id: int, updates: UserUpdate):
    """
    PATCH — only touches fields the client actually sent.
    model_dump(exclude_unset=True) ensures we don't overwrite
    existing fields with None.
    """
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    changed = updates.model_dump(exclude_unset=True)
    user.update(changed)
    return user


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int):
    if user_id not in users_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    del users_db[user_id]


# ============================================================
# PRODUCT resource — a second model family
# Shows: cost_price is DB-internal, never reaches the client
# ============================================================

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    price: float = Field(..., gt=0, description="Selling price in USD")


class ProductCreate(ProductBase):
    stock: int = Field(0, ge=0)
    category: str = Field(..., min_length=1)
    cost_price: float = Field(..., gt=0, description="Internal cost — never sent to clients")


class ProductOut(ProductBase):
    id: int
    stock: int
    category: str
    # cost_price is intentionally absent


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    price: float | None = Field(None, gt=0)
    stock: int | None = Field(None, ge=0)


products_db: dict[int, dict] = {}


@app.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate):
    new_id = len(products_db) + 1
    record = {"id": new_id, **product.model_dump()}
    products_db[new_id] = record
    return record   # cost_price is stripped by response_model=ProductOut


@app.get("/products", response_model=list[ProductOut])
def list_products():
    return list(products_db.values())


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    product = products_db.get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@app.patch("/products/{product_id}", response_model=ProductOut, response_model_exclude_unset=True)
def update_product(product_id: int, updates: ProductUpdate):
    product = products_db.get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    changed = updates.model_dump(exclude_unset=True)
    product.update(changed)
    return product
