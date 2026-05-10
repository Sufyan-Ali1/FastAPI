# Lesson 3 — First API: GET & POST (and the rest)

> **Goal of this lesson:** Understand HTTP methods and learn to build endpoints for **GET, POST, PUT, DELETE** — the four verbs every API uses.

---

## 1. What is an HTTP method?

When a client (browser, mobile app, frontend) talks to your API, every request includes a **method** that tells the server **what kind of action** the client wants.

There are 4 methods you'll use 99% of the time:

| Method | Meaning | Real-world analogy | Example |
|--------|---------|--------------------|---------|
| **GET** | **Read** data | Looking at a menu | "Give me user 5" |
| **POST** | **Create** new data | Placing a new order | "Create a new user" |
| **PUT** | **Update / Replace** data | Changing your order | "Update user 5" |
| **DELETE** | **Remove** data | Cancel an order | "Delete user 5" |

> 🔑 The URL is the **resource** (the thing).
> The method is the **action** (what to do with it).

Same URL `/users/5` can mean very different things:
- `GET /users/5` → fetch user 5
- `PUT /users/5` → update user 5
- `DELETE /users/5` → delete user 5

---

## 2. Why does this matter?

This is the foundation of **REST APIs** — a worldwide convention every backend developer follows.

If you respect these conventions:
- ✅ Frontend developers know exactly how to use your API
- ✅ Tools like Postman, Swagger, browsers behave correctly
- ✅ Your API is predictable and professional

Mixing them up (e.g. using GET to delete data) breaks caching, security, and confuses everyone.

---

## 3. What is REST? (deep dive)

**REST** stands for **REpresentational State Transfer**.
It is **not** a framework, **not** a library, **not** a tool — it is a **set of design rules** (an "architectural style") for building APIs.

It was introduced by **Roy Fielding** in his 2000 PhD dissertation. Today, **almost every web API in the world follows REST principles** — including Twitter, GitHub, Stripe, YouTube, and the FastAPI APIs you'll build.

### 3.1 The core idea of REST

> "Treat everything in your system as a **resource**, identify each resource with a **URL**, and let clients act on resources using **standard HTTP methods**."

So an API designed in REST style looks like:

| Resource | URL |
|----------|-----|
| All users | `/users` |
| A specific user | `/users/42` |
| All posts of a user | `/users/42/posts` |
| A specific post | `/posts/100` |

And actions are always expressed via the **HTTP method**, never the URL:

| ❌ Not RESTful | ✅ RESTful |
|---------------|----------|
| `GET /getUser?id=42` | `GET /users/42` |
| `POST /createUser` | `POST /users` |
| `POST /deleteUser/42` | `DELETE /users/42` |
| `GET /updateUser?id=42&name=John` | `PUT /users/42` |

> 🔑 The URL describes the **resource**.
> The HTTP method describes the **action**.

### 3.2 The 6 REST principles (rules)

REST is defined by 6 constraints. You don't need to memorize the names — just understand the ideas.

#### 1. Client–Server
The frontend (client) and backend (server) are **separate**. Each can evolve independently. Your FastAPI app is the server; a React app, a mobile app, or `curl` is the client.

#### 2. Stateless
Every request from the client must contain **all the information needed** to handle it. The server does **not** remember anything about previous requests.

✅ Example: every request includes an auth token in the header.
❌ Bad: server stores "user is logged in" in memory between requests.

This makes scaling easy — any server can handle any request.

#### 3. Cacheable
Responses should clearly say whether they can be **cached** by the client/proxies (e.g. via `Cache-Control` headers). GET responses are typically cacheable, POST is not.

#### 4. Uniform Interface
The API uses a **consistent**, predictable structure. This is what makes REST recognizable:
- Resources are nouns in URLs (`/users`, not `/getUsers`)
- HTTP methods do the actions (GET/POST/PUT/DELETE)
- Responses use standard formats (JSON)
- Standard status codes (200, 404, 500…)

#### 5. Layered System
The client doesn't know — and doesn't care — whether it's talking directly to your server, or through a load balancer, a CDN, or a proxy. Each layer just sees HTTP.

#### 6. Code on Demand (optional)
Server can send executable code to the client (e.g., JavaScript). Rarely used in REST APIs — most ignore this one.

### 3.3 RESTful URL design — naming rules

These are conventions every senior backend dev expects you to follow:

| Rule | ✅ Good | ❌ Bad |
|------|--------|-------|
| Use **nouns**, not verbs | `/users` | `/getUsers` |
| Use **plural** for collections | `/posts` | `/post` |
| Use **lowercase** + hyphens | `/blog-posts` | `/BlogPosts` or `/blog_posts` |
| **Hierarchy** for relationships | `/users/42/posts` | `/getPostsByUser?id=42` |
| **No file extensions** | `/users/42` | `/users/42.json` |
| **Filtering** via query params | `/products?category=shoes` | `/products/category/shoes` |

### 3.4 RESTful status codes

REST APIs always use **standard HTTP status codes** to communicate the result:

| Code | Meaning | When |
|------|---------|------|
| `200 OK` | Success | GET / PUT successful |
| `201 Created` | Resource created | POST successful |
| `204 No Content` | Success, nothing to return | DELETE successful |
| `400 Bad Request` | Client sent invalid data | Missing/wrong fields |
| `401 Unauthorized` | Not logged in | Missing token |
| `403 Forbidden` | Logged in but not allowed | Wrong role |
| `404 Not Found` | Resource doesn't exist | `/users/9999` |
| `409 Conflict` | Conflict with current state | Duplicate email |
| `422 Unprocessable Entity` | Validation failed | FastAPI uses this a lot |
| `500 Internal Server Error` | Server crashed | Unhandled exception |

> FastAPI returns these automatically based on what your function does.
> You'll customize them in **Lesson 12 (Status Codes & HTTPException)**.

### 3.5 A complete RESTful "blog" API example

```
GET    /posts              → list all posts
GET    /posts/42           → get post 42
POST   /posts              → create a new post
PUT    /posts/42           → update post 42
DELETE /posts/42           → delete post 42

GET    /posts/42/comments  → list comments on post 42
POST   /posts/42/comments  → add a comment to post 42
DELETE /comments/7         → delete comment 7

GET    /posts?author=john&limit=10  → filtering & pagination
```

This is the **standard pattern** you'll see in every professional codebase.

### 3.6 REST vs other API styles (just so you know they exist)

| Style | Idea | When used |
|-------|------|-----------|
| **REST** | Resources + HTTP methods | 90% of web APIs |
| **GraphQL** | One endpoint, client picks fields | Complex frontends |
| **gRPC** | Binary protocol, super fast | Microservices |
| **SOAP** | XML-based, very old | Legacy enterprise |
| **WebSockets** | Persistent two-way connection | Real-time chat / live data |

For now: **REST is your default**. We'll touch on the others later in Phase 4.

### 3.7 Quick REST checklist

When designing any endpoint, ask yourself:

- [ ] Is the URL a **noun** (resource), not a verb?
- [ ] Am I using the **right HTTP method** for the action?
- [ ] Am I returning the **right status code**?
- [ ] Am I keeping the request **stateless** (auth via header, not server memory)?
- [ ] Are URLs **plural** and **lowercase**?

If yes to all → your API is RESTful. ✅

---

## 4. How FastAPI maps methods to functions

In FastAPI, you simply use a **decorator** that matches the method:

```python
@app.get("/users")       # READ (list)
@app.get("/users/{id}")  # READ (single)
@app.post("/users")      # CREATE
@app.put("/users/{id}")  # UPDATE
@app.delete("/users/{id}") # DELETE
```

Behind the scenes:
1. Uvicorn receives the request and tells FastAPI the method + URL.
2. FastAPI's router checks: *"Do I have a function decorated with this method + URL?"*
3. If yes → it calls that function.
4. If no → it returns `405 Method Not Allowed` or `404 Not Found`.

---

## 5. The 4 main decorators in action

### 🟢 GET — Read data
```python
@app.get("/items")
def list_items():
    return [{"id": 1, "name": "Pen"}, {"id": 2, "name": "Book"}]
```
- No body. Data comes via URL (query/path).
- Should be **safe** (no side effects) and **idempotent** (same result if called 100 times).

### 🟡 POST — Create data
```python
@app.post("/items")
def create_item(item: dict):
    return {"created": item}
```
- Sends a **request body** (JSON).
- Each call **creates a new resource** → not idempotent.

### 🟠 PUT — Update / replace data
```python
@app.put("/items/{item_id}")
def update_item(item_id: int, item: dict):
    return {"updated_id": item_id, "data": item}
```
- Sends a body, updates the entire resource.
- **Idempotent**: same PUT 100 times → same end state.

### 🔴 DELETE — Remove data
```python
@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    return {"deleted_id": item_id}
```
- Usually no body. Just an ID in the URL.

---

## 6. How to test endpoints

### Option 1 — Swagger UI (built-in) ⭐ best for beginners
Go to `http://127.0.0.1:8000/docs` → click any endpoint → "Try it out" → "Execute".
You can test **POST/PUT/DELETE** directly here, no extra tool needed.

### Option 2 — `curl` (command line)
```bash
# GET
curl http://127.0.0.1:8000/items

# POST with JSON body
curl -X POST http://127.0.0.1:8000/items \
     -H "Content-Type: application/json" \
     -d '{"name": "Pen"}'

# DELETE
curl -X DELETE http://127.0.0.1:8000/items/1
```

### Option 3 — Postman / Thunder Client
A GUI app for testing APIs visually.

> ❗ Browsers can only send **GET** requests via URL bar. To test POST/PUT/DELETE you need Swagger UI, curl, or Postman.

---

## 7. Idempotency — important concept

A method is **idempotent** if calling it many times has the **same effect** as calling it once.

| Method | Idempotent? | Why |
|--------|-------------|-----|
| GET | ✅ Yes | Reading data 100 times → same result |
| PUT | ✅ Yes | Replacing with same data 100 times → same final state |
| DELETE | ✅ Yes | Deleting an already-deleted thing → still gone |
| POST | ❌ No | Each call creates a NEW resource → different result every time |

Why care? Because frontends, retries, and load balancers behave differently with idempotent vs non-idempotent calls.

---

## 8. Real-World Use Case

A typical "blog API" looks exactly like this:

| Method | URL | What it does |
|--------|-----|--------------|
| GET | `/posts` | List all blog posts |
| GET | `/posts/42` | Get post #42 |
| POST | `/posts` | Create a new post |
| PUT | `/posts/42` | Update post #42 |
| DELETE | `/posts/42` | Delete post #42 |

This pattern (called **CRUD** — Create, Read, Update, Delete) is used in 90% of all backend APIs in the world.

---

## 9. Mini Task

Open `main.py` in this lesson folder. It contains a tiny in-memory "items" API.

Your tasks:

1. **Run** it: `uvicorn main:app --reload`
2. Open `http://127.0.0.1:8000/docs`
3. From Swagger UI:
   - Use **GET `/items`** → should return an empty list
   - Use **POST `/items`** → create an item like `{"name": "Pen"}`
   - Use **GET `/items`** again → it should now show your item
   - Use **PUT `/items/0`** → update the first item
   - Use **DELETE `/items/0`** → remove it
4. **Bonus**: Add a new endpoint:
   ```python
   @app.get("/items/count")
   def count_items():
       return {"total": len(fake_db)}
   ```

---

## 10. Key Takeaways

- Every HTTP request has a **method** (GET / POST / PUT / DELETE).
- FastAPI decorators directly map to HTTP methods.
- **GET = read, POST = create, PUT = update, DELETE = remove.**
- **GET, PUT, DELETE are idempotent. POST is not.**
- **REST** = treat everything as a resource, identify by URL, act via HTTP methods.
- A RESTful API is **stateless**, **uniform**, and uses **standard status codes**.
- Test using Swagger UI at `/docs` — it's the easiest tool you'll ever use.

---

## ➡️ Next Lesson

**Lesson 4 — Path Parameters**
- Capture values from the URL like `/users/{user_id}`
- Type conversion (str → int automatically)
- Validation with `Path()`
- Why route order matters
