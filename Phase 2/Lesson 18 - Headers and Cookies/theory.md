# Lesson 18 — Headers & Cookies

> **Goal of this lesson:** Read custom request headers, set response headers, and work with cookies — including the security flags that make cookies safe in production.

---

## 1. Reading Request Headers

Use `Header()` to declare a header parameter:

```python
from fastapi import Header

@app.get("/info")
def info(user_agent: str = Header(None)):
    return {"user_agent": user_agent}
```

**Automatic underscore → hyphen conversion:**
HTTP headers use hyphens (`X-Request-ID`), but Python identifiers use underscores. FastAPI converts automatically:

```python
def endpoint(
    x_request_id: str  = Header(None),   # reads X-Request-ID
    accept_language: str = Header(None),  # reads Accept-Language
):
```

To disable conversion:
```python
x_request_id: str = Header(None, convert_underscores=False)
```

### Headers with multiple values

```python
from typing import Annotated

@app.get("/items")
def items(x_token: Annotated[list[str] | None, Header()] = None):
    # Client can send: X-Token: abc   X-Token: xyz
    return {"tokens": x_token}
```

---

## 2. Required vs Optional Headers

```python
# Required — 422 if missing
authorization: str = Header(...)

# Optional — None if missing
x_request_id: str | None = Header(None)

# With default
accept_language: str = Header("en")
```

---

## 3. Setting Response Headers

### Via the injected `Response` object

```python
from fastapi import Response

@app.get("/data")
def get_data(response: Response):
    response.headers["X-Custom-Header"] = "some-value"
    response.headers["Cache-Control"]   = "max-age=3600"
    return {"data": "..."}
```

### Via `JSONResponse`

```python
from fastapi.responses import JSONResponse

@app.get("/data")
def get_data():
    return JSONResponse(
        content={"data": "..."},
        headers={"X-Custom-Header": "some-value"},
    )
```

### Via middleware (global, every response)

```python
@app.middleware("http")
async def add_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-App-Version"] = "1.0.0"
    return response
```

---

## 4. Common Response Headers

| Header | Purpose | Example value |
|--------|---------|---------------|
| `Cache-Control` | Caching instructions | `max-age=3600`, `no-cache` |
| `ETag` | Resource version for conditional requests | `"abc123"` |
| `X-Request-ID` | Trace a request through logs | `a3f1b2c4` |
| `X-Rate-Limit-Remaining` | Tell client how many calls left | `42` |
| `Content-Disposition` | Trigger a file download | `attachment; filename="report.pdf"` |
| `Location` | Redirect target (used with 201/301/302) | `/users/42` |

---

## 5. Cookies — The Basics

Cookies are key-value pairs stored in the browser and sent automatically with every subsequent request to the same domain.

**Setting a cookie:**
```python
from fastapi import Response

@app.post("/login")
def login(response: Response, username: str):
    response.set_cookie(key="session_id", value="abc123")
    return {"message": "Logged in"}
```

**Reading a cookie:**
```python
from fastapi import Cookie

@app.get("/me")
def me(session_id: str | None = Cookie(None)):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    return {"session_id": session_id}
```

**Deleting a cookie:**
```python
@app.post("/logout")
def logout(response: Response):
    response.delete_cookie("session_id")
    return {"message": "Logged out"}
```

---

## 6. Cookie Security Flags — Critical for Production

| Flag | What it does | When to use |
|------|-------------|-------------|
| `httponly=True` | JavaScript cannot read the cookie | **Always** for session/auth cookies |
| `secure=True` | Cookie only sent over HTTPS | **Always in production** |
| `samesite="lax"` | Prevents CSRF in most cases | Default recommendation |
| `samesite="strict"` | Never sent cross-site (more restrictive) | High-security apps |
| `samesite="none"` | Sent cross-site (requires `secure=True`) | Cross-origin embedded apps |
| `max_age=3600` | Expires in N seconds | Session length control |
| `expires=datetime` | Absolute expiry datetime | Alternative to max_age |
| `domain="myapp.com"` | Restricts cookie to a domain | Multi-subdomain apps |
| `path="/"` | Which paths the cookie is sent on | Default is `/` |

```python
response.set_cookie(
    key="session_id",
    value="abc123",
    max_age=3600,          # 1 hour
    httponly=True,         # JS can't read it → prevents XSS theft
    secure=True,           # HTTPS only → prevents network sniffing
    samesite="lax",        # prevents CSRF
)
```

> 🔑 **`httponly=True` is the single most important cookie flag.** It prevents JavaScript (including malicious injected scripts) from reading your auth cookie — defeating the most common XSS attack vector.

---

## 7. Cookie-Based Session vs JWT

| | Cookie session | JWT (Authorization header) |
|---|---|---|
| Storage | Browser cookie store | Browser localStorage / memory |
| XSS protection | `httponly` prevents JS access | Stored in JS-accessible memory |
| CSRF risk | Yes (cookies auto-send) | No (must be manually attached) |
| Mobile friendly | Less common | Standard |
| Server state needed? | Yes (session store) | No (self-contained) |

We'll implement JWT in **Lesson 29**. For now, cookies are the simpler session mechanism.

---

## 8. Real-World Pattern — Secure Login/Logout

```python
import secrets
from datetime import datetime, timedelta

# Fake session store (use Redis in production)
sessions: dict[str, dict] = {}

FAKE_USERS = {"sufyan": "password123"}

@app.post("/login")
def login(response: Response, username: str, password: str):
    if FAKE_USERS.get(username) != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "user": username,
        "expires": datetime.utcnow() + timedelta(hours=1),
    }

    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=3600,
        httponly=True,
        secure=False,    # Set True in production (requires HTTPS)
        samesite="lax",
    )
    return {"message": f"Welcome, {username}!"}


def get_session(session_id: str | None = Cookie(None)):
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = sessions[session_id]
    if session["expires"] < datetime.utcnow():
        del sessions[session_id]
        raise HTTPException(status_code=401, detail="Session expired")
    return session


@app.get("/profile")
def profile(session = Depends(get_session)):
    return {"user": session["user"]}


@app.post("/logout")
def logout(response: Response, session_id: str | None = Cookie(None)):
    if session_id in sessions:
        del sessions[session_id]
    response.delete_cookie("session_id")
    return {"message": "Logged out"}
```

---

## 9. Setting a `Location` Header on 201 Created

REST best practice: when you create a resource, include a `Location` header pointing to it.

```python
@app.post("/users", status_code=201)
def create_user(user: UserCreate, response: Response):
    new_user = db.create(user)
    response.headers["Location"] = f"/users/{new_user.id}"
    return new_user
```

---

## 10. Mini Task

Open `main.py`:

1. Run: `uvicorn main:app --reload`
2. In `/docs`:
   - **POST `/login`** with `username=sufyan&password=secret` → check cookie in response
   - **GET `/profile`** → should fail (no cookie) if called manually; works if browser session is active
   - **POST `/logout`** → cookie should be cleared
   - **GET `/headers`** → see request headers echoed back
   - **GET `/set-headers`** → inspect `X-Custom`, `Cache-Control` in response headers
3. Open browser dev tools → Application → Cookies → confirm `httponly` flag is checked
4. **Bonus:** Add a `GET /admin` route that reads a cookie `admin_token`, validates it equals `"secret-admin"`, and returns admin data.

---

## 11. Key Takeaways

- `Header()` reads request headers; Python underscores map to HTTP hyphens automatically.
- Set response headers via the injected `Response`, `JSONResponse`, or middleware.
- `Cookie()` reads cookies; `response.set_cookie()` sets them; `response.delete_cookie()` clears them.
- **`httponly=True`** is non-negotiable for auth cookies — prevents XSS theft.
- **`secure=True`** ensures cookies only travel over HTTPS in production.
- **`samesite="lax"`** is the safe default that prevents most CSRF attacks.
- Use `secrets.token_urlsafe(32)` for session IDs — never a predictable value.

---

## ➡️ Next Lesson

**Lesson 19 — Static Files & Templates (Jinja2)**
- Serving static files (CSS, JS, images)
- `StaticFiles` mount
- Jinja2 templates for server-side HTML rendering
- Combining templates with FastAPI endpoints
