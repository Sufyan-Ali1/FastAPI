"""
Lesson 4 — Path Parameters
--------------------------
Demonstrates:
  - Basic path parameters with type hints
  - Validation with Path(...)
  - Multiple path parameters
  - Route ordering (static before dynamic)
  - Enum-restricted path parameters
  - Path containing slashes (:path converter)

Run from inside this folder:
    uvicorn main:app --reload

Test in Swagger UI:
    http://127.0.0.1:8000/docs
"""

from enum import Enum
from fastapi import FastAPI, Path

app = FastAPI(title="Lesson 4 - Path Parameters")


# ----------------------------------------------------
# 1. Static route MUST come BEFORE dynamic route
#    Otherwise "/users/me" would match "/users/{user_id}"
# ----------------------------------------------------
@app.get("/users/me")
def read_current_user():
    return {"user_id": "me", "name": "Logged-in User"}


# ----------------------------------------------------
# 2. Basic path parameter with type hint + validation
# ----------------------------------------------------
@app.get("/users/{user_id}")
def get_user(
    user_id: int = Path(
        ...,
        ge=1,                       # must be >= 1
        le=1000,                    # must be <= 1000
        title="User ID",
        description="The ID of the user (between 1 and 1000)",
    )
):
    return {"user_id": user_id}


# ----------------------------------------------------
# 3. Multiple path parameters
# ----------------------------------------------------
@app.get("/users/{user_id}/posts/{post_id}")
def get_user_post(user_id: int, post_id: int):
    return {"user_id": user_id, "post_id": post_id}


# ----------------------------------------------------
# 4. Enum-restricted path parameter
#    Only 'small', 'medium', 'large' are allowed.
# ----------------------------------------------------
class Size(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


@app.get("/sizes/{size}")
def get_size(size: Size):
    return {"size": size, "label": size.value.upper()}


# ----------------------------------------------------
# 5. Path parameter that can contain slashes (:path)
#    e.g. /files/home/user/notes.txt
# ----------------------------------------------------
@app.get("/files/{file_path:path}")
def read_file(file_path: str):
    return {"file_path": file_path}

@app.get("/products/{product_id}")
def get_product(
    product_id: int = Path(
        ..., 
        ge=100 , # must be >= 100
        le = 9999, # must be <= 9999
        description="The ID of the product (between 100 and 9999)"
        )
    ):
    return {"product_id": product_id}