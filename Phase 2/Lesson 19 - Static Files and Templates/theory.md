# Lesson 19 — Static Files & Templates (Jinja2)

> **Goal of this lesson:** Serve CSS/JS/images directly from FastAPI, and render server-side HTML pages using Jinja2 templates — turning FastAPI into a full web server, not just an API.

---

## 0. Required Dependencies

```bash
pip install jinja2 aiofiles
```

- `jinja2` — the template engine
- `aiofiles` — required by FastAPI's `StaticFiles` for async file serving

---

## 1. Static Files — What and Why

**Static files** are files that don't change per-request: CSS, JavaScript, images, fonts, PDFs.

Instead of serving them through endpoint functions (slow, unnecessary), you **mount** a directory and FastAPI serves them directly:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```

Now any file inside `static/` is accessible at `/static/<filename>`:
- `static/style.css` → `http://localhost:8000/static/style.css`
- `static/logo.png` → `http://localhost:8000/static/logo.png`

### Mount vs Route

`app.mount()` is different from `app.get()`:
- Routes match a specific path.
- Mounts match a **path prefix** — everything under `/static/` is handled by `StaticFiles`.

---

## 2. Jinja2 Templates

**Jinja2** is Python's most popular HTML template engine. Instead of returning JSON, you return a rendered HTML page.

```
FastAPI endpoint
  → loads a .html template
  → fills in variables ({{ user.name }}, {% for item in items %})
  → returns complete HTML to the browser
```

### Setup

```python
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
```

### Returning a Template Response

```python
from fastapi import Request

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Home Page"},
    )
```

> ⚠️ **`request` is required** in the context dict. Jinja2 needs it to generate URLs.

---

## 3. Jinja2 Template Syntax

| Syntax | Purpose | Example |
|--------|---------|---------|
| `{{ variable }}` | Output a value | `{{ user.name }}` |
| `{% if ... %}` | Conditional | `{% if user.is_admin %}` |
| `{% for ... %}` | Loop | `{% for item in items %}` |
| `{% block ... %}` | Template inheritance | `{% block content %}` |
| `{% extends "base.html" %}` | Inherit from a base | Top of child template |
| `{% include "nav.html" %}` | Include a partial | Reusable components |
| `{{ url_for('static', path='/style.css') }}` | Generate static URL | In `<link>` tags |

---

## 4. Template Inheritance — The Right Way

Don't repeat `<html><head><body>` in every template. Create a `base.html`:

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}My App{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/style.css') }}">
</head>
<body>
    <nav>
        <a href="/">Home</a> | <a href="/items">Items</a>
    </nav>
    <main>
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

Child templates extend it:

```html
<!-- templates/index.html -->
{% extends "base.html" %}

{% block title %}Home{% endblock %}

{% block content %}
<h1>Welcome, {{ username }}!</h1>
{% endblock %}
```

---

## 5. Passing Data to Templates

Any JSON-serializable Python value can be passed:

```python
@app.get("/items")
def item_list(request: Request):
    items = [
        {"id": 1, "name": "Laptop",  "price": 999},
        {"id": 2, "name": "Monitor", "price": 299},
    ]
    return templates.TemplateResponse(
        "items.html",
        {"request": request, "items": items, "count": len(items)},
    )
```

```html
<!-- templates/items.html -->
{% extends "base.html" %}
{% block content %}
<h2>{{ count }} items</h2>
<ul>
  {% for item in items %}
    <li>{{ item.name }} — ${{ item.price }}</li>
  {% endfor %}
</ul>
{% endblock %}
```

---

## 6. Forms in Templates

HTML forms POST to FastAPI endpoints:

```html
<form method="POST" action="/items">
    <input type="text" name="name" placeholder="Item name" required>
    <input type="number" name="price" placeholder="Price" required>
    <button type="submit">Add Item</button>
</form>
```

```python
@app.post("/items")
def create_item(
    request: Request,
    name: str = Form(...),
    price: float = Form(...),
):
    items.append({"name": name, "price": price})
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/items", status_code=303)
```

`303 See Other` is the correct redirect status after a POST — it tells the browser to GET the redirect target (prevents re-submission on refresh).

---

## 7. `url_for()` — Generating URLs

Instead of hardcoding URLs in templates, use `url_for()`:

```html
<!-- static file -->
<link href="{{ url_for('static', path='/style.css') }}">

<!-- named route -->
<a href="{{ url_for('item_detail', item_id=item.id) }}">View</a>
```

In Python, generate URLs the same way:
```python
from fastapi import Request

@app.get("/items/{item_id}", name="item_detail")
def item_detail(item_id: int, request: Request):
    url = request.url_for("item_detail", item_id=item_id)
    ...
```

---

## 8. Template + JSON from the Same Endpoint

You can have separate HTML and JSON routes for the same data:

```python
# HTML version
@app.get("/items", response_class=HTMLResponse)
def items_page(request: Request):
    return templates.TemplateResponse("items.html", {"request": request, "items": db})

# JSON version (for API consumers)
@app.get("/api/items")
def items_api() -> list[ItemOut]:
    return list(db.values())
```

---

## 9. `HTMLResponse` Directly

For tiny HTML snippets without a template:

```python
from fastapi.responses import HTMLResponse

@app.get("/ping", response_class=HTMLResponse)
def ping():
    return "<h1>Pong!</h1>"
```

---

## 10. Real-World Use Case

A simple CRUD web app entirely inside FastAPI:

```
GET  /items        → renders items.html (list)
GET  /items/{id}   → renders item_detail.html (detail)
GET  /items/new    → renders item_form.html (empty form)
POST /items        → processes form, redirects to GET /items
GET  /items/{id}/edit → renders item_form.html (pre-filled)
POST /items/{id}   → processes update, redirects
```

No separate frontend framework needed — ideal for admin dashboards, internal tools, quick prototypes.

---

## 11. Mini Task

1. Run: `uvicorn main:app --reload`
2. Open `http://localhost:8000/` in a browser (not Swagger) — you should see the HTML page
3. Navigate to `/items` — styled list of items
4. Use the form to add a new item
5. Check that `/static/style.css` returns CSS directly
6. **Bonus:** Add a `GET /items/{id}` route that renders a detail page showing the item's full info.

---

## 12. Key Takeaways

- `app.mount("/static", StaticFiles(directory="static"))` serves files directly — no endpoint functions.
- `Jinja2Templates(directory="templates")` sets up the template engine.
- Always pass `"request": request` in the template context — it's required.
- Use `{% extends "base.html" %}` to avoid repeating HTML boilerplate.
- `url_for('static', path='/...')` generates correct static file URLs.
- After POST, redirect with `303 See Other` to avoid form re-submission.
- Templates are for HTML UIs; JSON endpoints still serve API consumers.

---

## ➡️ Next Lesson

**Lesson 20 — Database Concepts Refresher**
- SQL vs NoSQL
- What an ORM is and why we need one
- Connection pooling
- How FastAPI connects to a database
- Setting up SQLite for local development
