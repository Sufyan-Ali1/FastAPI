"""Shared dependencies used across multiple routers."""

from fastapi import Depends, HTTPException, Query, status

# Fake user store
FAKE_USERS = {
    "user":  {"id": 1, "name": "Sufyan", "is_admin": False},
    "admin": {"id": 2, "name": "Admin",  "is_admin": True},
}


def get_current_user(token: str = Query(..., description="Use 'user' or 'admin'")):
    user = FAKE_USERS.get(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user


def require_admin(user: dict = Depends(get_current_user)):
    if not user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def pagination(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
) -> dict:
    return {"page": page, "limit": limit, "offset": (page - 1) * limit}
