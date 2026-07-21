"""schemas/item.py - the Pydantic API contract (request/response shapes).

Separate from the SQLAlchemy model (Lesson 23). Defines what comes IN and OUT.
"""

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    sku: str = Field(..., min_length=3, max_length=30)
    price: float = Field(..., gt=0)


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sku: str
    price: float
