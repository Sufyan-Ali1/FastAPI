"""Shared Pydantic models used across all routers."""

from pydantic import BaseModel, Field
from datetime import datetime


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    email: str | None = Field(None, pattern=r"^[^@]+@[^@]+\.[^@]+$")


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)


class ItemOut(BaseModel):
    id: int
    name: str
    price: float
