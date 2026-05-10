# 📝 Phase 1 — Comprehensive Assignment

> **Goal:** Lock in *every* important concept from Lessons 1–8 so you never need to revisit them.
> **Difficulty:** High. Most questions are advanced, scenario-based, or debugging-style.
> **How to attempt:** Don't run the code first. **Think it through, write your answer, then verify.** That's where retention comes from.

---

## 🧭 What this assignment covers

- **L1** What is FastAPI / Starlette / Pydantic / Uvicorn
- **L2** Installation, virtual environments, project structure
- **L3** GET / POST / PUT / DELETE, REST principles, idempotency, statelessness
- **L4** Path parameters, `Path()`, route ordering, `Enum`, `:path`
- **L5** Query parameters, `Query()`, optional vs required, lists, multi-value
- **L6** Pydantic `BaseModel`, `Field()`, nested models, validation
- **L7** Mixing path + query + body, `Body()`, `embed=True`
- **L8** Status codes, `HTTPException`, `JSONResponse`, headers, 204

---

## 🟢 SECTION A — Warm-up (Conceptual)

> *Build momentum. One or two short sentences each.*

**A1.** In one sentence each, define: **Starlette**, **Pydantic**, **Uvicorn**, **ASGI**.
Why does FastAPI need *all four* instead of just one of them?

**A2.** Why is using a virtual environment (`venv`) a non-negotiable habit, even on a single-developer laptop? Give one concrete failure mode that arises if you don't.

**A3.** What does the `--reload` flag in `uvicorn main:app --reload` actually do, and **why must you never use it in production**?

**A4.** Explain the difference between **path parameter** and **query parameter** in *one sentence*, then give a URL where the same value would arguably work as either, and justify which is better.

**A5.** Why does FastAPI return **422** (not 400) when a Pydantic body fails validation? What does that distinction tell the client?

**A6.** A junior dev says: *"`return JSONResponse({...})` and `return {...}` are identical, just different style."* Where exactly is this wrong?

---

## 🟡 SECTION B — Deep Conceptual

> *Test mental models, not memorisation. Aim for 3–6 sentences each.*

**B1. Idempotency vs Safety.**
Classify each as **safe**, **idempotent (but not safe)**, or **neither**:
GET, POST, PUT, DELETE, PATCH.
Then answer: *"If `DELETE /items/5` returns 404 the second time you call it, has it violated idempotency?"* Defend your answer.

**B2. Statelessness.**
A teammate stores the logged-in user inside `app.state.current_user` so they don't have to "pass it around". List **three** concrete things that will break in production because of this. Tie each one to the REST stateless constraint.

**B3. The decision tree FastAPI uses.**
For an arbitrary function parameter `x`, write the **exact 3-step rule** FastAPI uses to decide whether `x` is a path / query / body parameter. Why does this rule mean you almost never need `Path()`, `Query()`, or `Body()` in trivial cases?

**B4. The `=` Trap.**
Explain *precisely* why these two declarations behave very differently in FastAPI:
```python
def f(role: str | None = None): ...
def f(role: str = None): ...
```
What does Pydantic/FastAPI do under the hood in each case?

**B5. `gt`/`lt` vs `ge`/`le` and the Swagger surprise.**
You added `Path(..., gt=0, lt=10)` and a colleague added `Path(..., ge=1, le=9)`. Functionally similar — but in Swagger UI, one field rejects bad input *before* sending and the other lets it reach the server. Which is which, and why? (Hint: HTML5.)

**B6. Multiple body params.**
You declare two Pydantic models in one POST. Show:
1. The exact JSON shape FastAPI expects from the client.
2. The exact JSON shape if you change one of them to `embed=True` and remove the other.
3. The exact JSON shape if you change one of them to `Body(...)` with a primitive `int`.

**B7. The Pydantic v1 → v2 dial.**
Name **three** behavioural differences you'd hit if you copy-pasted v1 model code into a v2 codebase. (Think method names, validator decorators, config style.)

**B8. Why dict is bad.**
List the **five concrete losses** when you write `def create_item(item: dict)` instead of using a Pydantic model. For each loss, name a specific FastAPI feature that disappears.

---

## 🟤 SECTION B2 — Conceptual Coding (Reason in Code)

> *Each question forces you to **write or read** a tiny snippet that proves you understand a concept. No long endpoints — just the precise lines that test the idea.*

**B2-1. Minimal model.**
Write the *smallest* Pydantic model that accepts and validates this exact JSON. No `Field()` constraints — just type hints. Then mark each field **required** or **optional** based on the example alone:
```json
{
  "user":   { "id": 42, "tags": ["admin", "verified"] },
  "scores": [10, 20, 30],
  "active": true,
  "note":   null
}
```

**B2-2. The signature challenge.**
Write the **exact function signature only** (no body) for an endpoint that:
- URL: `/teams/{team_id}/members/{member_id}`
- `team_id`, `member_id` → int, ≥ 1
- Query: `role: str | None = None`, `active: bool = True`
- Body: a model `MemberUpdate` (name, email)
- Body: a primitive `note: str` ≤ 200 chars, optional, **must live inside the JSON body**

**B2-3. JSON → models.**
The client sends:
```json
{
  "name": "iPhone",
  "variants": [
    { "color": "red",  "stock": 5 },
    { "color": "blue", "stock": 0 }
  ],
  "manufacturer": { "name": "Apple", "country": "US" }
}
```
Write the `Product`, `Variant`, and `Manufacturer` models with: `stock ≥ 0`, `name` 1–100 chars, `country` exactly 2 uppercase letters (use regex).

**B2-4. Three flavours of optional.**
Show all **three** ways to declare an optional `bio` field in a Pydantic model. For each, write:
1. The declaration line.
2. What the model looks like when `"bio"` is *missing* from the JSON.
3. What happens when the client sends `"bio": null`.

**B2-5. Same URL, three methods.**
Write the **decorators + signatures** (no body) for `GET /items/{id}`, `PUT /items/{id}`, `DELETE /items/{id}` — each with the correct status code on the decorator and a return type hint where it makes sense.

**B2-6. The `Annotated[]` translation.**
Translate this older-style code to **modern `Annotated[]`** style. Don't change behaviour:
```python
def search(
    q: str = Query(..., min_length=3),
    tags: list[str] | None = Query(None),
    page: int = Query(1, ge=1),
):
    ...
```
In one sentence: why does the FastAPI team prefer `Annotated[]` now?

**B2-7. Flag in body or query?**
For `POST /users` with a body `User` and a flag `send_welcome_email: bool`, write **both** versions — (a) the flag as a **query param**, (b) the flag *inside* the JSON body. Then say which is better and why.

**B2-8. The mutable-default mistake.**
Write a Pydantic model where `created_at` defaults to "right now". Then write the **wrong** version that gives every record created across the app's uptime the **same** timestamp. Explain in one line why it happens.

**B2-9. Hide a field from the response.**
Without using `response_model` (that's Lesson 10), make sure `password_hash` is **never** returned to the client even though your function works with it internally. Write the smallest endpoint that proves this. (Hint: two models, not one.)

**B2-10. Conditional status code.**
Write a `POST /signup` endpoint that:
- Returns **201** if a new user was created
- Returns **200** if the user already existed (silent login)
- Sets a `X-User-Id` response header in **both** cases
- Uses the injected `Response` object — *not* `JSONResponse`

**B2-11. The right error, every time.**
For each scenario, write the **exact** `raise HTTPException(...)` line with the right status code:
1. The user tried to delete someone else's post.
2. JWT token is missing entirely.
3. Trying to register an email that already exists.
4. Valid request, but an upstream service we depend on is down.
5. The endpoint exists but only supports POST and the client sent GET. ⚠️ *Trick: does FastAPI handle this one for you?*

**B2-12. Path-overlap puzzle.**
Three routes are declared in this order:
```python
@app.get("/users/me")
@app.get("/users/{user_id}")
@app.get("/users/{user_id:int}")
```
1. Which routes are reachable? Which are dead code?
2. What does `{user_id:int}` actually mean in Starlette/FastAPI, and is it the same as just typing `user_id: int` in the function?

**B2-13. `Enum` vs `Literal`.**
Write a model with a `status` field that only accepts `"draft" | "published" | "archived"`:
1. Once using `Enum`.
2. Once using `Literal[...]` from `typing`.
When would you pick each? (Think: reusability, OpenAPI docs, runtime values.)

**B2-14. Reverse-engineer the OpenAPI.**
Given this slice of an OpenAPI document, write the **FastAPI Python code** that would generate it:
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

**B2-15. The exact body.**
Given:
```python
@app.post("/orders")
def create(user: User, item: Item, priority: int = Body(..., ge=1, le=5)):
    ...
```
Write the **exact** JSON body the client must send (no extra keys). Then rewrite the endpoint so the client can instead send:
```json
{ "order": { "user": {...}, "item": {...}, "priority": 3 } }
```
without changing field names.

**B2-16. Refactor for clarity.**
Rewrite this monstrosity into a clean, idiomatic FastAPI endpoint. Fix every issue you can identify (there are at least 6):
```python
@app.post("/users/")
def create_user(data: dict, response: Response):
    if "name" not in data: return JSONResponse({"err": "name required"}, 400)
    if len(data["name"]) < 2: return JSONResponse({"err": "too short"}, 400)
    if "age" in data and data["age"] < 0: return JSONResponse({"err": "bad age"}, 400)
    response.status_code = 201
    return data
```

---

## 🔵 SECTION C — Debugging (Find the Bug)

> *Each snippet has at least one bug or anti-pattern. Identify it, explain WHY it's broken, and write the fix.*

**C1.**
```python
@app.get("/items/{item_id}")
def get_item(item_id: int): ...

@app.get("/items/latest")
def latest(): ...
```
Why will `/items/latest` never run? Fix it without changing the URLs.

**C2.**
```python
class User(BaseModel):
    name: str = Field(..., min_length=2)
    age: int = Field(0, ge=0)

@app.post("/users")
def create(user: User, audit: bool):
    return user
```
The client sends a perfectly valid `User` body to `POST /users` and gets a 422 saying `audit` field is required. Why? Two valid fixes — give both.

**C3.**
```python
@app.get("/products")
def products(min_price: float = Query(ge=0)):
    return {"min_price": min_price}
```
The user wanted `min_price` to be **optional**. It isn't. Why, and what's the minimal change?

**C4.**
```python
@app.delete("/items/{id}", status_code=204)
def delete_item(id: int):
    return {"deleted": id}
```
Run it and the client sees a warning / unexpected behaviour. What's wrong with returning a body alongside a 204?

**C5.**
```python
@app.post("/orders")
def create_order(user: User, item: Item, priority: int):
    ...
```
Client sends:
```json
{ "user": {...}, "item": {...}, "priority": 3 }
```
…and gets 422 saying `priority` is missing as a *query parameter*. Why? Fix it in one line.

**C6.**
```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = db.get(user_id)
    if not user:
        return {"error": "not found"}, 404
    return user
```
Two things wrong here — one Pythonic, one FastAPI-idiomatic. Identify and fix both.

**C7.**
```python
class Item(BaseModel):
    tags: list = []
```
Why is this a footgun even though it "works"? Rewrite it correctly.

---

## 🟣 SECTION D — Predict the Output

> *No running the server. Reason it out.*

**D1.** Given:
```python
@app.get("/items")
def list_items(limit: int = 10, in_stock: bool = True):
    return {"limit": limit, "in_stock": in_stock}
```
For each URL, write the JSON response **or** the status code if it errors:
1. `/items`
2. `/items?limit=5`
3. `/items?limit=abc`
4. `/items?in_stock=yes`
5. `/items?in_stock=maybe`
6. `/items?limit=5&in_stock=0&limit=20` *(yes, twice)*

**D2.** Given:
```python
@app.get("/files/{path:path}")
def get_file(path: str): return {"path": path}
```
Output for:
1. `/files/a.txt`
2. `/files/folder/sub/a.txt`
3. `/files/`

**D3.** Given:
```python
class Address(BaseModel):
    city: str
class User(BaseModel):
    name: str
    age: int = 18
    address: Address
```
For each body sent to `POST /users`, predict status + key error or success:
1. `{ "name": "A", "address": {"city": "X"} }`
2. `{ "name": "A", "age": "20", "address": {"city": "X"} }`
3. `{ "name": "A", "address": "Karachi" }`
4. `{ "name": "A", "address": {} }`

---

## 🔴 SECTION E — Design Scenarios

> *No code required (unless you want). 4–8 sentences each. Justify trade-offs.*

**E1. Pagination URL design.**
You're building a `GET /comments` endpoint. Design the query parameters for **search + filter + paginate + sort**, with sensible defaults and validation. List the params, types, defaults, and the constraints you'd put on each. Why those defaults?

**E2. Path or Query?**
For each, decide path vs query and justify in one sentence:
1. The user's ID for fetching their profile.
2. A filter "show only verified users".
3. The post ID *and* the comment ID inside that post.
4. A search keyword.
5. The language code for an i18n response (`en`, `ur`, `ar`).
6. A boolean flag "include deleted".
7. The version of the API (`v1`, `v2`).

**E3. Status codes for a create-or-update endpoint.**
You build `PUT /users/{id}` that creates the user if they don't exist and updates them if they do. What status code(s) do you return in each case, and why? What does the spec say (look up if needed)?

**E4. Body shape choice.**
You're designing `POST /transfer` to move money between accounts. Three options:
- A) Two body params: `from: Account`, `to: Account`, plus `amount: int = Body(...)`
- B) One model `Transfer { from, to, amount }`
- C) Path: `/accounts/{from_id}/transfer/{to_id}`, body `{ amount }`

Pick one and defend it on **clarity, REST-compliance, and security**.

---

## ⚫ SECTION F — Build Challenges

> *Write actual code. Aim for production-quality: validation, status codes, errors, docs.*

### F1. The "Library API" (small but complete)

Build endpoints for a **library** with these rules:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/books` | POST | Create a book |
| `/books` | GET | List with filters: `author`, `min_year`, `max_year`, `available`, `page`, `limit` |
| `/books/{book_id}` | GET | Fetch one book; 404 if missing |
| `/books/{book_id}` | PUT | Replace entire book |
| `/books/{book_id}/borrow` | POST | Mark as borrowed; 409 if already borrowed |
| `/books/{book_id}` | DELETE | Remove; 204 |

**Requirements:**
- `Book` model with `id`, `title` (1–200 chars), `author` (1–100 chars), `year` (≥ 1450 — first printed book), `available: bool = True`
- POST returns **201**
- DELETE returns **204** with no body
- 409 on borrowing an already-borrowed book
- 404 with `HTTPException` for any missing book
- `page ≥ 1`, `1 ≤ limit ≤ 100`
- Use a dict as in-memory storage

Then **explain in 5 lines** which lessons each piece comes from.

### F2. The "URL Shortener" Bonus

Build:
- `POST /shorten` body `{ url: HttpUrl, custom_code?: str (3–10 chars, regex `^[a-z0-9_-]+$`) }`. Returns **201** with `{ code, short_url }`. **409** if `custom_code` is already taken.
- `GET /s/{code:path}` returns the original URL in JSON (don't actually redirect — that's Lesson 33).
- `DELETE /s/{code}` returns **204**.

Explain why `code:path` is the wrong choice here, and what the right path declaration is.

### F3. Validation gauntlet

Without using any custom validator (just `Field()`), declare a model `SignupForm` enforcing:
- `username`: 3–20 chars, lowercase letters + digits + underscore only, must start with a letter
- `email`: standard format
- `password`: at least 8 chars, must contain a digit and a non-alphanumeric char *(hint: think about whether plain `Field()` regex can do "must contain" — and if not, what your move is)*
- `age`: 13–120
- `referral_code`: optional, exactly 8 uppercase alphanumeric chars

If any of these can't be done with `Field()` alone, **say so explicitly** and explain what tool from a future lesson is needed.

---

## 🟠 SECTION G — Tricky / Edge Cases

> *Real-world gotchas. Short answers.*

**G1.** What's the difference between `tags: list[str] = []` and `tags: list[str] = Field(default_factory=list)` inside a Pydantic model? When does it actually bite?

**G2.** You declared `email: EmailStr` and import fails with `pydantic[email]`-related error. Why? Fix?

**G3.** Why does `bool` accept `"yes"`, `"on"`, `"1"`, `"true"` but reject `"maybe"`?

**G4.** A client posts `{"age": "22"}` to a model with `age: int`. Does it work? What about `{"age": "twenty"}`? What about `{"age": 22.7}`? Explain each.

**G5.** What happens if you write two `@app.get("/users")` decorators with different parameters? Which one wins? What's the underlying mechanism?

**G6.** You return a `Pydantic` model containing a `datetime`. The frontend complains the value has microseconds + a `+00:00` suffix it can't parse. Where in the chain is the JSON conversion happening, and what's the cleanest place to control the format?

**G7.** The Swagger `/docs` page is loading but your custom endpoint is missing from it. Name **three** reasons that can happen.

**G8.** A `PUT /items/{id}` endpoint should be idempotent. What if the body contains `created_at: datetime = Field(default_factory=datetime.now)` — does that break idempotency? Why or why not?

---

## 🏁 SECTION H — Capstone Reflection

> *Free-form. 1–2 paragraphs each. Force yourself to articulate.*

**H1.** Walk through what happens — second by second — from the moment a client sends `POST /users` with a JSON body, to the moment they receive a 201 response. Mention **every layer**: TCP, Uvicorn, ASGI, Starlette, FastAPI, Pydantic, your function, and the response trip back. Aim for ~10 numbered steps.

**H2.** You've finished Phase 1. Without rereading the lessons, write a *one-paragraph* mental model of FastAPI: what it is, why it exists, what its three "magic abilities" are, and what each one is *actually* doing under the hood (no hand-waving).

**H3.** Identify **the single concept from Phase 1** you feel least confident about. Write down a 5-line plan to fix that gap (re-read which file, build which mini-test, etc.). This is the most valuable answer in the whole assignment — be honest.

---

## ✅ How to submit

For any answer you're unsure about, **mark it with `?`** when you reply. We'll go through them together and I'll point out what to revisit before moving to Phase 2.

> 🎯 *Aim for accuracy over speed. The whole point is that after this assignment, you should be able to write any Phase-1 endpoint from a blank file without looking things up.*
