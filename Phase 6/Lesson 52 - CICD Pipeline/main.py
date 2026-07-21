"""
Lesson 52 - CI/CD Pipeline (the app the pipeline ships)
------------------------------------------------------
A minimal app. The real content is ci-cd.yml (the pipeline) and test_main.py
(what the pipeline's `test` stage runs before anything is built or deployed).
"""

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Lesson 52 - CI/CD")

ITEMS = {1: {"id": 1, "name": "Widget"}}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/items/{item_id}")
def get_item(item_id: int):
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    return item
