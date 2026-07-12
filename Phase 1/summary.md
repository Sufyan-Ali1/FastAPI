# Phase 1 Summary - FastAPI Fundamentals

This file is a revision guide for Phase 1. Its goal is to help you recall the full mental model after a break without rereading every lesson.

Phase 1 teaches the foundation of FastAPI:

- What FastAPI is and how it works internally.
- How to set up and run a FastAPI project.
- How HTTP methods and RESTful APIs work.
- How FastAPI reads path parameters, query parameters, and request bodies.
- How Pydantic validates data.
- How responses, status codes, headers, and errors work.

The most important idea in Phase 1:

FastAPI uses Python function signatures plus type hints to understand the HTTP request, validate incoming data, generate API docs, and serialize the response.

---

## 1. Big Picture Mental Model

A FastAPI app is an ASGI web application.

When a request comes in:

1. The client sends an HTTP request.
2. Uvicorn receives the network request.
3. Uvicorn talks to the FastAPI app using the ASGI protocol.
4. Starlette handles low-level web framework behavior like routing, requests, responses, and middleware.
5. FastAPI matches the request to the correct route function.
6. FastAPI inspects the route function parameters.
7. Pydantic validates and converts incoming data.
8. Your endpoint function runs.
9. FastAPI serializes the returned Python value into JSON.
10. Uvicorn sends the HTTP response back to the client.

Important tools:

| Tool | Job |
|---|---|
| FastAPI | Main framework. Provides decorators, validation integration, docs, dependency system later. |
| Starlette | Web foundation. Handles routing, request/response objects, middleware, ASGI behavior. |
| Pydantic | Data validation, type conversion, serialization, schemas. |
| Uvicorn | ASGI server. Runs the app and handles real HTTP traffic. |
| ASGI | The protocol between async Python web servers and apps. |

FastAPI's "magic" is not magic. It mostly comes from:

- Python type hints.
- Pydantic validation.
- Starlette routing.
- OpenAPI schema generation.

One type hint can give three benefits:

- Runtime validation.
- Editor/autocomplete help.
- Swagger/OpenAPI documentation.

---

## 2. Lesson 1 - What Is FastAPI?

FastAPI is a modern Python web framework for building APIs.

It is designed for:

- Fast development.
- Automatic validation.
- Automatic API docs.
- Async support.
- Clean Python type-hint based code.

Basic app shape:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}
```

Core ideas:

- `app = FastAPI()` creates the application object.
- `@app.get("/")` registers a route.
- The function below the decorator is called when that route receives a matching request.
- Returning a `dict` automatically becomes a JSON response.
- `/docs` gives Swagger UI.
- `/redoc` gives ReDoc.
- OpenAPI schema is available at `/openapi.json`.

Why FastAPI exists:

- Flask is flexible but does not provide built-in validation and docs in the same integrated way.
- Django REST Framework is powerful but heavier and more opinionated.
- FastAPI combines modern Python type hints, high performance, automatic validation, and automatic docs.

Important mental model:

FastAPI is mainly an API framework. It is usually used for backends that serve JSON to frontends, mobile apps, other services, AI apps, dashboards, and automation tools.

---

## 3. Lesson 2 - Installation and Setup

A FastAPI project needs:

- Python.
- A virtual environment.
- FastAPI package.
- Uvicorn server.
- A `main.py` file with `app = FastAPI()`.

Basic setup:

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install fastapi uvicorn
uvicorn main:app --reload
```

Meaning of `uvicorn main:app --reload`:

| Part | Meaning |
|---|---|
| `uvicorn` | Run the ASGI server. |
| `main` | Python file name, `main.py`. |
| `app` | FastAPI object inside `main.py`. |
| `--reload` | Restart server automatically when code changes. |

Use `--reload` only in development.

Do not use `--reload` in production because:

- It watches files continuously.
- It restarts the server on file changes.
- It can interrupt requests.
- It is meant for local development, not stable production serving.

Virtual environment purpose:

- Keeps dependencies isolated per project.
- Prevents version conflicts between projects.
- Makes the project reproducible.

`requirements.txt` purpose:

- Records installed package versions.
- Lets another machine recreate the same environment with:

```bash
pip install -r requirements.txt
```

Health check endpoint:

```python
@app.get("/health")
def health_check():
    return {"status": "ok"}
```

Why health checks matter:

- Servers, load balancers, Docker, Kubernetes, and cloud platforms can check if the app is alive.

---

## 4. Lesson 3 - HTTP Methods and REST

HTTP methods describe what action the client wants to perform.

| Method | Main Meaning | Common Use |
|---|---|---|
| GET | Read data | List or fetch resources |
| POST | Create data | Create a new resource |
| PUT | Replace/update data | Replace a full resource |
| PATCH | Partially update data | Update selected fields |
| DELETE | Remove data | Delete a resource |

FastAPI maps HTTP methods to decorators:

```python
@app.get("/items")
def list_items():
    ...

@app.post("/items")
def create_item():
    ...

@app.put("/items/{item_id}")
def update_item(item_id: int):
    ...

@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    ...
```

REST means designing APIs around resources.

Good REST URL examples:

| URL | Meaning |
|---|---|
| `GET /posts` | List posts |
| `POST /posts` | Create a post |
| `GET /posts/5` | Get post 5 |
| `PUT /posts/5` | Replace post 5 |
| `DELETE /posts/5` | Delete post 5 |
| `GET /users/3/posts` | Get posts for user 3 |

REST principles:

| Principle | Meaning |
|---|---|
| Client-server | Frontend/client and backend/server have separate jobs. |
| Stateless | Every request must contain all needed context. |
| Cacheable | Responses can define whether they may be cached. |
| Uniform interface | Use consistent resource URLs and HTTP methods. |
| Layered system | Client does not need to know if proxies/gateways exist between it and the server. |
| Code on demand | Optional. Server may send executable code, less common in APIs. |

Statelessness is critical:

- Do not store the "current user" in a global variable.
- Each request should carry auth/session context itself, usually through headers, cookies, or tokens.
- Stateless APIs scale better because any server instance can handle any request.

Idempotency:

| Method | Safe? | Idempotent? | Meaning |
|---|---:|---:|---|
| GET | Yes | Yes | Reading should not change state. |
| POST | No | Usually no | Calling twice may create two records. |
| PUT | No | Yes | Replacing with same data repeatedly leaves same final state. |
| DELETE | No | Yes | Deleting twice leaves resource deleted. |
| PATCH | No | Not guaranteed | Depends on patch behavior. |

Safe means no state change.

Idempotent means repeating the same request has the same final server state.

Important: idempotency is about final state, not always identical response status. `DELETE /items/5` can return `204` first and `404` second, but the resource is still gone both times.

Status code basics:

| Status | Meaning |
|---|---|
| 200 OK | Successful read/update. |
| 201 Created | New resource created. |
| 204 No Content | Successful delete with empty body. |
| 400 Bad Request | Bad request syntax or general bad input. |
| 401 Unauthorized | Authentication missing or invalid. |
| 403 Forbidden | Authenticated but not allowed. |
| 404 Not Found | Resource does not exist. |
| 409 Conflict | Request conflicts with current state, like duplicate email. |
| 422 Unprocessable Entity | Request parsed, but validation failed. |
| 500 Internal Server Error | Unexpected server bug. |

Why FastAPI often returns 422:

- The HTTP request was understood.
- The data inside it failed validation.
- Example: `age` expected `int`, but client sent `"abc"`.

---

## 5. Lesson 4 - Path Parameters

A path parameter is part of the URL path and identifies a specific resource.

Example:

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}
```

Request:

```text
GET /users/42
```

FastAPI:

- Captures `"42"` from the URL.
- Converts it to `int`.
- Passes `42` into `get_user`.
- Returns 422 if conversion fails.

Use path parameters when the value identifies a resource:

- `/users/5`
- `/posts/10`
- `/users/5/posts/2`

Do not use path parameters for optional filters. Use query parameters for filters.

Type conversion examples:

| Type Hint | URL Value | Python Value |
|---|---|---|
| `int` | `"5"` | `5` |
| `float` | `"9.99"` | `9.99` |
| `bool` | `"true"` | `True` |
| `str` | `"abc"` | `"abc"` |

Validation with `Path()`:

```python
from fastapi import Path

@app.get("/users/{user_id}")
def get_user(user_id: int = Path(..., ge=1, le=1000)):
    return {"user_id": user_id}
```

Important `Path()` ideas:

- `...` means required.
- Path parameters are always required because they are part of the URL.
- `ge=1` means greater than or equal to 1.
- `le=1000` means less than or equal to 1000.
- `gt` and `lt` mean strict greater than and strict less than.
- `title` and `description` improve docs.

Route order matters:

```python
@app.get("/users/me")
def read_current_user():
    ...

@app.get("/users/{user_id}")
def get_user(user_id: int):
    ...
```

Static routes should come before dynamic routes.

If `/users/{user_id}` is declared before `/users/me`, then `/users/me` may match the dynamic route first, and FastAPI will try to parse `"me"` as an `int`.

Multiple path parameters:

```python
@app.get("/users/{user_id}/posts/{post_id}")
def get_user_post(user_id: int, post_id: int):
    return {"user_id": user_id, "post_id": post_id}
```

Enum path parameters:

```python
from enum import Enum

class Size(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"

@app.get("/sizes/{size}")
def get_size(size: Size):
    return {"size": size}
```

Why use `Enum`:

- Restricts allowed values.
- Shows dropdown choices in Swagger UI.
- Prevents invalid values before business logic runs.

Path containing slashes:

```python
@app.get("/files/{file_path:path}")
def read_file(file_path: str):
    return {"file_path": file_path}
```

Normal path parameters capture one URL segment.

`{file_path:path}` captures multiple segments, including slashes.

Example:

```text
/files/home/user/notes.txt
```

Gives:

```json
{"file_path": "home/user/notes.txt"}
```

---

## 6. Lesson 5 - Query Parameters

A query parameter comes after `?` in the URL.

Example:

```text
/items?limit=10&in_stock=true
```

Query parameters are best for:

- Filtering.
- Searching.
- Sorting.
- Pagination.
- Optional flags.
- Client preferences.

Basic example:

```python
@app.get("/items")
def list_items(limit: int = 10, in_stock: bool = True):
    return {"limit": limit, "in_stock": in_stock}
```

FastAPI detects query parameters when:

- The parameter name is not in the path.
- The type is a simple type like `str`, `int`, `float`, `bool`, list, etc.
- It is not a Pydantic model body.

Required vs optional:

```python
def list_products(category: str, page: int = 1):
    ...
```

- `category` is required because it has no default.
- `page` is optional because it has a default.

Optional with `None`:

```python
def list_users(role: str | None = None):
    ...
```

- `/users` gives `role = None`.
- `/users?role=admin` gives `role = "admin"`.

Do not write:

```python
role: str = None
```

This says the type is `str`, but the default is `None`. In modern Pydantic, the type should explicitly allow `None`:

```python
role: str | None = None
```

Type conversion:

```text
/items?limit=5&in_stock=false&price=19.99
```

Can become:

```python
limit = 5          # int
in_stock = False   # bool
price = 19.99      # float
```

Bool query values FastAPI commonly understands:

- `true`, `1`, `yes`, `on` become `True`.
- `false`, `0`, `no`, `off` become `False`.
- Invalid values like `maybe` return 422.

Validation with `Query()`:

```python
from fastapi import Query

@app.get("/search")
def search(
    q: str = Query(..., min_length=3, max_length=50),
    page: int = Query(1, ge=1, le=1000),
):
    return {"q": q, "page": page}
```

Important `Query()` ideas:

- `Query(...)` means required.
- `Query(None)` means optional.
- `Query(1)` means optional with default value `1`.
- Constraints like `min_length`, `max_length`, `ge`, `le`, and `pattern` validate the value.
- Metadata like `title`, `description`, and `examples` improves docs.

List query parameters:

```python
from typing import Annotated
from fastapi import Query

@app.get("/items-by-tags")
def items_by_tags(tags: Annotated[list[str] | None, Query()] = None):
    return {"tags": tags}
```

Client sends:

```text
/items-by-tags?tags=python&tags=fastapi
```

FastAPI gives:

```python
tags = ["python", "fastapi"]
```

Path vs query:

| Use Path When | Use Query When |
|---|---|
| The value identifies a resource. | The value filters or modifies a result. |
| It is required for the URL to make sense. | It is optional or changes how data is returned. |
| Example: `/users/5` | Example: `/users?role=admin` |

Combined path and query:

```python
@app.get("/users/{user_id}/posts")
def list_user_posts(user_id: int, published: bool = True, limit: int = 10):
    return {"user_id": user_id, "published": published, "limit": limit}
```

Request:

```text
/users/5/posts?published=false&limit=20
```

---

## 7. Lesson 6 - Request Body and Pydantic

A request body is data sent inside the HTTP request, usually as JSON.

It is commonly used with:

- POST.
- PUT.
- PATCH.

Example JSON body:

```json
{
  "name": "Laptop",
  "price": 999.99
}
```

Problem with raw `dict`:

```python
@app.post("/items")
def create_item(item: dict):
    return item
```

Using `dict` loses:

- Field validation.
- Type conversion.
- Required field checks.
- Nested validation.
- Good Swagger schema.
- Editor autocomplete.
- Clear contract for the client.

Pydantic solves this.

Basic model:

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: str
    age: int = Field(..., ge=0, le=120)
    bio: str | None = None
```

Endpoint:

```python
@app.post("/users")
def create_user(user: User):
    return {"message": "User created", "user": user}
```

FastAPI sees `user: User` where `User` extends `BaseModel`, so it reads JSON from the request body and validates it.

Common field types:

| Type | Meaning |
|---|---|
| `str` | Text |
| `int` | Integer |
| `float` | Decimal number |
| `bool` | True/false |
| `list[str]` | List of strings |
| `dict` | Object/dictionary |
| `str | None` | String or null |
| nested `BaseModel` | Nested object |

Required vs optional in Pydantic:

```python
name: str
```

Required. Client must send it.

```python
name: str = "Anonymous"
```

Optional. Default is `"Anonymous"`.

```python
bio: str | None = None
```

Optional and nullable.

```python
bio: str | None
```

Required key, but value may be `null`.

`Field()` validation:

```python
name: str = Field(..., min_length=2, max_length=50)
age: int = Field(..., ge=13)
price: float = Field(..., gt=0)
email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
```

Common constraints:

| Constraint | Meaning |
|---|---|
| `min_length` | Minimum string length |
| `max_length` | Maximum string length |
| `gt` | Greater than |
| `ge` | Greater than or equal |
| `lt` | Less than |
| `le` | Less than or equal |
| `pattern` | Regex pattern |
| `description` | Docs text |
| `examples` | Docs examples |

Nested models:

```python
class ProductDetails(BaseModel):
    color: str
    weight_kg: float = Field(..., gt=0)
    in_stock: bool = True

class Product(BaseModel):
    name: str
    price: float = Field(..., gt=0)
    tags: list[str] = []
    details: ProductDetails
```

Client body:

```json
{
  "name": "Phone",
  "price": 500,
  "tags": ["electronics"],
  "details": {
    "color": "black",
    "weight_kg": 0.3,
    "in_stock": true
  }
}
```

Nested validation is automatic. If `details.weight_kg` is invalid, FastAPI returns a 422 pointing to that nested field.

Returning a Pydantic model:

```python
class EchoResponse(BaseModel):
    received: dict
    success: bool = True

@app.post("/echo", response_model=EchoResponse)
def echo(payload: dict):
    return EchoResponse(received=payload)
```

FastAPI serializes the Pydantic model into JSON.

---

## 8. Lesson 7 - Combining Path, Query, and Body

FastAPI decides where data comes from using this rule:

1. If the parameter name appears in the path string, it is a path parameter.
2. If the parameter type is a Pydantic `BaseModel`, it is a request body.
3. Otherwise, simple types are query parameters.

Example:

```python
class PostUpdate(BaseModel):
    title: str
    content: str

@app.put("/users/{user_id}/posts/{post_id}")
def update_post(
    user_id: int,
    post_id: int,
    post: PostUpdate,
    notify: bool = False,
):
    return {
        "user_id": user_id,
        "post_id": post_id,
        "notify": notify,
        "updated": post,
    }
```

Request:

```text
PUT /users/42/posts/9?notify=true
```

Body:

```json
{
  "title": "Hello",
  "content": "World"
}
```

FastAPI reads:

- `user_id` from path.
- `post_id` from path.
- `notify` from query.
- `post` from body.

Function parameter order:

Python requires non-default parameters before default parameters.

Invalid:

```python
def f(optional: bool = False, required: int):
    ...
```

Valid:

```python
def f(required: int, optional: bool = False):
    ...
```

Multiple body models:

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
  "user": {
    "name": "Sufyan",
    "email": "x@y.com"
  },
  "item": {
    "title": "Laptop",
    "price": 999.99
  }
}
```

When there are multiple body parameters, FastAPI wraps each one under the parameter name.

Primitive values normally become query parameters:

```python
def create_order(priority: int):
    ...
```

`priority` is treated as query:

```text
/orders?priority=3
```

Force a primitive into the body with `Body()`:

```python
from fastapi import Body

@app.post("/orders-with-priority")
def create_order_with_priority(
    user: User,
    item: Item,
    priority: int = Body(..., ge=1, le=5),
):
    return {"user": user, "item": item, "priority": priority}
```

Expected JSON:

```json
{
  "user": {...},
  "item": {...},
  "priority": 3
}
```

`Body(embed=True)`:

Normally, a single body model is sent directly:

```json
{
  "name": "Sufyan",
  "email": "x@y.com"
}
```

With `embed=True`:

```python
@app.post("/users-embedded")
def create_user_embedded(user: User = Body(..., embed=True)):
    return {"received": user}
```

Expected JSON:

```json
{
  "user": {
    "name": "Sufyan",
    "email": "x@y.com"
  }
}
```

Common mistake:

If the client sends `"priority"` inside JSON but the endpoint has `priority: int` without `Body()`, FastAPI will ignore the body value and look for `?priority=...` in the query string.

---

## 9. Lesson 8 - Response Basics

FastAPI automatically converts many Python values to JSON:

- `dict`
- `list`
- Pydantic models
- lists of Pydantic models
- supported special types like `datetime` in later use cases

Basic response:

```python
@app.get("/")
def root():
    return {"message": "Hello"}
```

The returned `dict` becomes JSON with status `200 OK`.

Set a status code on the decorator:

```python
from fastapi import status

@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate):
    return item
```

Use the `status` module because names are clearer than raw numbers.

Common response status codes:

| Status | Use |
|---|---|
| `200 OK` | Standard success |
| `201 Created` | Resource created |
| `204 No Content` | Success with empty body |
| `400 Bad Request` | Bad request |
| `401 Unauthorized` | Missing/invalid auth |
| `403 Forbidden` | Not allowed |
| `404 Not Found` | Missing resource |
| `409 Conflict` | Duplicate/conflicting state |
| `422 Unprocessable Entity` | Validation error |
| `500 Internal Server Error` | Server bug |

Returning a Pydantic model:

```python
class ItemOut(BaseModel):
    id: int
    name: str
    price: float

@app.get("/items/{item_id}")
def get_item(item_id: int) -> ItemOut:
    return {"id": item_id, "name": "Pen", "price": 1.5}
```

The return type hint helps humans and tools, but `response_model` is a stronger response contract in Phase 2.

Raise errors with `HTTPException`:

```python
from fastapi import HTTPException, status

@app.get("/items/{item_id}")
def get_item(item_id: int):
    item = db.get(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )
    return item
```

Why raise instead of return an error dict:

- It sets the correct HTTP status code.
- It stops the endpoint immediately.
- It creates a standard FastAPI error response.

Do not do this:

```python
return {"error": "not found"}, 404
```

FastAPI will serialize it as a tuple/list-like response and may still return 200. Use `HTTPException`.

`JSONResponse`:

```python
from fastapi.responses import JSONResponse

return JSONResponse(
    content={"message": "I'm a teapot"},
    status_code=418,
    headers={"X-Tea": "Earl Grey"},
)
```

Use `JSONResponse` when you need full manual control over:

- Response content.
- Dynamic status code.
- Custom headers.

Important difference:

`return {"x": 1}` goes through FastAPI's normal response pipeline.

`return JSONResponse(...)` is already a response object and gives you more control, but bypasses some automatic behavior.

Injected `Response` object:

```python
from fastapi import Response

@app.get("/with-headers")
def with_headers(response: Response):
    response.headers["X-Powered-By"] = "FastAPI"
    return {"message": "Check headers"}
```

Use injected `Response` when you want to keep normal FastAPI serialization but modify:

- Status code.
- Headers.
- Cookies.

Conditional status with `Response`:

```python
@app.post("/signup")
def signup(response: Response):
    response.status_code = 201
    response.headers["X-User-Id"] = "1"
    return {"message": "created"}
```

Cookies:

```python
response.set_cookie(key="theme", value="dark")
response.delete_cookie("theme")
```

204 No Content:

```python
@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    del db[item_id]
```

Do not return a body with 204.

Wrong:

```python
@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    return {"deleted": item_id}
```

204 means the response body must be empty.

---

## 10. FastAPI Parameter Decision Rule

This is one of the most important Phase 1 rules.

For every endpoint function parameter:

| Rule | Source |
|---|---|
| Name appears in path, like `{user_id}` | Path parameter |
| Type is a Pydantic `BaseModel` | Request body |
| Simple type not in path | Query parameter |
| Simple type with `Body()` | Request body |
| Parameter using `Header()`, `Cookie()`, etc. | Special request source, covered later |

Example:

```python
@app.put("/users/{user_id}")
def update_user(
    user_id: int,
    user: UserUpdate,
    notify: bool = False,
    priority: int = Body(...),
):
    ...
```

FastAPI reads:

- `user_id` from path.
- `user` from JSON body.
- `notify` from query.
- `priority` from body because `Body()` forces it.

---

## 11. Path vs Query vs Body

| Source | Best For | Example |
|---|---|---|
| Path | Resource identity | `/users/5` |
| Query | Filters, pagination, optional behavior | `/users?role=admin&page=2` |
| Body | Complex data being created or updated | JSON user/product/order data |

Use path when the endpoint cannot make sense without that value.

Use query when the value changes how results are selected or returned.

Use body when sending structured data.

Example full endpoint:

```python
@app.put("/teams/{team_id}/members/{member_id}")
def update_member(
    team_id: int = Path(..., ge=1),
    member_id: int = Path(..., ge=1),
    update: MemberUpdate,
    active: bool = True,
    note: str | None = Body(None, max_length=200),
):
    ...
```

Sources:

- `team_id`: path.
- `member_id`: path.
- `update`: body model.
- `active`: query.
- `note`: body primitive.

---

## 12. Required, Optional, and Nullable

This is a common source of confusion.

In function parameters:

```python
q: str
```

Required query parameter.

```python
q: str = "default"
```

Optional query parameter with default.

```python
q: str | None = None
```

Optional query parameter that can be absent.

In Pydantic models:

```python
name: str
```

Required field.

```python
name: str = "Anonymous"
```

Optional field with default.

```python
bio: str | None = None
```

Optional and nullable.

```python
bio: str | None
```

Required key, but value may be `null`.

```python
bio: str = None
```

Bad pattern in modern code. The type says `str`, but the default says `None`.

---

## 13. Validation Error Mental Model

When request data is invalid, FastAPI usually returns 422.

Examples:

- Missing required query parameter.
- Invalid path parameter type.
- Body field missing.
- Body field has wrong type.
- `Field()` constraint failed.
- `Query()` or `Path()` constraint failed.

FastAPI's validation response points to the source:

- `path`
- `query`
- `body`

Example:

If endpoint expects:

```python
@app.get("/items/{item_id}")
def get_item(item_id: int):
    ...
```

Request:

```text
/items/abc
```

FastAPI matches the route, then fails converting `"abc"` to `int`, and returns 422.

---

## 14. Common Mistakes and Fixes

### Mistake 1: Static route declared after dynamic route

Wrong:

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    ...

@app.get("/users/me")
def current_user():
    ...
```

Fix:

```python
@app.get("/users/me")
def current_user():
    ...

@app.get("/users/{user_id}")
def get_user(user_id: int):
    ...
```

Static routes first, dynamic routes second.

### Mistake 2: Returning tuple for status code

Wrong:

```python
return {"error": "not found"}, 404
```

Fix:

```python
raise HTTPException(status_code=404, detail="Not found")
```

### Mistake 3: Returning body with 204

Wrong:

```python
@app.delete("/items/{id}", status_code=204)
def delete_item(id: int):
    return {"deleted": id}
```

Fix:

```python
@app.delete("/items/{id}", status_code=204)
def delete_item(id: int):
    return
```

### Mistake 4: Expecting primitive values in body without `Body()`

Wrong:

```python
def create_order(user: User, priority: int):
    ...
```

`priority` becomes query.

Fix:

```python
def create_order(user: User, priority: int = Body(...)):
    ...
```

### Mistake 5: Using `dict` instead of Pydantic model

Wrong:

```python
def create_user(user: dict):
    ...
```

Fix:

```python
class UserCreate(BaseModel):
    name: str
    age: int

def create_user(user: UserCreate):
    ...
```

### Mistake 6: Query validation without default

This is required:

```python
min_price: float = Query(ge=0)
```

Better optional version:

```python
min_price: float | None = Query(None, ge=0)
```

### Mistake 7: Confusing `gt` and `ge`

- `gt=0`: strictly greater than 0.
- `ge=0`: greater than or equal to 0.
- `lt=10`: strictly less than 10.
- `le=10`: less than or equal to 10.

### Mistake 8: Untyped list

Weak:

```python
tags: list = []
```

Better:

```python
tags: list[str] = []
```

Best when you want explicit default factory:

```python
tags: list[str] = Field(default_factory=list)
```

---

## 15. Phase 1 Cheat Sheet

Create app:

```python
app = FastAPI()
```

Run app:

```bash
uvicorn main:app --reload
```

GET route:

```python
@app.get("/items")
def list_items():
    return []
```

Path parameter:

```python
@app.get("/items/{item_id}")
def get_item(item_id: int):
    ...
```

Validated path:

```python
item_id: int = Path(..., ge=1)
```

Query parameter:

```python
def list_items(limit: int = 10):
    ...
```

Validated query:

```python
q: str = Query(..., min_length=3)
```

Optional query:

```python
role: str | None = None
```

Pydantic body:

```python
class ItemCreate(BaseModel):
    name: str
    price: float = Field(..., gt=0)

@app.post("/items")
def create_item(item: ItemCreate):
    ...
```

Primitive in body:

```python
priority: int = Body(..., ge=1, le=5)
```

Multiple body models expected JSON:

```json
{
  "user": {...},
  "item": {...}
}
```

Single embedded model expected JSON:

```json
{
  "user": {...}
}
```

Raise 404:

```python
raise HTTPException(status_code=404, detail="Item not found")
```

Set status code:

```python
@app.post("/items", status_code=status.HTTP_201_CREATED)
```

Set response header:

```python
def endpoint(response: Response):
    response.headers["X-App"] = "FastAPI"
    return {"ok": True}
```

Return custom response:

```python
return JSONResponse(content={"message": "custom"}, status_code=418)
```

No-content delete:

```python
@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    ...
```

---

## 16. Full Phase 1 Mental Model

FastAPI lets you describe an API using normal Python functions.

The route decorator says which HTTP method and URL should call the function.

The function parameters describe what data the endpoint needs.

FastAPI decides the data source from the parameter:

- Path if the name appears in the URL path.
- Body if the type is a Pydantic model.
- Query if it is a simple type and not in the path.
- Body if it is explicitly marked with `Body()`.

Pydantic validates incoming data before your function runs.

If validation fails, your function does not run. FastAPI returns 422 with details.

If validation succeeds, your function receives clean Python values, not raw strings from the URL.

Your function returns normal Python data.

FastAPI converts that data into a JSON HTTP response.

You use:

- `Path()` for path validation and docs.
- `Query()` for query validation and docs.
- `Body()` to control request body behavior.
- `Field()` for Pydantic model field validation and docs.
- `HTTPException` for clean error responses.
- `Response` when you want to modify headers, cookies, or dynamic status while keeping normal serialization.
- `JSONResponse` when you need direct control over the response object.

The core habit:

Design the URL first, then decide what belongs in path, query, and body.

Resource identity goes in the path.

Filtering and optional behavior go in the query string.

Structured data goes in the body.

Errors should use proper HTTP status codes.

Successful creation should usually return 201.

Successful deletion with no body should return 204.

Missing resources should raise 404.

Duplicate/conflicting resources should raise 409.

Invalid request data usually becomes 422 through FastAPI/Pydantic.

By the end of Phase 1, you should be able to build a small API from scratch with:

- Multiple HTTP methods.
- Path parameters.
- Query parameters.
- Pydantic request bodies.
- Validation rules.
- Nested models.
- Correct status codes.
- Clean error handling.
- Basic custom response headers.

