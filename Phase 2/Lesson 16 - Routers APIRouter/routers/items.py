"""Items router — all /items endpoints live here."""

from fastapi import APIRouter, Depends, HTTPException, status
from models import ItemCreate, ItemOut
from dependencies import get_current_user, pagination

router = APIRouter(prefix="/items", tags=["Items"])

_db: dict[int, dict] = {}


@router.get("/", response_model=list[ItemOut])
def list_items(pages: dict = Depends(pagination)):
    all_items = list(_db.values())
    start = pages["offset"]
    return all_items[start: start + pages["limit"]]


@router.post("/", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate, current=Depends(get_current_user)):
    new_id = len(_db) + 1
    record = {"id": new_id, **item.model_dump()}
    _db[new_id] = record
    return record


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int):
    item = _db.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, current=Depends(get_current_user)):
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Item not found")
    del _db[item_id]
