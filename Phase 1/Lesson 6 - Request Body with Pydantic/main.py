"""
Lesson 6 — Request Body with Pydantic Models
--------------------------------------------
Demonstrates:
  - BaseModel with type hints
  - Required vs optional fields
  - Validation with Field()
  - Nested models
  - Returning a model directly

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 6 - Pydantic Request Body")


# ----------------------------------------------------
# 1. Simple Pydantic model
# ----------------------------------------------------
class User(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., pattern=r"^[\w.]+@[\w.]+\.\w+$")
    age: int = Field(..., ge=0, le=120)
    bio: str | None = Field(None, max_length=500)

class SignUpRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20,pattern=r"^[a-zA-Z0-9_]+$")
    email: str = Field(..., pattern=r"^[\w.]+@[\w.]+\.\w+$")
    password: str = Field(..., min_length=8)
    age: int = Field(..., ge=13)


@app.post("/users")
def create_user(user: User):
    """Create a new user. The body is validated automatically."""
    return {"message": "User created", "user": user}


# ----------------------------------------------------
# 2. Nested models
# ----------------------------------------------------
class ProductDetails(BaseModel):
    color: str = Field(..., examples=["red"])
    weight_kg: float = Field(..., gt=0)
    in_stock: bool = True


class Product(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0, description="Price in USD")
    tags: list[str] = Field(default=[], description="Tag list")
    details: ProductDetails


@app.post("/products")
def create_product(product: Product):
    """Notice how `details` is a full nested model — validated recursively."""
    return {"message": "Product created", "product": product}


# ----------------------------------------------------
# 3. Returning a model directly
# ----------------------------------------------------
class EchoResponse(BaseModel):
    received: dict
    success: bool = True


@app.post("/echo", response_model=EchoResponse)
def echo(payload: dict):
    """FastAPI auto-serializes the returned EchoResponse object to JSON."""
    return EchoResponse(received=payload)


@app.post("/sign-up")
def sign_up(request: SignUpRequest):
    """Example of a more realistic sign-up endpoint."""
    # Here you would normally create the user in the database
    return {"message": f"User '{request.username}' signed up successfully!"}