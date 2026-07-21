"""services/item_service.py - the BUSINESS LOGIC layer.

Pure logic: no FastAPI, no HTTP, no routers. It takes a Session and plain
inputs, applies the rules, and returns model objects (or raises domain errors).
This is what makes the logic unit-testable and reusable.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.schemas.item import ItemCreate
from app.services.exceptions import DuplicateSKUError, ItemNotFoundError


def list_items(db: Session) -> list[Item]:
    return list(db.scalars(select(Item).order_by(Item.id)).all())


def get_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise ItemNotFoundError(item_id)   # domain error, NOT HTTPException
    return item


def create_item(db: Session, payload: ItemCreate) -> Item:
    # Business rule: SKU must be unique (checked in the service, not the route).
    if db.scalar(select(Item).where(Item.sku == payload.sku)) is not None:
        raise DuplicateSKUError(payload.sku)
    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: int) -> None:
    item = get_item(db, item_id)           # reuses get_item's not-found logic
    db.delete(item)
    db.commit()
