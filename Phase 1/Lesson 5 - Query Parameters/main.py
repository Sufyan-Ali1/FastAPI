"""
Lesson 5 — Query Parameters
---------------------------
Demonstrates:
  - Required vs optional query params
  - Default values & type conversion
  - Validation with Query(...)
  - Optional params (None default)
  - Lists (multiple values for one param)
  - Combining path + query params

Run:
    uvicorn main:app --reload

Test in Swagger UI:
    http://127.0.0.1:8000/docs
"""

from typing import Annotated
from fastapi import FastAPI, Query

app = FastAPI(title="Lesson 5 - Query Parameters")


# ----------------------------------------------------
# 1. Basic query params: required + optional with default
# ----------------------------------------------------
# @app.get("/products")
# def list_products(category: str, page: int = 1):
#     """
#     /products?category=shoes&page=2
#     - category is REQUIRED (no default)
#     - page defaults to 1
#     """
#     return {"category": category, "page": page}


# ----------------------------------------------------
# 2. Type conversion (int, bool, float)
# ----------------------------------------------------
@app.get("/items")
def list_items(limit: int = 10, in_stock: bool = True, price: float = 0.0):
    """
    /items?limit=5&in_stock=false&price=19.99
    Strings in the URL → real Python types automatically.
    """
    return {"limit": limit, "in_stock": in_stock, "price": price}


# ----------------------------------------------------
# 3. Validation with Query(...)
# ----------------------------------------------------
@app.get("/search")
def search(
    q: str = Query(
        ...,
        min_length=3,
        max_length=50,
        title="Search term",
        description="Text to search for (3–50 chars)",
    ),
    page: int = Query(1, ge=1, le=1000),
):
    """
    /search?q=fastapi&page=2
    """
    return {"q": q, "page": page}


# ----------------------------------------------------
# 4. Optional param (None default)
# ----------------------------------------------------
@app.get("/users")
def list_users(role: str | None = None):
    """
    /users          -> everyone
    /users?role=admin -> filtered
    """
    if role:
        return {"filter": role}
    return {"filter": "everyone"}


# ----------------------------------------------------
# 5. List / multi-value query parameter
# ----------------------------------------------------
@app.get("/items-by-tags")
def items_by_tags(tags: Annotated[list[str] | None, Query()] = None):
    """
    /items-by-tags?tag=python&tag=fastapi
    Pass the same key multiple times.
    """
    return {"tags": tags}


# ----------------------------------------------------
# 6. Combining path + query parameters
# ----------------------------------------------------
@app.get("/users/{user_id}/posts")
def list_user_posts(
    user_id: int,
    published: bool = True,
    limit: int = 10,
):
    """
    /users/5/posts?published=false&limit=20
    user_id comes from the path, the rest from the query string.
    """
    return {"user_id": user_id, "published": published, "limit": limit}

@app.get("/products")
def list_products(
    category:str,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, le=100000),
    page : int = Query(1, ge=1)
    ):
    return {"category": category, "min_price": min_price, "max_price": max_price, "page": page}