"""
Lesson 19 — Static Files & Templates (Jinja2)
-----------------------------------------------
Demonstrates:
  - app.mount() for serving a static directory
  - Jinja2Templates for server-side HTML rendering
  - Template inheritance (base.html → child templates)
  - Passing data to templates (variables, lists, dicts)
  - url_for() in templates for static files and named routes
  - HTML form → POST → 303 redirect pattern
  - Mixing HTML pages and JSON API endpoints

Install:
    pip install jinja2 aiofiles

Run:
    uvicorn main:app --reload

Open in BROWSER (not Swagger):
    http://localhost:8000/
"""

import sys
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Lesson 19 - Static Files & Templates")

# ── Static files ─────────────────────────────────────────────
# All files in static/ are served at /static/<filename>
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Jinja2 templates ─────────────────────────────────────────
templates = Jinja2Templates(directory="templates")

# ── Fake in-memory DB ────────────────────────────────────────
_next_id = 1
items_db: dict[int, dict] = {}


def next_id() -> int:
    global _next_id
    _id = _next_id
    _next_id += 1
    return _id


# Seed a couple of items so the page isn't empty on first load
items_db[next_id()] = {"id": 1, "name": "Laptop",  "price": 999.99, "category": "Electronics"}
items_db[next_id()] = {"id": 2, "name": "Notebook", "price": 4.99,  "category": "Stationery"}


# ============================================================
# HTML pages
# ============================================================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Renders index.html — shows app info and item count."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request":        request,
            "server":         "FastAPI + Uvicorn",
            "python_version": sys.version.split()[0],
            "item_count":     len(items_db),
        },
    )


@app.get("/items", response_class=HTMLResponse)
def items_page(request: Request, flash: str | None = None, flash_type: str = "success"):
    """
    Renders items.html — lists all items and shows an add form.
    Optional ?flash=... query param shows a flash message.
    """
    flash_data = {"message": flash, "type": flash_type} if flash else None
    return templates.TemplateResponse(
        "items.html",
        {
            "request": request,
            "items":   list(items_db.values()),
            "flash":   flash_data,
        },
    )


@app.post("/items")
def create_item(
    name:     str   = Form(..., min_length=1),
    price:    float = Form(..., gt=0),
    category: str   = Form(""),
):
    """
    Processes the HTML form. After inserting, redirects to GET /items.
    303 See Other → browser issues a GET, preventing form re-submission on refresh.
    """
    item_id = next_id()
    items_db[item_id] = {
        "id":       item_id,
        "name":     name.strip(),
        "price":    price,
        "category": category.strip() or None,
    }
    return RedirectResponse(
        url=f"/items?flash={name} added successfully!",
        status_code=303,
    )


@app.get("/items/{item_id}", response_class=HTMLResponse, name="item_detail")
def item_detail(item_id: int, request: Request):
    """Renders item_detail.html for a single item."""
    item = items_db.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return templates.TemplateResponse(
        "item_detail.html",
        {"request": request, "item": item},
    )


@app.post("/items/{item_id}/delete")
def delete_item(item_id: int):
    """Deletes an item and redirects back to the list."""
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    name = items_db[item_id]["name"]
    del items_db[item_id]
    return RedirectResponse(
        url=f"/items?flash={name} deleted.&flash_type=error",
        status_code=303,
    )


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


# ============================================================
# JSON API endpoints (same data, different format)
# ============================================================

@app.get("/api/items")
def api_items():
    """JSON version for API consumers — same DB, different response format."""
    return list(items_db.values())


@app.get("/api/items/{item_id}")
def api_item(item_id: int):
    item = items_db.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


# ── Tiny inline HTML (no template needed) ───────────────────
@app.get("/ping", response_class=HTMLResponse)
def ping():
    return "<h1 style='font-family:sans-serif'>🏓 Pong!</h1>"
