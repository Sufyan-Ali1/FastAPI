"""Users router — all /users endpoints live here."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from models import UserCreate, UserOut, UserUpdate
from dependencies import get_current_user, pagination

router = APIRouter(prefix="/users", tags=["Users"])

# Fake DB
_db: dict[int, dict] = {}


@router.get("/", response_model=list[UserOut])
def list_users(pages: dict = Depends(pagination)):
    all_users = list(_db.values())
    start = pages["offset"]
    return all_users[start: start + pages["limit"]]


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    if any(u["email"] == user.email for u in _db.values()):
        raise HTTPException(status_code=409, detail="Email already registered")
    new_id = len(_db) + 1
    record = {"id": new_id, "created_at": datetime.now(), **user.model_dump()}
    _db[new_id] = record
    return record


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    user = _db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut, response_model_exclude_unset=True)
def update_user(user_id: int, updates: UserUpdate, current=Depends(get_current_user)):
    user = _db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.update(updates.model_dump(exclude_unset=True))
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, current=Depends(get_current_user)):
    if user_id not in _db:
        raise HTTPException(status_code=404, detail="User not found")
    del _db[user_id]
