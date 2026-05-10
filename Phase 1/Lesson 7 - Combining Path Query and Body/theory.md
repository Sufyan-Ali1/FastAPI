# Lesson 7 — Combining Path + Query + Body

> **Goal of this lesson:** Use **all three input sources** — path, query, and body — in a **single endpoint**, and understand exactly how FastAPI decides which is which.

---

## 1. The Big Picture

A real REST endpoint often needs all three at once:

```
PUT /users/42/posts/9?notify=true
Content-Type: application/json

{
  "title": "Updated post",
  "content": "..."
}
```

| Source | Example | What it represents |
|--------|---------|--------------------|
| **Path** | `/users/42/posts/9` | *Which* resource (IDs) |
| **Query** | `?notify=true` | *How* / a flag / a filter |
| **Body** | `{ "title": "...", "content": "..." }` | The actual data |

In FastAPI, this is just **one function** with parameters from all three sources.

---

## 2. The Rule FastAPI Uses

FastAPI looks at every function parameter and decides where it comes from with this exact priority:

```
1. If the parameter name matches a {placeholder} in the URL path
        → it is a PATH parameter

2. Otherwise, if the type is a Pydantic BaseModel (or a body type)
        → it is a BODY parameter

3. Otherwise (str, int, float, bool, list, etc.)
        → it is a QUERY parameter
```

That's it. **You don't tag anything manually** — FastAPI figures it out from the URL pattern and the type hint.

---

## 3. A Complete Example

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

class PostUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str

@app.put("/users/{user_id}/posts/{post_id}")
def update_post(
    user_id: int,            # in URL path → PATH param
    post_id: int,            # in URL path → PATH param
    notify: bool = False,    # not in path, simple type → QUERY param
    post: PostUpdate = ...,  # not in path, Pydantic model → BODY param
):
    return {
        "user_id": user_id,
        "post_id": post_id,
        "notify": notify,
        "updated": post,
    }
```

Send:
```
PUT /users/42/posts/9?notify=true
{
  "title": "Hello",
  "content": "world"
}
```

You get back all four pieces neatly typed.

---

## 4. Order of Parameters in the Function

**Order does NOT affect routing.** FastAPI matches by name + type, not position.

But Python has a rule: **arguments without defaults must come before arguments with defaults.**

```python
# ❌ Python error — required arg after optional one
def update(user_id: int, notify: bool = False, post: PostUpdate):
    ...

# ✅ Required first, then optional
def update(user_id: int, post: PostUpdate, notify: bool = False):
    ...
```

If you ever need to *break* that order (e.g. force keyword-only), use `Annotated[...]` (modern style) or put `*,` before optional args.

---

## 5. Multiple Body Parameters

You can declare **more than one** Pydantic model as body. FastAPI will expect a JSON object that **wraps each** under its parameter name:

```python
class User(BaseModel):
    name: str
    email: str

class Item(BaseModel):
    title: str
    price: float

@app.post("/orders")
def create_order(user: User, item: Item):
    return {"user": user, "item": item}
```

Expected JSON:
```json
{
  "user":  { "name": "Sufyan", "email": "x@y.com" },
  "item":  { "title": "Laptop", "price": 999.99 }
}
```

Notice: NOT a flat `{name, email, title, price}` — each model becomes its **own key**.

---

## 6. Singular Body Values with `Body()`

What if you want a **single primitive** (like an `int` or a `str`) inside the JSON body, instead of a query param?

By default, a parameter like `priority: int` becomes a **query param**. To force it into the body, wrap it in `Body()`:

```python
from fastapi import Body

@app.post("/orders")
def create_order(
    user: User,
    item: Item,
    priority: int = Body(..., ge=1, le=5),   # ← forces this into the JSON body
):
    return {"user": user, "item": item, "priority": priority}
```

JSON the client must send:
```json
{
  "user":  { ... },
  "item":  { ... },
  "priority": 3
}
```

`Body()` accepts the same validators as `Query()` and `Field()`: `ge`, `le`, `min_length`, `pattern`, etc.

---

## 7. `Body(..., embed=True)` — One Model, Wrapped

When you have **only one** body model, FastAPI sends the JSON **flat**:

```python
@app.post("/users")
def create_user(user: User):
    ...
# Expected: { "name": "...", "email": "..." }
```

Sometimes you want it wrapped under a key for consistency:

```python
@app.post("/users")
def create_user(user: User = Body(..., embed=True)):
    ...
# Expected: { "user": { "name": "...", "email": "..." } }
```

`embed=True` is rare but useful when your frontend expects a wrapping key.

---

## 8. Putting It All Together (Cheat Sheet)

```python
@app.put("/users/{user_id}/posts/{post_id}")
def update_post(
    # PATH (in the URL pattern)
    user_id: int,
    post_id: int,

    # QUERY (simple types, NOT in path)
    notify: bool = False,
    lang: str = "en",

    # BODY (Pydantic model)
    post: PostUpdate,

    # BODY (forced primitive)
    priority: int = Body(1, ge=1, le=5),
):
    ...
```

| Parameter   | Source | Why |
|-------------|--------|-----|
| `user_id`   | path   | name matches `{user_id}` |
| `post_id`   | path   | name matches `{post_id}` |
| `notify`    | query  | not in path + simple type |
| `lang`      | query  | not in path + simple type |
| `post`      | body   | Pydantic model |
| `priority`  | body   | wrapped in `Body()` |

---

## 9. Common Mistakes

| Mistake | What happens | Fix |
|---------|--------------|-----|
| Param name doesn't match path placeholder | FastAPI thinks it's a query param | Match exactly: `{user_id}` ↔ `user_id` |
| Two Pydantic models, but client sent flat JSON | 422 — missing fields | Send `{"user": {...}, "item": {...}}` |
| Single primitive expected in body but written as `int` directly | FastAPI puts it in query | Use `Body(...)` |
| Required body param after a default-valued query param | Python `SyntaxError` | Reorder: required first |

---

## 10. Real-World Use Case

A **PATCH for a comment** on a blog:

```
PATCH /posts/{post_id}/comments/{comment_id}?notify_author=true
{
  "comment": { "text": "Edited!" },
  "edited_by": { "user_id": 42, "reason": "typo" }
}
```

```python
class CommentUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)

class EditMeta(BaseModel):
    user_id: int
    reason: str | None = None

@app.patch("/posts/{post_id}/comments/{comment_id}")
def edit_comment(
    post_id: int,
    comment_id: int,
    notify_author: bool = False,
    comment: CommentUpdate,
    edited_by: EditMeta,
):
    return {
        "post_id": post_id,
        "comment_id": comment_id,
        "notify_author": notify_author,
        "comment": comment,
        "edited_by": edited_by,
    }
```

One endpoint. Three input sources. Fully validated. Auto-documented.

---

## 11. Mini Task

Open `main.py` in this lesson folder:

1. Run: `uvicorn main:app --reload`
2. Test in `/docs`:
   - **PUT `/users/{user_id}/posts/{post_id}`** — try it with a body, query flag, and path IDs
   - **POST `/orders`** — send `{ "user": {...}, "item": {...} }` (notice the wrapping)
   - **POST `/orders-with-priority`** — same, plus a `priority` field at the top level
3. **Bonus:** Add an endpoint `PUT /products/{product_id}` that takes:
   - `product_id` (path, int, ≥ 1)
   - `notify` (query, bool, default False)
   - A body with `name` (≥ 1 char) and `price` (> 0)
   - A body field `updated_by` (forced via `Body()`, str, ≥ 2 chars)

---

## 12. Key Takeaways

- FastAPI infers source from **path placeholders** + **type hints**.
- Path → name in URL. Body → Pydantic / `Body()`. Query → everything else.
- Multiple body models → JSON nests each under its name.
- `Body(...)` forces a primitive into the body.
- `Body(..., embed=True)` wraps a single model under a key.
- Order in the function signature **doesn't affect routing**, only Python rules.

---

## ➡️ Next Lesson

**Lesson 8 — Response Basics**
- Auto JSON conversion
- Setting status codes (`status_code=`)
- `JSONResponse` vs returning a dict
- A peek at `response_model`
