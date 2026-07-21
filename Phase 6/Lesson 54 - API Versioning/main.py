"""
Lesson 54 - API Versioning
--------------------------
Serves /api/v1 and /api/v2 SIDE BY SIDE, demonstrating a real breaking change
handled without breaking old clients:

    v1  GET /api/v1/users/{id}  -> {"id", "name", "email"}                (old contract)
    v2  GET /api/v2/users/{id}  -> {"id", "first_name", "last_name", ...} (new contract)

Both versions are served by the SAME user service - only the response SHAPE
differs. v1 also sends Deprecation/Sunset headers so clients know to migrate.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Then open /docs (endpoints grouped by version tag).
"""

from fastapi import APIRouter, FastAPI, HTTPException, Response
from pydantic import BaseModel

app = FastAPI(title="Lesson 54 - API Versioning")


# ---------------------------------------------------------------------------
# ONE service = one source of truth. Both API versions call this; they only
# differ in how they SHAPE the response.
# ---------------------------------------------------------------------------
class User:
    def __init__(self, id: int, first: str, last: str, email: str):
        self.id, self.first, self.last, self.email = id, first, last, email


_USERS = {
    1: User(1, "Ada", "Lovelace", "ada@example.com"),
    2: User(2, "Alan", "Turing", "alan@example.com"),
}


def get_user(user_id: int) -> User:
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


# ---------------------------------------------------------------------------
# v1 - the OLD contract: a single `name` field. Kept running for existing
# clients, but marked deprecated.
# ---------------------------------------------------------------------------
v1 = APIRouter(prefix="/api/v1", tags=["v1 (deprecated)"])


class UserV1(BaseModel):
    id: int
    name: str            # v1 combined the name into one field
    email: str


@v1.get("/users/{user_id}", response_model=UserV1)
def get_user_v1(user_id: int, response: Response):
    u = get_user(user_id)
    # Signal deprecation so clients can migrate programmatically.
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Sat, 31 Dec 2026 23:59:59 GMT"
    response.headers["Link"] = '<https://docs.example.com/migrate-v2>; rel="deprecation"'
    return UserV1(id=u.id, name=f"{u.first} {u.last}", email=u.email)


# ---------------------------------------------------------------------------
# v2 - the NEW contract: first_name / last_name split out (a BREAKING change,
# which is exactly why it needs a new version).
# ---------------------------------------------------------------------------
v2 = APIRouter(prefix="/api/v2", tags=["v2 (current)"])


class UserV2(BaseModel):
    id: int
    first_name: str      # v2 splits the name -> would break any v1 client
    last_name: str
    email: str


@v2.get("/users/{user_id}", response_model=UserV2)
def get_user_v2(user_id: int):
    u = get_user(user_id)
    return UserV2(id=u.id, first_name=u.first, last_name=u.last, email=u.email)


# v2 can also add NEW, version-specific endpoints (additive, no v1 equivalent).
@v2.get("/users", response_model=list[UserV2])
def list_users_v2():
    return [
        UserV2(id=u.id, first_name=u.first, last_name=u.last, email=u.email)
        for u in _USERS.values()
    ]


app.include_router(v1)
app.include_router(v2)


@app.get("/")
def root():
    return {"versions": ["/api/v1 (deprecated)", "/api/v2 (current)"], "docs": "/docs"}
