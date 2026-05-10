"""
Lesson 10 — Response Models
----------------------------
Demonstrates:
  - response_model= to filter output fields
  - Separate input / output models (UserCreate vs UserOut)
  - response_model_exclude_unset (ideal for PATCH)
  - response_model_exclude_none (strip null fields)
  - response_model_include / exclude by field name
  - list[Model] as a response model

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 10 - Response Models")


# ============================================================
# 1. The problem — password_hash leaking without response_model
# ============================================================

class UserCreate(BaseModel):
    email: str
    name: str
    password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    """What the CLIENT sees — no password, no internal fields."""
    id: int
    email: str
    name: str


class UserDB(BaseModel):
    """Internal model — includes password_hash."""
    id: int
    email: str
    name: str
    password_hash: str


# Fake DB
users_db: dict[int, dict] = {}


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    """
    Client sends password. We store password_hash.
    Response is filtered through UserOut — password_hash never leaves.
    """
    new_id = len(users_db) + 1
    db_record = {
        "id": new_id,
        "email": user.email,
        "name": user.name,
        "password_hash": f"hashed_{user.password}",  # fake hash
    }
    users_db[new_id] = db_record
    return db_record  # FastAPI strips password_hash via response_model=UserOut


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@app.get("/users", response_model=list[UserOut])
def list_users():
    return list(users_db.values())


# ============================================================
# 2. response_model_exclude_unset — ideal for PATCH
# ============================================================

class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str
    published: bool = False
    views: int = 0


class PostOut(BaseModel):
    id: int
    title: str
    content: str
    published: bool
    views: int


class PostUpdate(BaseModel):
    """All fields optional — only send what you want to change."""
    title: str | None = None
    content: str | None = None
    published: bool | None = None


posts_db: dict[int, dict] = {}


@app.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(post: PostCreate):
    new_id = len(posts_db) + 1
    record = {"id": new_id, **post.model_dump()}
    posts_db[new_id] = record
    return record


@app.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int):
    post = posts_db.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.patch(
    "/posts/{post_id}",
    response_model=PostOut,
    response_model_exclude_unset=True,  # only return what changed
)
def update_post(post_id: int, updates: PostUpdate):
    """
    PATCH only touches provided fields.
    response_model_exclude_unset=True means the response
    only contains the fields actually set — not all defaults.
    """
    post = posts_db.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    changed = updates.model_dump(exclude_unset=True)
    post.update(changed)
    return post


# ============================================================
# 3. response_model_exclude_none — strip null fields
# ============================================================

class Article(BaseModel):
    id: int
    title: str
    subtitle: str | None = None
    summary: str | None = None
    word_count: int = 0


articles_db: dict[int, dict] = {
    1: {"id": 1, "title": "FastAPI Rocks", "subtitle": None, "summary": None, "word_count": 500},
    2: {"id": 2, "title": "Pydantic Tips", "subtitle": "Must read", "summary": None, "word_count": 200},
}


@app.get("/articles/{article_id}", response_model=Article)
def get_article_full(article_id: int):
    """Returns ALL fields including nulls."""
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Not found")
    return article


@app.get("/articles/{article_id}/clean", response_model=Article, response_model_exclude_none=True)
def get_article_clean(article_id: int):
    """Returns only non-null fields — cleaner for the client."""
    article = articles_db.get(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Not found")
    return article


# ============================================================
# 4. response_model_include / response_model_exclude
# ============================================================

class FullUser(BaseModel):
    id: int
    name: str
    email: str
    role: str = "user"
    internal_notes: str = ""


full_users_db: dict[int, dict] = {
    1: {
        "id": 1, "name": "Sufyan", "email": "sufyan@example.com",
        "role": "admin", "internal_notes": "flagged for review"
    }
}


@app.get(
    "/admin/users/{user_id}",
    response_model=FullUser,
    response_model_include={"id", "name", "email", "role"},
)
def get_admin_user(user_id: int):
    """
    Returns only id, name, email, role.
    internal_notes is excluded even though it's in FullUser.
    """
    user = full_users_db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    return user
