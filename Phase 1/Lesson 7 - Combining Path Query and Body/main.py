"""
Lesson 7 — Combining Path + Query + Body
----------------------------------------
Demonstrates:
  - Mixing path, query, and body in one endpoint
  - How FastAPI decides which source each parameter comes from
  - Multiple Pydantic models in a single body
  - Body() to force a primitive into the body
  - Body(embed=True) to wrap a single model under a key

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, Body
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 7 - Combining Path + Query + Body")


# ----------------------------------------------------
# 1. Path + Query + Body in one endpoint
# ----------------------------------------------------
class PostUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str


@app.put("/users/{user_id}/posts/{post_id}")
def update_post(
    user_id: int,            # PATH  (name matches {user_id})
    post_id: int,            # PATH  (name matches {post_id})
    post: PostUpdate,        # BODY  (Pydantic model)
    notify: bool = False,    # QUERY (simple type, not in path)
):
    """
    PUT /users/42/posts/9?notify=true
    Body: { "title": "Hello", "content": "world" }
    """
    return {
        "user_id": user_id,
        "post_id": post_id,
        "notify": notify,
        "updated": post,
    }


# ----------------------------------------------------
# 2. Multiple body parameters (each model gets its own key)
# ----------------------------------------------------
class User(BaseModel):
    name: str = Field(..., min_length=2)
    email: str


class Item(BaseModel):
    title: str
    price: float = Field(..., gt=0)


@app.post("/orders")
def create_order(user: User, item: Item):
    """
    Body must look like:
    {
      "user": { "name": "Sufyan", "email": "x@y.com" },
      "item": { "title": "Laptop", "price": 999.99 }
    }
    """
    return {"user": user, "item": item}


# ----------------------------------------------------
# 3. Forcing a primitive into the body with Body()
# ----------------------------------------------------
@app.post("/orders-with-priority")
def create_order_with_priority(
    user: User,
    item: Item,
    priority: int = Body(..., ge=1, le=5),
):
    """
    Body must look like:
    {
      "user": { ... },
      "item": { ... },
      "priority": 3
    }
    Without Body(), `priority` would be treated as a query parameter.
    """
    return {"user": user, "item": item, "priority": priority}


# ----------------------------------------------------
# 4. Embedding a single model under a key
# ----------------------------------------------------
@app.post("/users-embedded")
def create_user_embedded(user: User = Body(..., embed=True)):
    """
    Body must look like:
    { "user": { "name": "...", "email": "..." } }

    Without embed=True it would be:
    { "name": "...", "email": "..." }
    """
    return {"received": user}
