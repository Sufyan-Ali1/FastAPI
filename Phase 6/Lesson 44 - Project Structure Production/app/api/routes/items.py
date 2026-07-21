"""api/routes/items.py - the HTTP layer for items. THIN.

Each route: read validated input (schemas), call a service, return the result.
No business logic lives here - it delegates to services/item_service.py.
"""

from fastapi import APIRouter, status

from app.api.deps import DB
from app.schemas.item import ItemCreate, ItemRead
from app.services import item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemRead])
def list_items(db: DB):
    return item_service.list_items(db)


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, db: DB):
    return item_service.create_item(db, payload)      # delegate to the service


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int, db: DB):
    return item_service.get_item(db, item_id)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: DB):
    item_service.delete_item(db, item_id)
