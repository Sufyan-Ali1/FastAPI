# Lesson 29 — Authentication & Authorization

> **Goal of this lesson:** Add real security. Learn **password hashing** (bcrypt), the **OAuth2 Password Flow**, **JWT** tokens (create, validate, refresh), the **`Depends(get_current_user)`** pattern, **role-based access control (RBAC)**, and **API keys**.
>
> Every assignment so far faked identity with a header like `X-User-Id`. This lesson replaces that with genuine authentication. `main.py` is a runnable, database-backed auth API.

---

## 1. Authentication vs Authorization

Two different questions people constantly conflate:

| | **Authentication (AuthN)** | **Authorization (AuthZ)** |
|---|---|---|
| Question | **Who are you?** | **What are you allowed to do?** |
| Proves | Identity (login) | Permission (roles/scopes) |
| Example | "This request is from user `alice`." | "`alice` is an admin, so she can delete users." |
| Fails with | `401 Unauthorized` | `403 Forbidden` |

You always authenticate **first** (establish who), then authorize (check what they may do). This lesson covers both, in that order.

> 🔑 `401` = "I don't know who you are (or your token is invalid)." `403` = "I know who you are, but you're not allowed." Using the right code matters.

---

## 2. Password Hashing — Never Store Plaintext

Rule zero of auth: **never store passwords as plaintext.** If your database leaks, every password is exposed (and reused on other sites). Instead you store a **hash**.

**Hashing ≠ encryption:**

| | Encryption | Hashing |
|---|---|---|
| Reversible? | Yes (with the key) | **No** — one-way |
| Use for passwords? | No | **Yes** |
| Verify a password | — | Hash the input, compare to stored hash |

You never "decrypt" a password. At login you **hash the submitted password and compare** it to the stored hash.

### 2.1 Salt and slow hashing

A good password hash must be:

- **Salted** — a random value mixed in so identical passwords produce different hashes, defeating precomputed "rainbow table" attacks.
- **Slow** — deliberately expensive to compute, so brute-forcing millions of guesses is impractical. (Fast hashes like MD5/SHA-256 are **wrong** for passwords.)

**bcrypt** does both: it generates a salt and applies a tunable "cost factor." That's why we use it.

```python
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

The stored hash (e.g. `$2b$12$...`) embeds the algorithm, cost, and salt — everything needed to verify later.

> ⚠️ **The `passlib` gotcha.** Many older tutorials use `passlib`'s `CryptContext`. But `passlib` (last released 2020) is **broken with modern `bcrypt` 4.x/5.x** — you get `AttributeError: module 'bcrypt' has no attribute '__about__'`. This course uses the **`bcrypt` library directly**, which is maintained and simpler. The syllabus mentions passlib for historical awareness; prefer bcrypt directly.

> 💡 bcrypt only hashes the first **72 bytes** of a password. Validate a sensible `max_length` on the password field so long inputs don't silently truncate.

---

## 3. The Token Model — Why JWT

After a user logs in with a password, how does the *next* request prove who they are? We don't want them to send their password every time. Two classic approaches:

| | **Sessions** (server state) | **Tokens / JWT** (stateless) |
|---|---|---|
| Server stores | A session record per login | Nothing — the token is self-contained |
| Client sends | A session id cookie | A signed token (usually a header) |
| Scaling | Needs shared session store | Any server can verify the signature |
| Fits REST's statelessness | Less naturally | **Yes** |

FastAPI's ecosystem leans on **JWT (JSON Web Tokens)**: the server issues a **signed** token at login; the client sends it on every request; the server verifies the signature — **no lookup required**.

---

## 4. JWT Anatomy

A JWT is three base64url parts joined by dots: `header.payload.signature`.

```
eyJhbGciOiJIUzI1NiJ9 . eyJzdWIiOiJhbGljZSIsImV4cCI6MTcuLn0 . 4pX9...signature
     header                        payload (claims)                 signature
```

- **Header** — the algorithm, e.g. `{"alg": "HS256", "typ": "JWT"}`.
- **Payload (claims)** — JSON data about the user, e.g. `{"sub": "alice", "role": "admin", "exp": 1712345678}`.
  - `sub` (subject) — who the token is about.
  - `exp` (expiry) — a timestamp after which the token is invalid.
- **Signature** — the header+payload signed with your **secret key**. Anyone can *read* the payload, but only the holder of the secret can produce a valid signature.

> 🔑 **A JWT is signed, NOT encrypted.** The payload is only base64-encoded — anyone can decode and read it. Never put secrets (passwords, card numbers) in a JWT. The signature guarantees *integrity* (it wasn't tampered with) and *authenticity* (your server issued it), not confidentiality.

```python
import jwt  # PyJWT
from datetime import datetime, timedelta, timezone

SECRET_KEY = "..."          # 32+ random bytes, from config/env - never hardcode in real apps
ALGORITHM = "HS256"

def create_access_token(data: dict, minutes: int = 15) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # raises on bad/expired
```

`jwt.decode` verifies the signature **and** the `exp` automatically, raising `ExpiredSignatureError` or `InvalidTokenError` — you turn those into `401`.

> 💡 Use **PyJWT** (`import jwt`). The old `python-jose` also appears in tutorials, but PyJWT is what FastAPI's official docs now use and is actively maintained.

---

## 5. OAuth2 Password Flow in FastAPI

FastAPI has first-class support for the **OAuth2 Password Flow** — the standard "username + password → token" login. Two pieces:

```python
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# Declares the scheme; tells Swagger where to get a token; extracts the
# "Authorization: Bearer <token>" header on protected routes.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
```

- **`OAuth2PasswordBearer(tokenUrl="token")`** — a dependency that pulls the bearer token out of the `Authorization` header, and powers the "Authorize" button in `/docs`.
- **`OAuth2PasswordRequestForm`** — a dependency that reads the standard form fields `username` and `password` from the login request.

The login endpoint:

```python
@app.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    access = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": access, "token_type": "bearer"}
```

- The client POSTs `username`/`password` as **form data** (not JSON — that's the OAuth2 standard).
- On success it gets `{"access_token": "...", "token_type": "bearer"}`.
- The `WWW-Authenticate: Bearer` header on the 401 is part of the spec.

---

## 6. The `get_current_user` Dependency

This is the heart of the pattern. A dependency that: extracts the token → decodes it → loads the user → hands the user to the endpoint. Every protected route just depends on it.

```python
from typing import Annotated

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=401, detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)          # verifies signature + expiry
        username = payload.get("sub")
        if username is None:
            raise credentials_error
    except jwt.PyJWTError:
        raise credentials_error

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise credentials_error
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]
```

Now protecting any route is one annotation:

```python
@app.get("/users/me", response_model=UserRead)
def read_me(current_user: CurrentUser):
    return current_user          # only reachable with a valid token
```

If the token is missing, malformed, expired, or the user doesn't exist → automatic `401`. The endpoint body only runs for authenticated users.

### 6.1 Layering dependencies — the active-user check

Dependencies compose (Lesson 14). Build `get_current_active_user` on top of `get_current_user`:

```python
def get_current_active_user(current_user: CurrentUser) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
```

---

## 7. Authorization — Role-Based Access Control (RBAC)

Authentication tells you *who*. **RBAC** decides *what they may do* based on a **role** (`user`, `admin`, ...). The clean pattern is a **dependency factory** that returns a dependency requiring a role:

```python
def require_role(*allowed_roles: str):
    def checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker

# Usage: only admins may reach this route
@app.delete("/admin/users/{user_id}")
def delete_user(user_id: int, admin: Annotated[User, Depends(require_role("admin"))]):
    ...
```

- `require_role("admin")` returns a dependency that runs *after* `get_current_user` (it depends on it), then checks the role.
- Wrong role → **`403`** (authenticated but not permitted), distinct from the `401` for "not authenticated."

> 🔑 AuthN (`get_current_user`) and AuthZ (`require_role`) are **layered dependencies**: the role check builds on the identity check. This composition is exactly why FastAPI's dependency system shines here.

You can attach a role requirement to a **whole router** too, via `APIRouter(dependencies=[Depends(require_role("admin"))])` (Lesson 16), so every route in an admin router is protected in one place.

---

## 8. Refresh Tokens

Access tokens should be **short-lived** (e.g. 15 minutes) — if one leaks, it expires soon. But forcing login every 15 minutes is bad UX. The solution: issue **two** tokens at login.

| Token | Lifetime | Purpose |
|---|---|---|
| **Access token** | Short (minutes) | Sent on every request to access resources |
| **Refresh token** | Long (days) | Used only to obtain a new access token |

Flow: when the access token expires, the client POSTs its refresh token to `/refresh` and gets a fresh access token — no password re-entry.

```python
@app.post("/refresh", response_model=Token)
def refresh(refresh_token: str = Body(..., embed=True), db: Session = Depends(get_db)):
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":       # reject access tokens here
            raise HTTPException(401, "Invalid token type")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid refresh token")
    ...  # issue a new access token
```

Mark the token type in the payload (`"type": "access"` vs `"refresh"`) so a refresh token can't be used as an access token or vice-versa.

> 💡 True refresh-token *revocation* (logout, rotation) needs server-side storage of valid/blocked tokens — a common production add-on. The JWT itself can't be "un-issued" before it expires.

---

## 9. API Keys — The Other Auth Method

Not every client is a human logging in. **Machine-to-machine** callers (a partner service, a cron job, a webhook) often use an **API key**: a long random secret sent in a header.

```python
from fastapi import Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

def require_api_key(key: str = Security(api_key_header)) -> str:
    if key not in VALID_API_KEYS:          # in real apps: hashed keys in the DB
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key
```

| | JWT / OAuth2 Password Flow | API Key |
|---|---|---|
| Best for | Human users logging in | Services / scripts / integrations |
| Carries | Identity + claims + expiry | Just "this caller is authorized" |
| Lifetime | Short, refreshable | Long-lived, manually rotated |
| Sent as | `Authorization: Bearer <jwt>` | Custom header, e.g. `X-API-Key` |

> 🔑 Use **JWT/OAuth2** for user login flows; use **API keys** for trusted service-to-service access. Store API keys **hashed** (like passwords), never in plaintext, and support rotation.

---

## 10. Security Best Practices

| Practice | Why |
|---|---|
| Store only **hashed** passwords (bcrypt) | A DB leak must not expose passwords |
| Keep `SECRET_KEY` in **config/env**, 32+ random bytes | Anyone with it can forge tokens |
| **Short** access-token expiry + refresh tokens | Limits damage from a leaked token |
| Never put secrets in a JWT payload | It's readable by anyone |
| Serve over **HTTPS only** | Tokens/passwords must not travel in cleartext |
| Return generic login errors | "Incorrect username or password" (don't reveal which) |
| Correct codes: `401` vs `403` | AuthN vs AuthZ are different failures |
| Validate password length/complexity | And respect bcrypt's 72-byte limit |

> ⚠️ The demo hardcodes a `SECRET_KEY` for simplicity. In a real app it comes from environment/config (Lesson 45) and must be a strong random value — a weak or committed secret means anyone can mint admin tokens.

---

## 11. Real-World Use Case — Replacing the Fake `X-User-Id`

Every Phase 1–3 assignment used a header like `X-User-Id` as "identity," with a giant caveat that it was **not** real auth. Now you can do it properly:

- Users **register** (`POST /register`) → password hashed with bcrypt, stored.
- Users **log in** (`POST /token`) → get a JWT access token (+ refresh token).
- Protected endpoints depend on **`get_current_user`** → the acting user is proven by the token, not claimed in a header.
- Admin-only actions use **`require_role("admin")`** → real authorization.
- A partner integration uses an **API key** → machine access without a login.

The finance API from the Phase 3 assignment becomes genuinely multi-tenant-safe: a user's token determines which rows they can touch, and it cannot be forged without the secret key.

---

## 12. Mini Task

`main.py` is a runnable, database-backed auth API.

1. Install: `pip install fastapi uvicorn sqlalchemy "pyjwt" bcrypt python-multipart`
   (`python-multipart` is required for OAuth2 form login.)
2. Run: `uvicorn main:app --reload` → open `/docs`.
3. Walk the full flow in Swagger:
   - `POST /register` → create a user.
   - Click **Authorize** (top-right), log in with your username/password — Swagger calls `/token` and stores the bearer token.
   - `GET /users/me` → now returns your user (try it *without* authorizing first → `401`).
   - `POST /register` an admin (seeded role), then hit `DELETE /admin/users/{id}` as a normal user → `403`, and as an admin → success.
   - `GET /service/data` with the `X-API-Key` header → API-key auth.
4. **Prove the security:**
   - Copy your JWT and paste it at jwt.io (or decode the middle part) — see your `sub`/`role` in plaintext. This is why secrets never go in a JWT.
   - Tamper one character of the token and call `/users/me` → `401` (signature check).
5. **Bonus:**
   - Add token expiry of 1 minute and watch a call fail with `401` after it lapses; then use `/refresh` to get a new one.
   - Add a `scopes`-style permission beyond role (e.g. `can_publish`) and a dependency that enforces it.

---

## 13. Common Mistakes

| Mistake | Fix |
|---|---|
| Storing plaintext (or fast-hashed) passwords | Use bcrypt (salted, slow). |
| Using `passlib` with modern bcrypt | Use the `bcrypt` library directly. |
| Putting secrets in the JWT payload | It's readable; only put non-sensitive claims. |
| Hardcoding / committing `SECRET_KEY` | Load from env/config; use 32+ random bytes. |
| Confusing `401` and `403` | `401` = not authenticated; `403` = not permitted. |
| Long-lived access tokens | Short access token + refresh token. |
| Forgetting `python-multipart` | OAuth2 form login needs it installed. |
| Sending login as JSON | The Password Flow uses form fields `username`/`password`. |

---

## 14. Key Takeaways

- **AuthN** ("who are you?") comes first; **AuthZ** ("what may you do?") second. `401` vs `403`.
- **Never store plaintext passwords.** Hash with **bcrypt** (salted + slow); verify by hashing the input. Use bcrypt directly, not passlib.
- **JWTs are signed, not encrypted** — readable by anyone, tamper-proof via the secret. Never store secrets in them.
- The **OAuth2 Password Flow** (`OAuth2PasswordBearer` + `OAuth2PasswordRequestForm`) issues a token at `/token`.
- **`get_current_user`** is the core dependency: token → decode → load user → inject. Protect any route by depending on it.
- **RBAC** via a `require_role(...)` dependency factory layered on `get_current_user`; wrong role → `403`.
- **Refresh tokens** (long-lived) mint new **access tokens** (short-lived) without re-login.
- **API keys** authenticate services; store them hashed and rotate them.

---

## ➡️ Next Lesson

**Lesson 30 — Background Tasks**
- `BackgroundTasks` (built-in) for work after the response
- When to reach for Celery / RQ / ARQ instead
- Fire-and-forget vs. durable job queues
