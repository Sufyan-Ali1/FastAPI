# Phase 1 Assignment — Correct Answers

---

## A1. Define: Starlette, Pydantic, Uvicorn, ASGI — and why FastAPI needs all four

**Starlette** — A lightweight ASGI web framework/toolkit that provides FastAPI's core web primitives: routing, request/response objects, middleware, WebSocket support, and background tasks.

**Pydantic** — A data validation and serialization library that uses Python type hints to validate incoming data, convert types automatically, and serialize Python objects (including complex types like `datetime`, `UUID`) into JSON.

**Uvicorn** — A production-ready ASGI server that runs the FastAPI application, handling the actual TCP connections and translating network traffic into ASGI-compatible messages.

**ASGI (Asynchronous Server Gateway Interface)** — A *specification/protocol* (not a library) that defines how async Python web applications and async web servers communicate with each other. It is the async successor to WSGI.

**Why all four are needed:**
Each layer has a distinct, non-overlapping job:
- **Uvicorn** handles the network layer (accepts TCP connections, speaks HTTP).
- **ASGI** is the contract between Uvicorn and the app.
- **Starlette** handles the web framework layer (routing, middleware).
- **Pydantic** handles the data layer (validation, serialization).

FastAPI itself is a thin layer on top of all three — it adds the decorator API (`@app.get`), OpenAPI doc generation, and dependency injection. None of these four can replace the others.

---

## A2. Why virtual environments are non-negotiable

Without a virtual environment, all packages install globally on the system Python. This creates a concrete failure: if Project A requires `pydantic==1.10` and Project B requires `pydantic==2.0`, upgrading for Project B will silently break Project A's imports, because both share the same global site-packages. You cannot have two versions of the same package installed globally at the same time.

---

## A3. What `--reload` does and why it must never be used in production

`--reload` starts a file-watcher process alongside the server. Whenever a `.py` file changes on disk, it terminates the current server process and restarts it. This is safe on a dev machine where you are the only user and downtime doesn't matter.

In production it must never be used because:
1. **Performance overhead** — the file watcher continuously scans the filesystem, wasting CPU cycles.
2. **Brief downtime on every restart** — in-flight requests are dropped when the process restarts.
3. **Security surface** — any accidental file write (log rotation, temp file) could trigger an unintended restart.
4. **Multi-worker incompatibility** — production runs multiple worker processes; `--reload` is designed for a single process and does not coordinate restarts safely across workers.

---

## A4. Path parameter vs query parameter — with a URL example

**One-sentence difference:** A path parameter identifies *which* resource to act on (part of the URL structure), while a query parameter describes *how* to retrieve or filter data (appended after `?`).

**Example where the same value could be either:**

```
/users/42          ← user_id as path parameter
/users?id=42       ← user_id as query parameter
```

**Which is better:** `/users/42` (path parameter) is better here. REST convention is that a unique identifier that selects a single resource belongs in the path — it is a required, structural part of the URL. Query parameters are for optional modifiers (filtering, sorting, pagination). Using `?id=42` makes the endpoint look like a search rather than a direct resource access, and it breaks REST conventions for resource addressing.

---

## A5. Why FastAPI returns 422 instead of 400 for validation failures

**400 Bad Request** means the HTTP request itself was malformed — the server could not parse or understand it (e.g., broken HTTP syntax, missing required HTTP headers).

**422 Unprocessable Entity** means the request was received and parsed correctly, but the *data inside it* failed semantic validation. FastAPI understood what you were trying to send, but the values violated the rules (wrong type, missing required field, value out of range, etc.).

The distinction matters to the client: a 422 tells the client *"the request structure was fine, but fix your data"* — and FastAPI attaches a `detail` array showing exactly which fields failed and why. A 400 would suggest the HTTP request itself was broken, which is a different problem entirely. This lets clients write smarter error handling: 400 → check network/HTTP layer, 422 → check application-level input.

---

## A6. Where the junior dev is wrong about `return {}` vs `return JSONResponse({...})`

They are wrong in three distinct ways:

1. **Response model pipeline:** `return {}` passes through FastAPI's full response pipeline — it is filtered by `response_model`, validated, and serialized by Pydantic. `return JSONResponse(...)` bypasses the entire pipeline. Any `response_model` you declared is completely ignored.

2. **Serialization of complex types:** `return {}` can handle Python objects that are not natively JSON-serializable — `datetime`, `UUID`, Pydantic models, `Decimal` — because FastAPI's serializer converts them automatically. `return JSONResponse(...)` requires the dict to already contain only JSON-compatible primitives; passing a `datetime` inside it will raise a `TypeError`.

3. **Headers and status code control:** This is the *only* thing the junior dev got partially right — `JSONResponse` lets you set a custom status code and custom response headers directly. However, you can also achieve this with `return {}` by declaring `response: Response` as a function parameter and setting headers/cookies on it. So this is not a fundamental difference.

The core mistake in their claim: they think the result is the same. It is not — the output JSON might look identical in simple cases, but the pipeline that produced it is completely different.

---

# Section B — Deep Conceptual

---

## B1. Idempotency vs Safety

| Method | Classification | Reason |
|--------|----------------|--------|
| GET | **Safe** | Read-only. No side effects. Calling it 100 times changes nothing on the server. |
| POST | **Neither** | Creates a new resource each time. Has side effects and is not idempotent. |
| PUT | **Idempotent, not safe** | Replaces the resource. Has a side effect (write), but calling it twice leaves the server in the same state as calling it once. |
| DELETE | **Idempotent, not safe** | Has a side effect (deletion), but calling it again on an already-deleted resource leaves the server in the same state: the resource is gone. |
| PATCH | **Neither** | Partial update. A PATCH like `{ "views": views + 1 }` is not idempotent. The spec does not guarantee idempotency for PATCH. |

**"If `DELETE /items/5` returns 404 the second time, has it violated idempotency?"**

**No.** Idempotency is about the *server state*, not the *response code*. After the first DELETE, item 5 is gone. After the second DELETE, item 5 is still gone. The state of the server is identical. The 404 is a different response code, but the world is in the same condition either way. Idempotency does not promise you get the same HTTP response — it promises the same effect on the resource.

---

## B2. Statelessness — three things that break

`app.state.current_user` is a single shared variable on the application object.

**1. Concurrent request race condition.**
Two users log in within milliseconds of each other. Request A sets `app.state.current_user = alice`. Before A's handler finishes, Request B sets `app.state.current_user = bob`. Now Request A continues processing — but it reads `bob` as the current user. Alice gets Bob's data or permissions. REST statelessness requires each request to carry all context needed to serve it (via headers/tokens), not rely on shared server memory that any concurrent request can overwrite.

**2. Multiple worker processes.**
Production deploys multiple Uvicorn workers (or Gunicorn + Uvicorn workers). Each process has its own copy of `app.state`. User logs in through worker 1. The next request is routed to worker 2 — `current_user` is `None`. The user is randomly "logged out" depending on which worker handles them. REST statelessness means the server's response must depend only on the incoming request, not on which process happens to receive it.

**3. No horizontal scaling.**
If you ever scale to multiple machines (containers, VMs), each machine has its own `app.state`. The user is logged in on Machine A but anonymous on Machine B. This breaks completely under any load balancer. REST's stateless constraint exists precisely so that any server in a cluster can handle any request — but only if the request carries its own context.

---

## B3. FastAPI's 3-step parameter decision rule

For any function parameter `x`:

1. **Is `x`'s name present in the URL path string?** (e.g., `/users/{x}`) → **Path parameter**
2. **Is `x`'s type annotation a subclass of Pydantic `BaseModel`?** → **Body parameter** (parsed from JSON body)
3. **Everything else** (primitive types: `str`, `int`, `float`, `bool`, `list`, etc.) → **Query parameter** (read from `?x=value`)

**Why this means you rarely need `Path()`, `Query()`, or `Body()`:**
The three rules above handle routing automatically for the simple case. You only reach for the explicit markers when you need extras: `Path(ge=1)` for validation, `Query(description="...")` for Swagger docs, or `Body(embed=True)` to override the wrapping behavior for a single model. Without those extras, FastAPI infers everything from variable names and type hints alone.

---

## B4. The `=` Trap

```python
def f(role: str | None = None): ...   # version 1
def f(role: str = None): ...          # version 2
```

**Version 1** — `str | None` is the type annotation. Pydantic sees this as a union type that explicitly permits `None`. The default is `None`. Sending no value → `None`. Sending `null` → `None`. Sending a string → validated as `str`. This is correct and intentional.

**Version 2** — The type annotation says `str` (not optional). The default is `None`, but `None` is not a valid `str`. In Pydantic v2, this raises a `ValidationError` at instance creation time if `None` is actually received — the annotation does not permit `None`, so Pydantic rejects it. In Pydantic v1, the type was silently widened to `Optional[str]`, masking the bug.

The key insight: **the default value does not change the type annotation**. `role: str = None` lies — it claims the type is `str` but provides a non-`str` default. Pydantic v2 enforces the annotation strictly and will reject `None` at runtime.

---

## B5. `gt`/`lt` vs `ge`/`le` and the Swagger surprise

**`ge=1, le=9`** → FastAPI writes `minimum: 1, maximum: 9` into the OpenAPI JSON schema. Swagger UI renders this as an HTML5 `<input type="number" min="1" max="9">`. The browser's built-in HTML5 form validation enforces these bounds *before* the request is sent. Bad values are rejected in the UI.

**`gt=0, lt=10`** → FastAPI writes `exclusiveMinimum: 0, exclusiveMaximum: 10`. These are valid JSON Schema keywords, but HTML5 form inputs do not have a native "exclusive" bound concept. Swagger UI renders the input without enforcing the exclusivity client-side. The user can type `0` or `10`, the browser allows it, and the request reaches the server where FastAPI returns a 422.

**Answer:** `ge`/`le` rejects at the Swagger UI (client-side). `gt`/`lt` lets the value reach the server.

---

## B6. Multiple body params — exact JSON shapes

Assume:
```python
class User(BaseModel): name: str
class Item(BaseModel): title: str
```

**1. Two Pydantic models: `def create(user: User, item: Item)`**

When a function has more than one body source, FastAPI wraps each under its parameter name as a key:
```json
{
  "user": { "name": "Alice" },
  "item": { "title": "Book" }
}
```

**2. One model with `embed=True`, other removed: `def create(user: User = Body(..., embed=True))`**

`embed=True` on a *single* model forces the same wrapping behavior (normally a single model is unwrapped). The client must still nest it:
```json
{
  "user": { "name": "Alice" }
}
```
Without `embed=True` on a single model, the client sends the flat object directly:
```json
{ "name": "Alice" }
```

**3. Two models + a primitive `int`: `def create(user: User, item: Item, priority: int = Body(...))`**

The `Body(...)` on `priority` tells FastAPI it belongs in the JSON body. With multiple body sources, all are wrapped:
```json
{
  "user": { "name": "Alice" },
  "item": { "title": "Book" },
  "priority": 3
}
```

---

## B7. Three Pydantic v1 → v2 differences

**1. Validator decorator names and signatures changed.**
v1: `@validator("field_name")` — function takes `(cls, v)`.
v2: `@field_validator("field_name")` — must also add `@classmethod`, and cross-field access uses `info: ValidationInfo` instead of `values` dict.

**2. Config style replaced.**
v1: `class Config: orm_mode = True`
v2: `model_config = ConfigDict(from_attributes=True)` — `orm_mode` was renamed `from_attributes`, and the nested class was replaced by a module-level `ConfigDict`.

**3. Method names renamed.**
v1: `.dict()`, `.json()`, `.schema()`
v2: `.model_dump()`, `.model_dump_json()`, `.model_json_schema()`
Calling `.dict()` in v2 still works but triggers a deprecation warning and will be removed in a future version.

---

## B8. Five concrete losses when using `dict` instead of a Pydantic model

| # | What you lose | FastAPI feature that disappears |
|---|---------------|--------------------------------|
| 1 | **Type coercion** — `"42"` stays a string instead of becoming `42` | Automatic type conversion on input |
| 2 | **Field validation** — any key, any value, no constraints enforced | `Field(min_length=..., ge=..., regex=...)` constraints |
| 3 | **OpenAPI schema generation** — FastAPI can't introspect a `dict` | The request body schema in Swagger UI (`/docs`) is blank |
| 4 | **IDE autocomplete and static type safety** — `item["name"]` is untyped; typos become runtime `KeyError`s | Type checker (mypy/pyright) and IDE support |
| 5 | **Nested model validation** — inner dicts are raw, unvalidated Python dicts | Nested model validation (e.g., `address: Address` inside `User`) |

---

# Section B2 — Conceptual Coding

---

## B2-1. Minimal model

```python
from pydantic import BaseModel

class UserNested(BaseModel):
    id: int                  # required
    tags: list[str]          # required

class Payload(BaseModel):
    user: UserNested         # required
    scores: list[int]        # required
    active: bool             # required
    note: str | None         # required (but nullable — must send the key, value can be null)
```

Field status breakdown:
- `user` → **required** (present, no default given)
- `scores` → **required** (present, no default given)
- `active` → **required** (present, no default given)
- `note` → **required but nullable** — the JSON shows the key `"note"` is present with a `null` value; the type `str | None` with no default means you must send the key, but `null` is accepted as the value

---

## B2-2. Signature challenge

```python
from typing import Annotated
from fastapi import Path, Query, Body
from pydantic import BaseModel, Field

class MemberUpdate(BaseModel):
    name: str
    email: str

@app.put("/teams/{team_id}/members/{member_id}")
def update_member(
    team_id: Annotated[int, Path(ge=1)],
    member_id: Annotated[int, Path(ge=1)],
    role: str | None = None,
    active: bool = True,
    update: MemberUpdate = Body(...),
    note: Annotated[str | None, Body(max_length=200)] = None,
):
    ...
```

`note` uses `Body(max_length=200)` to force it into the JSON body (otherwise a primitive with a default would be treated as a query param) and constrain its length.

---

## B2-3. Product, Variant, Manufacturer models

```python
from pydantic import BaseModel, Field

class Variant(BaseModel):
    color: str
    stock: int = Field(..., ge=0)

class Manufacturer(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., pattern=r'^[A-Z]{2}$')

class Product(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    variants: list[Variant]
    manufacturer: Manufacturer
```

---

## B2-4. Three flavours of optional `bio`

**Flavour 1 — `str | None = None` (fully optional, nullable)**
```python
bio: str | None = None
```
- `"bio"` missing from JSON → `bio` becomes `None` (no error)
- `"bio": null` sent → `bio` becomes `None` (no error)

**Flavour 2 — `str | None` with no default (nullable but required)**
```python
bio: str | None
```
- `"bio"` missing from JSON → **422 validation error** — the key is required
- `"bio": null` sent → `bio` becomes `None` (no error)

**Flavour 3 — `str = ""` (optional, non-nullable, empty string default)**
```python
bio: str = ""
```
- `"bio"` missing from JSON → `bio` becomes `""` (empty string, no error)
- `"bio": null` sent → **422 validation error** — `str` does not accept `None`

---

## B2-5. Same URL, three methods

```python
from fastapi import status

@app.get("/items/{id}", status_code=status.HTTP_200_OK)
def get_item(id: int) -> ItemOut: ...

@app.put("/items/{id}", status_code=status.HTTP_200_OK)
def update_item(id: int, item: ItemUpdate) -> ItemOut: ...

@app.delete("/items/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(id: int) -> None: ...
```

DELETE has `-> None` because 204 means no body is returned.

---

## B2-6. `Annotated[]` translation

```python
from typing import Annotated
from fastapi import Query

def search(
    q: Annotated[str, Query(min_length=3)],
    tags: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
):
    ...
```

**Why `Annotated[]` is preferred:** It separates the type annotation (which belongs to Python) from FastAPI-specific metadata (which belongs to the framework), so the type hints remain usable by type checkers and other tools that have no knowledge of FastAPI.

---

## B2-7. Flag in body or query — both versions

**(a) Flag as a query parameter**
```python
@app.post("/users", status_code=201)
def create_user(user: User, send_welcome_email: bool = False):
    ...
```

**(b) Flag inside the JSON body**
```python
@app.post("/users", status_code=201)
def create_user(user: User, send_welcome_email: bool = Body(False)):
    ...
```
Client must send: `{ "user": {...}, "send_welcome_email": true }`

**Which is better:** (a) — query parameter. `send_welcome_email` is a behavioral modifier describing *what the server should do*, not data about the user resource. It does not belong in the resource representation. Query parameters are the correct location for operational flags that control side effects without changing the resource itself.

---

## B2-8. Mutable default mistake

**Wrong — every instance gets the same timestamp:**
```python
from datetime import datetime
from pydantic import BaseModel

class Record(BaseModel):
    name: str
    created_at: datetime = datetime.now()  # evaluated ONCE when the class is defined
```

**Correct — each instance gets its own timestamp:**
```python
from datetime import datetime
from pydantic import BaseModel, Field

class Record(BaseModel):
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
```

**Why it happens:** `datetime.now()` is a function call. Python evaluates default values once at class definition time (when the module is imported), not each time an instance is created. Every `Record()` gets the same frozen timestamp from import time. `default_factory` stores a *reference to the function*, which is called fresh on each instantiation.

---

## B2-9. Hide `password_hash` without `response_model`

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UserCreate(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str

fake_db: dict[int, dict] = {}
_counter = 0

@app.post("/users", status_code=201)
def create_user(data: UserCreate) -> UserOut:
    global _counter
    _counter += 1
    fake_db[_counter] = {
        "id": _counter,
        "username": data.username,
        "password_hash": f"bcrypt:{data.password}",
    }
    return UserOut(id=_counter, username=data.username)
```

The function works with a record that includes `password_hash`, but it explicitly returns a `UserOut` instance that has no `password_hash` field — so it can never appear in the response.

---

## B2-10. Conditional status code using injected `Response`

```python
from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI()
users_db: dict[str, dict] = {}

class SignupRequest(BaseModel):
    email: str
    password: str

@app.post("/signup")
def signup(data: SignupRequest, response: Response):
    if data.email in users_db:
        user_id = users_db[data.email]["id"]
        response.status_code = 200
    else:
        user_id = len(users_db) + 1
        users_db[data.email] = {"id": user_id, "email": data.email}
        response.status_code = 201

    response.headers["X-User-Id"] = str(user_id)
    return {"user_id": user_id}
```

---

## B2-11. The right error for each scenario

```python
# 1. User tried to delete someone else's post
raise HTTPException(status_code=403, detail="You do not have permission to delete this post")

# 2. JWT token is missing entirely
raise HTTPException(
    status_code=401,
    detail="Authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)

# 3. Registering an email that already exists
raise HTTPException(status_code=409, detail="An account with this email already exists")

# 4. Upstream service is down
raise HTTPException(status_code=503, detail="Upstream service temporarily unavailable")

# 5. Endpoint exists but client sent GET instead of POST
# ⚠️ TRICK: FastAPI handles this automatically.
# You never need to raise 405 yourself — FastAPI and Starlette return 405 Method Not Allowed
# if a route exists for a URL but not for the HTTP method the client used.
```

---

## B2-12. Path-overlap puzzle

```python
@app.get("/users/me")
@app.get("/users/{user_id}")
@app.get("/users/{user_id:int}")
```

**1. Which are reachable / dead:**
- `/users/me` — **reachable**. Declared first, so `GET /users/me` matches it before the second route is tried.
- `/users/{user_id}` — **reachable**. Matches any string segment (including integers) not already caught by route 1.
- `/users/{user_id:int}` — **dead code**. Route 2 already captures every path including integer-like strings. Route 3 can never be reached because route 2 wins first.

**2. `{user_id:int}` vs `user_id: int` in the function signature:**
These are two completely different levels:
- `{user_id:int}` in the path string is a **Starlette router-level converter**. It filters at the routing layer — the route only matches if the URL segment is parseable as an integer. A non-integer URL skips this route entirely (may result in 404).
- `user_id: int` in the function signature is a **FastAPI/Pydantic type hint**. The route matches any string, but after matching, FastAPI tries to coerce the captured string to `int`. If it fails, FastAPI returns a 422 validation error — the route *was* matched, but validation failed.

Practical difference: `{user_id:int}` skips the route on non-integers (404). `user_id: int` matches the route on non-integers and then returns 422.

---

## B2-13. `Enum` vs `Literal`

**Using Enum:**
```python
from enum import Enum
from pydantic import BaseModel

class PostStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"

class Post(BaseModel):
    status: PostStatus = PostStatus.draft
```

**Using Literal:**
```python
from typing import Literal
from pydantic import BaseModel

class Post(BaseModel):
    status: Literal["draft", "published", "archived"] = "draft"
```

**When to pick each:**
- **Enum**: when the values are reused across multiple models, when you need to reference them programmatically (`PostStatus.published`), or when you want a named type in OpenAPI docs (Swagger will show the enum type by name). Better for domain constants.
- **Literal**: when it's a one-off constraint in a single model with no reuse elsewhere. Simpler, less boilerplate. OpenAPI still shows the allowed values, but without a named type.

---

## B2-14. Reverse-engineer the OpenAPI

```yaml
parameters:
  - name: status
    in: query
    required: false
    schema:
      type: string
      enum: [active, banned, pending]
      default: active
      description: "Filter users by account status"
```

```python
from enum import Enum
from typing import Annotated
from fastapi import Query

class UserStatus(str, Enum):
    active = "active"
    banned = "banned"
    pending = "pending"

@app.get("/users")
def list_users(
    status: Annotated[UserStatus, Query(description="Filter users by account status")] = UserStatus.active,
):
    ...
```

---

## B2-15. The exact body

**Original endpoint:**
```python
@app.post("/orders")
def create(user: User, item: Item, priority: int = Body(..., ge=1, le=5)):
    ...
```

Client must send:
```json
{
  "user":     { "name": "Alice" },
  "item":     { "title": "Book", "price": 10.0 },
  "priority": 3
}
```

**Rewritten to accept `{ "order": { ... } }`:**
```python
from pydantic import BaseModel, Field

class OrderBody(BaseModel):
    user: User
    item: Item
    priority: int = Field(..., ge=1, le=5)

@app.post("/orders")
def create(order: OrderBody = Body(..., embed=True)):
    ...
```

`embed=True` on a single model wraps it under the parameter name `"order"`, so the client sends:
```json
{
  "order": {
    "user": { "name": "Alice" },
    "item": { "title": "Book", "price": 10.0 },
    "priority": 3
  }
}
```

---

## B2-16. Refactor the monstrosity

**Original (with at least 6 issues marked):**
```python
@app.post("/users/")
def create_user(data: dict, response: Response):             # issue 1: dict — no validation or docs
    if "name" not in data: return JSONResponse({"err": "name required"}, 400)   # issue 2: manual validation FastAPI handles
    if len(data["name"]) < 2: return JSONResponse({"err": "too short"}, 400)    # issue 3: same — Field() does this
    if "age" in data and data["age"] < 0: return JSONResponse({"err": "bad age"}, 400)  # issue 4: same
    response.status_code = 201                               # issue 5: status code belongs on the decorator
    return data                                              # issue 6: returning raw untyped dict
```

**Clean version:**
```python
from fastapi import FastAPI, status
from pydantic import BaseModel, Field

app = FastAPI()

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2)
    age: int | None = Field(None, ge=0)

class UserOut(BaseModel):
    name: str
    age: int | None = None

@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate) -> UserOut:
    return UserOut(name=data.name, age=data.age)
```

**Six issues fixed:**
1. `dict` → typed `UserCreate` Pydantic model (validation, OpenAPI docs, IDE safety)
2–4. Manual `if` checks removed — `Field(min_length=2)` and `Field(ge=0)` handle all three automatically, with proper 422 responses and field-level error messages
5. `response.status_code = 201` removed — `status_code=HTTP_201_CREATED` on the decorator is the correct, idiomatic location
6. `return data` → `return UserOut(...)` — returns a typed, validated response model instead of a raw dict

---

# Section C — Debugging

---

## C1. Route ordering bug

**Bug:** FastAPI matches routes in declaration order — first match wins. When a request arrives for `GET /items/latest`, FastAPI tries the first declared route `/items/{item_id}`. The string `"latest"` matches the `{item_id}` pattern. FastAPI then tries to coerce `"latest"` into `int` (because `item_id: int`), fails, and returns **422**. The second route `GET /items/latest` is never reached — it is dead code.

**Fix — swap the order so the static route is declared first:**
```python
@app.get("/items/latest")       # static route first
def latest(): ...

@app.get("/items/{item_id}")    # dynamic route second
def get_item(item_id: int): ...
```

Rule: always declare static/literal routes before dynamic `{param}` routes that share the same URL prefix.

---

## C2. `audit: bool` treated as a required query parameter

**Bug:** FastAPI's 3-step rule classifies `audit: bool` as a **query parameter** (it's not in the path, not a Pydantic model). Because it has no default value, it is a *required* query parameter. The client sends a JSON body but no `?audit=true` in the URL, so FastAPI returns 422 saying `audit` is missing from the query string.

**Fix 1 — make it an optional query parameter with a default:**
```python
@app.post("/users")
def create(user: User, audit: bool = False):
    return user
```

**Fix 2 — move it into the JSON body using `Body()`:**
```python
from fastapi import Body

@app.post("/users")
def create(user: User, audit: bool = Body(...)):
    return user
```
Client now sends: `{ "user": {...}, "audit": true }`

---

## C3. `Query(ge=0)` does not make a field optional

**Bug:** `Query(ge=0)` is shorthand for `Query(default=..., ge=0)`. In FastAPI, `...` (Ellipsis) as the first argument to `Query()` means **required** — no default is provided. The `ge=0` is a validation *constraint*, not a default value. So `min_price` is a required query param that must be ≥ 0.

**Minimal fix:**
```python
@app.get("/products")
def products(min_price: float | None = Query(None, ge=0)):
    return {"min_price": min_price}
```

`None` is the explicit default, making the param optional. `ge=0` still applies when a value is provided. The type becomes `float | None` to reflect that it can be absent.

---

## C4. Returning a body with status 204

**Bug:** HTTP 204 No Content is a spec-level contract that the response will have **no body**. FastAPI/Starlette silently strips the returned dict — the client receives an empty response body, not `{"deleted": id}`. The `return {"deleted": id}` line is dead code that misleads any developer reading it.

**Fix — choose one path:**

Option A: Return nothing (correct 204):
```python
@app.delete("/items/{id}", status_code=204)
def delete_item(id: int):
    items_db.pop(id, None)
    return None   # or just: return
```

Option B: Return a body with 200 instead:
```python
@app.delete("/items/{id}", status_code=200)
def delete_item(id: int):
    return {"deleted": id}
```

---

## C5. Primitive `priority` treated as a query parameter

**Bug:** FastAPI applies the 3-step rule to every parameter. `priority: int` is not in the path, not a Pydantic model, and has no default — so it is classified as a **required query parameter**. Even though `user` and `item` force a JSON body, `priority` is looked up in `?priority=3`, not inside the JSON body. The client's `"priority": 3` in the body is ignored.

**Fix — one line, force it into the body:**
```python
priority: int = Body(..., ge=1)
```

Full corrected signature:
```python
@app.post("/orders")
def create_order(user: User, item: Item, priority: int = Body(...)):
    ...
```

Client sends exactly what they already tried:
```json
{ "user": {...}, "item": {...}, "priority": 3 }
```

---

## C6. Two bugs — one Pythonic, one FastAPI-idiomatic

**Original:**
```python
if not user:
    return {"error": "not found"}, 404
```

**Bug 1 (Pythonic) — tuple return is not a 404:**
`return {"error": "not found"}, 404` returns a Python *tuple* `(dict, int)`. FastAPI serializes it as a JSON array: `[{"error": "not found"}, 404]`, with a **200** status code. The `404` is just a second element in the tuple — it is NOT the HTTP status code. The client receives a 200 with unexpected JSON.

**Bug 2 (FastAPI-idiomatic) — use `HTTPException`, not a manual error dict:**
Returning `{"error": "not found"}` is informal and inconsistent. FastAPI's standard pattern for "resource not found" is `raise HTTPException(status_code=404, ...)`, which produces a structured error response and the correct HTTP status code.

**Fix:**
```python
from fastapi import HTTPException

@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

---

## C7. Untyped `list` in a Pydantic model

**Bug:** `tags: list = []` declares `tags` as an untyped list. Pydantic accepts *any* element inside it — strings, integers, dicts, nested lists — with no validation. A client can send `"tags": [1, null, {"x": 2}]` and it passes silently. The OpenAPI schema for `tags` has no item type (`items: {}`), giving Swagger UI and API consumers no information about what belongs in the array.

Note: the mutable `[]` default is **not** a bug in Pydantic — unlike Python dataclasses, Pydantic v2 deep-copies mutable defaults per instance automatically.

**Fix:**
```python
class Item(BaseModel):
    tags: list[str] = []
```

Now every element is validated as a `str`. Non-string elements raise a 422. Swagger UI shows `items: { type: string }`. If you prefer to be explicit about the default factory:
```python
from pydantic import Field

class Item(BaseModel):
    tags: list[str] = Field(default_factory=list)

---
---

# Section D — Predict the Output

---

## D1. Query parameter coercion

```python
@app.get("/items")
def list_items(limit: int = 10, in_stock: bool = True):
    return {"limit": limit, "in_stock": in_stock}
```

**1. `/items`**
Both params use their defaults.
```json
{"limit": 10, "in_stock": true}
```

**2. `/items?limit=5`**
`limit` overridden to 5, `in_stock` stays default.
```json
{"limit": 5, "in_stock": true}
```

**3. `/items?limit=abc`**
`"abc"` cannot be coerced to `int`.
→ **422 Unprocessable Entity**

**4. `/items?in_stock=yes`**
FastAPI's bool coercion accepts `"yes"`, `"on"`, `"true"`, `"1"` as `True`.
```json
{"limit": 10, "in_stock": true}
```

**5. `/items?in_stock=maybe`**
`"maybe"` is not in FastAPI's accepted bool string set.
→ **422 Unprocessable Entity**

**6. `/items?limit=5&in_stock=0&limit=20`** *(limit appears twice)*
For a scalar (non-list) parameter with duplicate keys, Starlette's `QueryParams` builds an internal dict that keeps the **last** value. So `limit = 20`. `"0"` coerces to `False`.
```json
{"limit": 20, "in_stock": false}
```

---

## D2. `:path` converter

```python
@app.get("/files/{path:path}")
def get_file(path: str): return {"path": path}
```

**1. `/files/a.txt`**
Everything after `/files/` is captured.
```json
{"path": "a.txt"}
```

**2. `/files/folder/sub/a.txt`**
`:path` is special — unlike `{param}`, it captures forward slashes too.
```json
{"path": "folder/sub/a.txt"}
```

**3. `/files/`**
`:path` matches empty string when nothing follows the slash.
```json
{"path": ""}
```

---

## D3. Nested model validation

```python
class Address(BaseModel):
    city: str

class User(BaseModel):
    name: str
    age: int = 18
    address: Address
```

**1. `{ "name": "A", "address": {"city": "X"} }`**
All required fields present. `age` defaults to `18`. `address` is a valid `Address` object.
→ **200 OK** — `{"name": "A", "age": 18, "address": {"city": "X"}}`

**2. `{ "name": "A", "age": "20", "address": {"city": "X"} }`**
`age` is sent as string `"20"`. Pydantic automatically coerces `"20"` → `20` for an `int` field (lax mode).
→ **200 OK** — `{"name": "A", "age": 20, "address": {"city": "X"}}`

**3. `{ "name": "A", "address": "Karachi" }`**
`address` expects a JSON object that maps to `Address`, not a plain string. Pydantic cannot construct `Address` from a string.
→ **422 Unprocessable Entity** — error on `address`: input should be a valid dict

**4. `{ "name": "A", "address": {} }`**
`address` is an empty object. `Address` requires `city: str` with no default — it is a required field. Missing required field.
→ **422 Unprocessable Entity** — error on `address.city`: field required
