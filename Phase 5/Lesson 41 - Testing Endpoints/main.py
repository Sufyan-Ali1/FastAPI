"""
Lesson 41 - Testing Endpoints (the app under test)
--------------------------------------------------
An auth-protected API with roles and an external service dependency - the kinds
of things you must test with real tokens AND with dependency overrides.

The tests live in:

    conftest.py        - shared `client` fixture that clears overrides
    test_endpoints.py  - real-token auth, overridden auth, RBAC, mocked service

Run with:

    pip install fastapi uvicorn httpx pytest pytest-asyncio
    pytest -v
"""

from dataclasses import dataclass, field

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

app = FastAPI(title="Lesson 41 - Testing Endpoints")


# ---------------------------------------------------------------------------
# A tiny "user store" and a simplified token scheme (token == username here).
# Auth mechanics are Lesson 29; this lesson is about TESTING them.
# ---------------------------------------------------------------------------
@dataclass
class User:
    id: int
    username: str
    role: str = "member"      # "member" | "admin"
    disabled: bool = False


USERS = {
    "alice": User(id=1, username="alice", role="member"),
    "root": User(id=2, username="root", role="admin"),
    "banned": User(id=3, username="banned", role="member", disabled=True),
}
PASSWORD = "password123"  # same for all demo users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# ---------------------------------------------------------------------------
# Auth dependency - the thing tests will OVERRIDE.
# ---------------------------------------------------------------------------
def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    user = USERS.get(token)  # simplified: the "token" is the username
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.disabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User is disabled")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


# ---------------------------------------------------------------------------
# An external "notifier" service - the thing tests will MOCK with a fake.
# ---------------------------------------------------------------------------
@dataclass
class Notifier:
    sent: list = field(default_factory=list)

    def send(self, to: str, message: str) -> None:
        # A real one would hit email/SMS/push. We just record for the demo.
        self.sent.append((to, message))


_notifier = Notifier()


def get_notifier() -> Notifier:
    return _notifier


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
class UserOut(BaseModel):
    id: int
    username: str
    role: str


@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = USERS.get(form.username)
    if user is None or form.password != PASSWORD:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect credentials")
    # Simplified token: just the username (Lesson 29 uses real JWTs).
    return {"access_token": user.username, "token_type": "bearer"}


@app.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)):
    return user


@app.get("/admin/stats")
def admin_stats(admin: User = Depends(require_admin)):
    return {"total_users": len(USERS), "requested_by": admin.username}


class NotifyIn(BaseModel):
    to: str
    message: str


@app.post("/notify", status_code=status.HTTP_202_ACCEPTED)
def notify(
    payload: NotifyIn,
    user: User = Depends(get_current_user),
    notifier: Notifier = Depends(get_notifier),
):
    notifier.send(payload.to, payload.message)
    return {"status": "queued", "by": user.username}
