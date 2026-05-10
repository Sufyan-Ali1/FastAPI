# 📝 Phase 2 — Production-Grade Assignment

> **Scope:** Lessons 9–19 (Phase 2) + reinforcement of Lessons 1–8 (Phase 1).
> **Constraint:** All problems are solvable using only the covered FastAPI features and Python standard library. No databases, ORMs, auth systems, or external infrastructure.
> **Standard:** Industry-level. Every answer should explain *why*, not just *what*.

---

## 🧭 Coverage Map

| Topic | Section(s) |
|-------|-----------|
| Pydantic validators, `model_config` | B, C, I |
| Response models, `exclude_unset` | B, C, D |
| Multiple models per route | B, G |
| Status codes & HTTPException | A, C, D |
| Error handling (validation, global, dev/prod) | C, E, H |
| Dependency Injection (`Depends`, `yield`, class-based) | B, C, D, G |
| Middleware (order, custom, built-in) | B, D, F, G |
| Routers, prefixes, tags, router-level deps | B, C, F, G |
| Form data & file uploads | C, H, G |
| Headers & cookies (security flags) | B, H, G |
| Static files & Jinja2 templates | H, G |
| Phase 1 reinforcement (path/query/body, REST) | A, C, D |

---

## 🟢 SECTION A — Warm-up

> *Short conceptual answers — 2–4 sentences each. Build momentum before the hard parts.*

**A1.** What is the single biggest difference between `@field_validator` and `@model_validator(mode="after")`? When would one fail but the other succeed — give a concrete example.

**A2.** A teammate says *"I always use `response_model_exclude_none=True` on every endpoint — it makes responses cleaner."* What real case breaks this assumption? Name a field type where sending `null` (not just omitting the field) is semantically meaningful.

**A3.** You have two `@app.middleware("http")` decorators. A second `app.add_middleware(CORSMiddleware)` call follows. In what order do the three layers execute for an incoming request? Draw the onion.

**A4.** Why can you not use a Pydantic `BaseModel` as a body parameter in the same endpoint as `Form()` fields? What is the exact technical reason, not just "they conflict"?

**A5.** What is the difference between `dependencies=[Depends(fn)]` on `include_router()` vs placing `Depends(fn)` inside an individual endpoint's parameters? Name one thing you can do with the latter that you cannot with the former.

**A6.** `response_model_exclude_unset=True` and `model_dump(exclude_unset=True)` both exist. What does each one do, when does each run, and why do PATCH endpoints need *both*?

---

## 🟡 SECTION B — Deep Conceptual

> *Detailed answers expected. Justify every claim.*

**B1. Validator execution order.**
Given this model:
```python
class Order(BaseModel):
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    discount: float = Field(0.0, ge=0.0, lt=1.0)

    @field_validator("discount")
    @classmethod
    def discount_needs_minimum_quantity(cls, v, info: ValidationInfo):
        if v > 0 and info.data.get("quantity", 0) < 5:
            raise ValueError("Discounts only apply to orders of 5+ items")
        return v

    @model_validator(mode="after")
    def total_must_be_positive(self):
        total = self.quantity * self.price * (1 - self.discount)
        if total <= 0:
            raise ValueError("Total must be positive")
        return self
```
Trace the **exact execution order** when this JSON is sent: `{"quantity": 3, "price": 10.0, "discount": 0.2}`.
Which validator fires first? Which error surfaces to the client? What does the 422 response look like?

**B2. The dependency graph.**
You have:
```python
def A(): return "a"
def B(a=Depends(A)): return a + "b"
def C(a=Depends(A)): return a + "c"
def D(b=Depends(B), c=Depends(C)): return b + c

@app.get("/")
def endpoint(result=Depends(D)):
    return result
```
1. How many times does `A()` actually execute per request? Why?
2. What does the endpoint return?
3. If `A` were `Depends(A, use_cache=False)` in both `B` and `C`, what changes?
4. Rewrite `A` as a `yield` dependency that prints "open" before and "close" after. What prints to the console for one request?

**B3. `model_config` interaction.**
```python
class Strict(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)
    name: str = Field("anonymous", min_length=3)
```
1. What happens when you instantiate `Strict()` with no arguments?
2. What happens when you send `{"name": "  ab  "}` to an endpoint using this model?
3. What happens with `{"name": "  x  "}`? Walk through each step.

**B4. Middleware vs Dependency — the hard choice.**
For each scenario, decide: **middleware** or **dependency**? Justify in 2 sentences:
1. Reject all requests where `Content-Type` is not `application/json` for POST routes.
2. Load the current user from a session cookie and inject them into the endpoint.
3. Add a `X-Response-Time` header to every response including 404s.
4. Check that a specific `X-Feature-Flag` header is present for a specific set of 3 endpoints.
5. Log every request's IP address, method, path, and response status to a file.
6. Validate that an uploaded file is not empty before the endpoint handler runs.

**B5. Router-level dependency propagation.**
```python
def check_auth(token: str = Query(...)):
    if token != "secret": raise HTTPException(401)

router = APIRouter(dependencies=[Depends(check_auth)])

@router.get("/a")
def route_a(): return "a"

@router.get("/b")
def route_b(extra: str = Query("default")): return extra

app.include_router(router, prefix="/api")
```
1. What URL with what parameters successfully hits `/api/b`?
2. `route_b` defines its own `Query` parameter. Does it conflict with `check_auth`'s `token` parameter? Why not?
3. If you add `dependencies=[Depends(check_auth)]` to `include_router()` as well (it's also on the router), does `check_auth` run once or twice?

**B6. Response model inheritance chain.**
```python
class Base(BaseModel):
    id: int
    name: str

class Full(Base):
    email: str
    internal_score: float

class Public(Base):
    pass  # only id and name

@app.get("/users/{id}", response_model=Public)
def get_user(id: int):
    return Full(id=id, name="Sufyan", email="x@y.com", internal_score=9.5)
```
1. What does the client receive?
2. Does FastAPI validate that the returned `Full` object satisfies the `Public` model's constraints before stripping?
3. What if `Full` had a field `id: str` (string instead of int)? What happens at the `response_model` filtering step?

**B7. The `yield` dependency cleanup guarantee.**
```python
cleanup_log = []

def get_resource():
    cleanup_log.append("open")
    try:
        yield {"data": "resource"}
    finally:
        cleanup_log.append("close")

@app.get("/data")
def read_data(res=Depends(get_resource)):
    raise HTTPException(status_code=500, detail="Something broke")
```
1. After this endpoint is called, what is in `cleanup_log`?
2. What does the client receive?
3. If `raise RuntimeError("crash")` replaces the `HTTPException`, does `cleanup_log` still get `"close"`?

**B8. Cookie security flags matrix.**
For each scenario, write the exact `set_cookie()` call with the minimum required flags. Justify each flag:
1. A long-lived (30-day) session token on an HTTPS-only production site.
2. A UI theme preference (needs JS access) on a public site.
3. A CSRF token that must be readable by JavaScript and sent cross-origin.
4. A short-lived (5-minute) OTP validation marker.

**B9. Pydantic v1 → v2 migration.**
A colleague hands you this v1 code. List every change needed to make it run in Pydantic v2. Be specific — don't say "update syntax", say exactly what line changes to what:
```python
from pydantic import BaseModel, validator, root_validator

class User(BaseModel):
    name: str
    age: int

    @validator("name")
    def name_must_be_title(cls, v):
        return v.title()

    @root_validator
    def check_adult_name(cls, values):
        if values.get("age", 0) >= 18 and values.get("name") == "Kid":
            raise ValueError("Adults cannot be named 'Kid'")
        return values

    class Config:
        orm_mode = True
```

---

## 🔵 SECTION C — Debugging & Code Review

> *Find every bug. Explain WHY it is wrong. Write the fix.*

**C1.**
```python
class ProductUpdate(BaseModel):
    name: str | None = None
    price: float | None = None

@app.patch("/products/{id}")
def update_product(id: int, updates: ProductUpdate):
    product = db[id]
    product.update(updates.model_dump())
    return product
```
Two bugs: one causes silent data corruption, one doesn't validate the id. Fix both.

**C2.**
```python
@app.exception_handler(HTTPException)
async def handler(request, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

@app.exception_handler(RequestValidationError)
async def val_handler(request, exc):
    return JSONResponse({"errors": exc.errors()}, status_code=400)

@app.get("/items/{id}")
def get_item(id: int):
    if id not in db:
        return {"error": "not found"}   # ← line A
    return db[id]
```
What is wrong on line A? How does it interact with the global handler? What does the client actually receive?

**C3.**
```python
class UserCreate(BaseModel):
    email: str
    password: str = Field(..., min_length=8)

class UserOut(UserCreate):  # ← inherits UserCreate
    id: int
    created_at: datetime

@app.post("/users", response_model=UserOut, status_code=201)
def create_user(user: UserCreate):
    ...
    return {"id": 1, "email": user.email, "created_at": datetime.now(), **user.model_dump()}
```
One serious bug. What is it, what does it expose, and how do you fix it?

**C4.**
```python
def heavy_computation():
    print("computing...")
    return sum(range(10_000_000))

@app.get("/a")
def route_a(result=Depends(heavy_computation)):
    return result

@app.get("/b")
def route_b(result=Depends(heavy_computation)):
    return result
```
A user hits `/a` and `/b` in the same browser tab (two separate requests). They expected the computation to run only once. Why doesn't caching help here, and what would you use instead?

**C5.**
```python
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)

@app.middleware("http")
async def timing(request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Time"] = str(time.time() - start)
    return response
```
Draw the actual execution order. If `AuthMiddleware` short-circuits (returns early without calling `call_next`), does `LoggingMiddleware` run? Does `timing` run?

**C6.**
```python
@app.post("/upload")
async def upload(
    user: UserCreate,           # Pydantic body model
    file: UploadFile = File(...),
):
    contents = await file.read()
    return {"name": user.name, "file": file.filename}
```
What happens when this endpoint is called? Why? What is the correct way to accept both user data and a file in one endpoint?

**C7.**
```python
router = APIRouter(prefix="/v1")

@router.get("/users")
def list_users(): return []

app.include_router(router, prefix="/api")
app.include_router(router, prefix="/internal")
```
1. List all URL paths that get registered.
2. Is this safe? What happens if `list_users` has side effects?
3. How would you structure this differently?

**C8.**
```python
@app.middleware("http")
async def block_large_requests(request: Request, call_next):
    body = await request.body()
    if len(body) > 1024:
        return JSONResponse({"error": "too large"}, status_code=413)
    return await call_next(request)
```
This middleware breaks POST endpoints that have a body smaller than 1024 bytes. Why? How do you fix it?

---

## 🟣 SECTION D — Behavior Analysis (Predict & Explain)

> *No running code. Reason through it.*

**D1.** Given:
```python
call_log = []

def dep_a():
    call_log.append("A")
    return 1

def dep_b(a=Depends(dep_a)):
    call_log.append("B")
    return a + 1

@app.get("/x", dependencies=[Depends(dep_b)])
def x(val=Depends(dep_b)):
    return {"val": val, "log": call_log}
```
What does a GET `/x` return? How many times does `dep_a` run? How many times does `dep_b` run? What is in `call_log`?

**D2.** Trace the **full request lifecycle** — including every layer — for:
```
POST /api/users?token=secret
Content-Type: application/json
X-Request-ID: abc123
Body: { "email": "x@y.com", "password": "short" }
```
The app has: CORS middleware → `APIKeyMiddleware` (checks `X-API-Key` header, not query) → request logging middleware → `require_auth` dependency on the router → `UserCreate` Pydantic model with `password min_length=8`.
List each layer the request hits, and at which layer it stops and what the client receives.

**D3.** Given:
```python
class Item(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., min_length=2)
    tags: list[str] = []

    @field_validator("tags", mode="before")
    @classmethod
    def split_string_tags(cls, v):
        if isinstance(v, str):
            return [t.strip() for t in v.split(",")]
        return v
```
For each input, predict the model's final state or the error:
1. `{"name": "  Laptop  ", "tags": ["new", "  sale  "]}`
2. `{"name": "X"}`
3. `{"name": "TV", "tags": "4k, oled, smart"}`
4. `{"name": "PC", "tags": ""}`

**D4.**
```python
@app.get("/items", response_model=list[ItemOut], response_model_exclude_unset=True)
def list_items():
    return [
        {"id": 1, "name": "Laptop"},          # price missing
        {"id": 2, "name": "Mouse", "price": 29.99},
    ]
```
`ItemOut` has: `id: int`, `name: str`, `price: float = 0.0`, `in_stock: bool = True`.
What exactly does each item look like in the response? Does `exclude_unset=True` apply to the returned dicts the same way it applies to Pydantic model instances? Explain the difference.

---

## 🔴 SECTION E — Dependency Injection Deep Dive

> *DI is the most important FastAPI feature. These questions go beyond the basics.*

**E1. Class-based dependency design.**
Design a `RateLimiter` class-based dependency that:
- Takes `max_calls: int` and `window_seconds: int` in `__init__`
- Uses an in-memory dict to track call counts per client IP
- Returns `429 Too Many Requests` with a `Retry-After` header when exceeded
- Resets counts after `window_seconds`

Write the full class + two router usages: one with `max_calls=10`, one with `max_calls=100`.

**E2. Yield dependency chain.**
```python
def get_a():
    print("A open")
    yield "a"
    print("A close")

def get_b(a=Depends(get_a)):
    print("B open")
    yield a + "b"
    print("B close")

def get_c(b=Depends(get_b)):
    print("C open")
    yield b + "c"
    print("C close")

@app.get("/chain")
def chain(c=Depends(get_c)):
    print("endpoint")
    return c
```
Write the **exact console output** (in order) for one successful GET `/chain`. Then write the output if the endpoint raises `HTTPException(500)` midway.

**E3. Dependency override for testing.**
You have:
```python
def get_current_user(token: str = Header(...)):
    user = verify_jwt(token)
    if not user: raise HTTPException(401)
    return user

@app.get("/me")
def me(user=Depends(get_current_user)):
    return user
```
Write the test setup (no actual test framework needed — just the override mechanism) that:
1. Replaces `get_current_user` with a function returning `{"id": 1, "name": "TestUser"}`
2. Ensures the override is cleaned up after the test
3. Explains why this is better than mocking `verify_jwt`

**E4. Sub-dependency that uses path parameters.**
Design a dependency `get_owned_item(item_id: int, user=Depends(get_current_user))` that:
- Reads `item_id` from the path (FastAPI resolves it automatically)
- Checks that the item exists in `items_db`
- Checks that `item["owner_id"] == user["id"]`
- Returns the item if both checks pass, raises appropriate HTTP errors otherwise

Write the full dependency + an endpoint `DELETE /items/{item_id}` that uses it.

---

## ⚫ SECTION F — Architecture & Design

> *No single correct answer. Justify your choices with trade-offs.*

**F1. The three-layer error strategy.**
You're building an API for a fintech startup. Design a complete error handling system:
- All errors must follow `{"success": false, "error": {"code": N, "type": "SNAKE_CASE", "message": "..."}}`.
- Validation errors must expose individual field names.
- Production must never expose stack traces.
- Different HTTP status codes for: not found, permission denied, business rule violation, duplicate resource, invalid input.

Write the architecture (exception classes + global handlers + a sample endpoint using it all). No external libraries.

**F2. Router organisation.**
You're building a multi-tenant SaaS API with these resource groups:
- Public: `/health`, `/docs`
- User-facing: `/users`, `/products`, `/orders` — require user token
- Admin: `/admin/users`, `/admin/metrics` — require admin token
- Internal: `/internal/jobs`, `/internal/cache` — require internal service key (different header)

Design the router structure in `main.py`. Show: which dependencies go where (router-level vs endpoint-level), file layout, how `include_router` calls look. You don't need full implementations — just signatures and structure.

**F3. Middleware vs dependency trade-off.**
You need to implement request ID tracking: generate a UUID per request, attach it to every log line, and return it as `X-Request-ID` in every response. Two engineers disagree:
- **Engineer A:** Use `@app.middleware("http")` — it covers every response including errors.
- **Engineer B:** Use a `Depends()` injected into every endpoint — gives more control per route.

Who is right? Is there a third option? Write code for each approach, identify what each one misses, and give your recommendation.

**F4. File upload architecture.**
Design an endpoint `POST /documents/upload` that:
- Accepts `title` (form), `category` (form, one of `contract|report|invoice`), and `file` (UploadFile)
- Validates: PDF or DOCX only, ≤ 10 MB, title 1–200 chars
- Uses a dependency `get_upload_context` that returns the current user + a generated upload ID
- Returns `201` with `{ upload_id, title, category, filename, size_kb }`
- Uses a custom `InvalidFileException` for file-related errors

Write the full implementation.

---

## 🟠 SECTION G — Build Challenges

> *Production-quality code. Clean structure, validation, error handling, DI, response models.*

### G1. Team Management API (Modular, Multi-router)

Build a team management API with these files:
```
main.py
dependencies.py
models.py
routers/
    teams.py
    members.py
```

**Requirements:**

`models.py`:
- `TeamCreate`: `name` (3–50 chars), `description` (≤ 500 chars, optional)
- `TeamOut`: `id`, `name`, `description`, `member_count` (int, default 0)
- `MemberCreate`: `username` (3–20 chars, `^[a-z0-9_]+$`), `role` (`Literal["owner","admin","member"]`), `team_id` (int)
- `MemberOut`: `id`, `username`, `role`, `team_id`
- `MemberUpdate`: all fields optional

`dependencies.py`:
- `pagination`: class-based, `max_limit=50`, returns `{page, limit, offset}`
- `get_current_user`: reads `token` query param, two users: `{"token": "user1", "id": 1, "is_admin": False}`, `{"token": "admin1", "id": 2, "is_admin": True}`
- `require_admin`: sub-dep of `get_current_user`

`routers/teams.py`:
- `POST /teams` → 201
- `GET /teams` → paginated, with optional `?search=` filter (case-insensitive name match)
- `GET /teams/{team_id}` → 404 if not found
- `DELETE /teams/{team_id}` → admin only, 204

`routers/members.py`:
- `POST /teams/{team_id}/members` → 409 if username already in that team
- `GET /teams/{team_id}/members` → list all members
- `PATCH /members/{member_id}` → partial update, `exclude_unset=True`
- `DELETE /members/{member_id}` → admin or self only

`main.py`:
- Include both routers, CORS middleware, request ID middleware
- Global error handler with `{"success": false, "error": {...}}` shape

---

### G2. File Processing Service (Upload, Validate, Store)

Build a standalone `main.py` for a document service:

**Endpoints:**
- `POST /upload` — accepts `description: Form`, `category: Form` (one of `image|document|data`), `file: UploadFile`
- `GET /files` — lists all stored file metadata
- `GET /files/{file_id}` — returns metadata for one file
- `DELETE /files/{file_id}` — removes the file record (not the actual disk file, just the in-memory record)

**Rules:**
- `image`: JPG/PNG/WEBP only, ≤ 5 MB
- `document`: PDF/DOCX only, ≤ 20 MB
- `data`: CSV/JSON only, ≤ 2 MB
- Reject empty files (0 bytes)
- Save with UUID prefix, store metadata in-memory dict
- Custom `FileValidationError(HTTPException)` for all file rule violations
- Custom `@app.exception_handler` that wraps all `HTTPException`s uniformly
- Middleware that logs `[UPLOAD] filename | category | size_kb` for every successful upload (hint: you'll need to attach metadata to the request state)
- Return `201` on success with `{file_id, original_name, stored_name, category, size_kb, description}`

---

### G3. Request Context System (Middleware + Headers + Cookies)

Build a system where every request gets tracked end-to-end:

**Requirements:**
1. **Middleware:** Generate a UUID `request_id` per request. Attach it to `request.state.request_id`. Return it as `X-Request-ID` in every response.
2. **Middleware:** Track a visit counter per IP in memory. Attach count to `request.state.visit_count`. Add it as `X-Visit-Count` response header.
3. **Cookie:** On `POST /session/start`, create a session with `secrets.token_urlsafe(32)`. Set cookie: `httponly=True`, `samesite="lax"`, `max_age=1800`.
4. **Dependency:** `get_session(session_id: str | None = Cookie(None))` — returns session or raises 401.
5. **Feature flag:** Read `X-Feature-Flags` header (comma-separated: `"beta,dark_mode"`). Create a dependency `require_feature(flag: str)` that checks if the flag is active.
6. **Protected endpoints:**
   - `GET /session/data` — requires session
   - `GET /beta-feature` — requires session + `"beta"` feature flag
   - `POST /session/end` — clears session + deletes cookie

All responses must include `X-Request-ID`. All session errors must use a custom `SessionExpiredException(HTTPException)`.

---

### G4. Web UI + API Hybrid (Templates + Forms + Static + JSON)

Build a note-taking app with both an HTML interface and a JSON API for the same data:

**File structure:**
```
main.py
static/style.css
templates/
    base.html
    notes.html        ← list + add form
    note_detail.html  ← single note view
    404.html          ← custom error page
```

**HTML routes** (return `TemplateResponse`):
- `GET /` → redirect to `/notes`
- `GET /notes` → list all notes, show add form
- `POST /notes` → create via form, redirect `303` to `/notes`
- `GET /notes/{id}` → detail page, show edit form
- `POST /notes/{id}` → update via form, redirect `303`
- `POST /notes/{id}/delete` → delete, redirect `303`

**JSON API routes**:
- `GET /api/notes` → list (with `?search=` and `?tag=` filters)
- `POST /api/notes` → create (JSON body)
- `GET /api/notes/{id}` → get one
- `PUT /api/notes/{id}` → full replace
- `DELETE /api/notes/{id}` → 204

**Requirements:**
- `Note` model: `id`, `title` (1–200), `content` (1–5000), `tags: list[str]`, `created_at`, `updated_at`
- Custom `404.html` page returned for `HTTPException(404)` from HTML routes
- Flash messages on redirect (passed as query param, rendered in `base.html`)
- Static CSS served from `/static/style.css`
- `url_for()` used for all links inside templates
- JSON API uses `response_model=NoteOut` (no `updated_at` exposed) and `response_model_exclude_unset=True` on PATCH

---

## 🟤 SECTION H — Edge Cases & Tricky Behavior

> *Short but sharp. Real gotchas from production FastAPI apps.*

**H1.** You define `router = APIRouter(prefix="/api")` in `routers/users.py` and then do `app.include_router(users.router, prefix="/v1")`. What is the final URL prefix for all routes? What's the idiomatic way to avoid accidental double-prefixing?

**H2.** You have `response_model=UserOut` where `UserOut` has `id: int`. Your endpoint returns `{"id": "not-an-int", "name": "x"}`. Does FastAPI raise an error? If yes, what kind and when? If no, what does the client receive?

**H3.** You upload a `.png` file. `file.content_type` says `image/png`. You reject anything not in `{"image/jpeg", "image/png"}` — so it passes. But the actual file is a PHP script with a `.png` extension. Your validation passed. What is the correct defensive measure? (No external libraries needed — think Python standard library.)

**H4.** A yield dependency opens a resource and yields. The endpoint calls `call_next` (inside middleware, hypothetically). Explain: in what order does cleanup happen for yield dependencies relative to the response being sent to the client?

**H5.** `UploadFile.content_type` returns `None` for a file uploaded from a curl command that didn't set the Content-Type on the part. How should your validation code handle this defensively?

**H6.** You have `@app.middleware("http")` that reads `await request.body()` for logging. An endpoint also reads `await request.body()` (or uses a Pydantic body model). What happens to the second read? How do you fix it?

**H7.** A client sends `X-User-Id: 42` as a header. Your endpoint declares `x_user_id: int = Header(None)`. What is the value of `x_user_id`? Is it `42` (int) or `"42"` (str)?

**H8.** You use `samesite="none"` on a cookie. The browser silently ignores the cookie. Why, and what additional flag is required?

**H9.** You define this in Jinja2:
```html
<a href="/notes/{{ note.id }}">{{ note.title }}</a>
```
vs
```html
<a href="{{ url_for('note_detail', note_id=note.id) }}">{{ note.title }}</a>
```
When does the first approach break but the second doesn't? What specific FastAPI change triggers the breakage?

**H10.** A `@model_validator(mode="before")` receives the **raw input dict** before any field parsing. A `@model_validator(mode="after")` receives the fully-parsed model instance. You need to transform a key — rename `user_name` to `username` in incoming data. Which mode do you use and why? Write the validator.

---

## 🏁 SECTION I — Conceptual Coding

> *Write the precise code that proves understanding. No full endpoints needed — just the critical lines.*

**I1.** Write a `@field_validator` for a `phone` field that:
- Strips all spaces and dashes before validation
- Accepts only digits after stripping
- Enforces exactly 10–15 digits
- Returns the cleaned value

**I2.** Write the full family of models for a `BlogPost` resource:
- `PostBase`: `title` (1–200), `content` (1–10000), `tags: list[str] = []`
- `PostCreate`: extends base, adds `author_id: int`
- `PostOut`: extends base, adds `id`, `author_id`, `published_at: datetime`
- `PostUpdate`: all optional, standalone (no inheritance from base)
- `PostDB`: extends `PostOut`, adds `view_count: int`, `edit_history: list[str]`

Then: which models are safe to use as `response_model`? Which should never be?

**I3.** Write a `Paginator` class-based dependency that:
- Accepts `max_limit` at construction time
- Reads `page` (≥1) and `limit` (≥1, ≤ max_limit) from query
- Validates that `page * limit ≤ 10_000` (a "too deep" pagination guard)
- Returns `{"page", "limit", "offset", "is_last_page": False}` (the `is_last_page` is always `False` — you don't know without a DB)

**I4.** Write a global `RequestValidationError` handler that returns:
```json
{
  "success": false,
  "errors": [
    {
      "location": "body.address.city",
      "message": "Field required",
      "type": "missing"
    }
  ]
}
```
The `location` field must be a dot-joined path, stripping the source prefix (`"body"`, `"query"`, `"path"`).

**I5.** Write a single endpoint `PUT /users/{user_id}/avatar` that:
- `user_id` path param, int ≥ 1
- `display_name`: form field, 2–50 chars
- `avatar`: UploadFile, images only (jpeg/png/webp), ≤ 3 MB
- Returns `201` with `{user_id, display_name, avatar_filename, size_kb}`
- Uses a custom `AvatarTooLargeException(HTTPException)` for size violations

**I6.** Write a middleware that:
- Intercepts all `POST` and `PUT` requests
- Checks if `Content-Type` header starts with `application/json`
- If not, returns `415 Unsupported Media Type` immediately
- Passes everything else through
- Skips the check for `/upload` and `/form-submit` paths

**I7.** Convert this into a clean router-based structure. `main.py` should only create the app and include routers:
```python
# Messy main.py with 40+ endpoints all in one file
@app.get("/products")
@app.post("/products")
@app.get("/products/{id}")
@app.put("/products/{id}")
@app.delete("/products/{id}")
@app.get("/orders")
@app.post("/orders")
@app.get("/orders/{id}")
# ... etc
```
Write the target `main.py` and the skeleton of `routers/products.py` and `routers/orders.py`.

**I8.** Write an endpoint that demonstrates ALL THREE body sources at once:
- Path: `project_id: int` (≥ 1)
- Query: `notify: bool = False`, `priority: int = Query(1, ge=1, le=5)`
- Body model: `TaskCreate` with `title`, `assignee_id`
- Body primitive: `due_date: str = Body(None)` (optional)

Show: the endpoint signature, the exact JSON body shape the client must send, and what happens if `due_date` is omitted.

---

## 🎯 SECTION J — Capstone Reflection

> *Force synthesis. 1–2 paragraphs each.*

**J1.** You've just completed Phase 2. Without looking at any code, write the **complete mental model** of a FastAPI request from the moment it arrives to the moment a response leaves — naming every layer in Phase 2 that can intercept, modify, or terminate the request. Be specific about order.

**J2.** You're joining a team's codebase. The `main.py` is 2000 lines, uses no routers, has error handling in every endpoint individually, has auth repeated in 40 functions, and uses raw `dict` returns with no `response_model`. Write a **refactor plan** in 5 concrete steps, ordered by impact vs effort, using only Phase 1 and Phase 2 knowledge.

**J3.** Which single topic from Phase 2 do you feel least confident about? Name it. Write a 5-line plan to close that gap using only the files already in your `Claude/` folder. Be specific — which `main.py`, which endpoint, what you will modify and test.

---

## ✅ Submission Guide

1. Attempt all sections in order — early sections build vocabulary for later ones.
2. For Build Challenges (G1–G4), create actual runnable files.
3. Mark uncertain answers with `?` — these become your review list before Phase 3.
4. Reply with your answers section-by-section or all at once. I will review each one.

> 🎯 *After completing this assignment, you should be able to design, build, and review any Phase 1 + Phase 2 FastAPI application from a blank file — without referencing documentation.*
