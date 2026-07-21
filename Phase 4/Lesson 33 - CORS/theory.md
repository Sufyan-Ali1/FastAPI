# Lesson 33 — CORS (Cross-Origin Resource Sharing)

> **Goal of this lesson:** Understand the error every developer hits the moment they connect a frontend to their API — *"blocked by CORS policy"* — and fix it properly. Learn **why the Same-Origin Policy exists**, what an **origin** is, how **CORS** relaxes it in a controlled way, and how to configure FastAPI's **`CORSMiddleware`** for real frontend integration.
>
> `main.py` is a runnable app with CORS configured; the verification shows the exact response headers the browser looks for.

---

## 1. The Error Everyone Hits

You build a FastAPI backend on `http://localhost:8000`. You build a React frontend on `http://localhost:3000`. The frontend calls the API and the browser console explodes:

```
Access to fetch at 'http://localhost:8000/api/data' from origin
'http://localhost:3000' has been blocked by CORS policy: No
'Access-Control-Allow-Origin' header is present on the requested resource.
```

The request never even reached your endpoint logic in a usable way — the **browser** blocked it. This lesson explains exactly why, and how to allow it deliberately.

---

## 2. The Same-Origin Policy

Browsers enforce a security rule called the **Same-Origin Policy (SOP)**: by default, JavaScript running on one **origin** may **not** read responses from a **different** origin.

So a page loaded from `http://localhost:3000` cannot, by default, read the response of a `fetch()` to `http://localhost:8000`. The browser makes the request but **hides the response** from the JavaScript unless the server explicitly says it's allowed.

> 🔑 SOP is enforced by the **browser**, for **browser-based JavaScript**. Server-to-server calls, `curl`, Postman, and mobile apps are **not** subject to CORS — they'll happily call your API. CORS only governs what a **web page's JS** is allowed to read.

---

## 3. What Is an "Origin"?

An **origin** is the triple: **scheme + host + port**. Two URLs are the *same* origin only if all three match.

```
        https://api.example.com:443/users
        └─┬─┘   └──────┬──────┘ └┬┘
        scheme       host       port
```

| URL A | URL B | Same origin? | Why |
|---|---|---|---|
| `http://localhost:3000` | `http://localhost:8000` | ❌ No | Different **port** |
| `http://localhost:3000` | `https://localhost:3000` | ❌ No | Different **scheme** |
| `https://app.example.com` | `https://api.example.com` | ❌ No | Different **host** |
| `https://example.com/a` | `https://example.com/b` | ✅ Yes | Only the path differs |

> 🔑 A different **port** is a different origin. This is why `localhost:3000` (frontend) → `localhost:8000` (backend) needs CORS even though both are "localhost."

---

## 4. Why the Same-Origin Policy Exists

Without SOP, any malicious website you visit could run JavaScript that calls `https://yourbank.com/api/transfer` **using the cookies your browser already has** for your bank — and read the response. SOP stops one site from silently reading another site's authenticated data through your browser.

So SOP is a **security feature**. CORS isn't a way to defeat it — it's a **controlled, server-approved exception**: the server that owns the resource declares which other origins are allowed to read it.

---

## 5. What CORS Actually Is

**CORS (Cross-Origin Resource Sharing)** is a set of **HTTP response headers** by which a server tells the browser: *"these specific other origins are allowed to read my responses."*

The flow:

1. The browser sends the request, including an **`Origin:`** header (e.g. `Origin: http://localhost:3000`).
2. The server responds with **`Access-Control-Allow-Origin:`** naming allowed origin(s).
3. The browser checks: does the response's `Access-Control-Allow-Origin` match the page's origin?
   - **Yes** → the browser hands the response to the JavaScript.
   - **No** → the browser **blocks** it and logs the CORS error.

> 🔑 CORS is a **conversation between the server and the browser.** Your server adds headers *permitting* origins; the browser *enforces* them. The server isn't "blocking" anything — it's granting permission, and the browser does the blocking when permission is absent.

---

## 6. Simple Requests vs Preflight

Not all cross-origin requests behave the same. The browser splits them into two categories.

### 6.1 Simple requests

A request is "simple" if it uses `GET`, `POST`, or `HEAD`, with only basic headers and a standard content type (`text/plain`, `application/x-www-form-urlencoded`, `multipart/form-data`). The browser sends it directly and checks the `Access-Control-Allow-Origin` on the response.

### 6.2 Preflighted requests

Anything else — `PUT`/`DELETE`/`PATCH`, a JSON body (`application/json`), custom headers (like `Authorization`) — triggers a **preflight**: before the real request, the browser automatically sends an **`OPTIONS`** request asking permission.

```
Browser preflight (automatic):
   OPTIONS /api/data
   Origin: http://localhost:3000
   Access-Control-Request-Method: DELETE
   Access-Control-Request-Headers: authorization, content-type

Server responds:
   Access-Control-Allow-Origin: http://localhost:3000
   Access-Control-Allow-Methods: GET, POST, PUT, DELETE
   Access-Control-Allow-Headers: authorization, content-type
   Access-Control-Max-Age: 600

Only if the preflight is approved does the browser send the real DELETE.
```

> 🔑 Most real API calls (JSON bodies, `Authorization` headers, `PUT`/`DELETE`) are **preflighted**. The browser sends an `OPTIONS` request first, entirely on its own. Your CORS config must answer that preflight correctly, or the real request never happens.

---

## 7. The CORS Response Headers

| Header | Says |
|---|---|
| `Access-Control-Allow-Origin` | Which origin(s) may read the response (`*` or a specific origin) |
| `Access-Control-Allow-Methods` | Which HTTP methods are allowed (preflight) |
| `Access-Control-Allow-Headers` | Which request headers are allowed (preflight) |
| `Access-Control-Allow-Credentials` | Whether cookies/auth may be sent (`true`) |
| `Access-Control-Expose-Headers` | Which response headers the JS may read |
| `Access-Control-Max-Age` | How long the browser may cache the preflight result |

You rarely set these by hand — FastAPI's middleware does it for you.

---

## 8. `CORSMiddleware` in FastAPI

FastAPI ships CORS support via Starlette's `CORSMiddleware` (you met middleware in Lesson 15). Add it once:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.example.com"],
    allow_credentials=True,
    allow_methods=["*"],          # or ["GET", "POST", "PUT", "DELETE"]
    allow_headers=["*"],          # or ["Authorization", "Content-Type"]
    expose_headers=["X-Total-Count"],
    max_age=600,
)
```

| Parameter | Purpose |
|---|---|
| `allow_origins` | List of permitted origins. **List them explicitly** in production. |
| `allow_origin_regex` | Match origins by regex (e.g. all `*.example.com`) |
| `allow_credentials` | Allow cookies/`Authorization` on cross-origin requests |
| `allow_methods` | Permitted methods (`["*"]` = all) |
| `allow_headers` | Permitted request headers (`["*"]` = all) |
| `expose_headers` | Response headers the frontend JS is allowed to read |
| `max_age` | Seconds the browser caches the preflight (fewer `OPTIONS` calls) |

The middleware automatically handles **preflight `OPTIONS`** requests and adds the right headers to every response — you don't write an `OPTIONS` handler yourself.

---

## 9. The Credentials + Wildcard Rule

A critical gotcha enforced by the browser spec:

> **You cannot use `allow_origins=["*"]` together with `allow_credentials=True`.**

If credentials (cookies, `Authorization`) are allowed, the `Access-Control-Allow-Origin` **must** be a specific origin, not the `*` wildcard. Browsers reject the combination. So if your frontend sends cookies or auth headers cross-origin, you must **list explicit origins**:

```python
# ✅ works with credentials
allow_origins=["https://app.example.com"], allow_credentials=True

# ❌ browser rejects this combination
allow_origins=["*"], allow_credentials=True
```

> 🔑 If you need `allow_credentials=True`, you **must** enumerate exact origins (or use `allow_origin_regex`). The `*` wildcard only works for non-credentialed requests.

---

## 10. What CORS Is *Not*

This is the most misunderstood part of CORS:

- CORS is **not server-side security.** It does not protect your API from `curl`, scripts, mobile apps, or other servers — those ignore CORS entirely. It only constrains **browser JavaScript**.
- CORS is **not authentication or authorization.** Allowing an origin says "this website's JS may read responses," not "this user is logged in." You still need Lesson 29's auth.
- Loosening CORS (`allow_origins=["*"]`) does **not** make your API less secure against non-browser clients — but it does let *any* website's JS call it with the user's browser, which matters if you rely on cookies.

> 🔑 CORS protects **your users' browsers** from other sites reading your API with their credentials. It is **not** a firewall for your API. Real security is still auth (Lesson 29) + validation + HTTPS.

---

## 11. Dev vs Prod Configuration

| | Development | Production |
|---|---|---|
| `allow_origins` | Your local frontend, e.g. `["http://localhost:3000"]` | Exact deployed origins, e.g. `["https://app.example.com"]` |
| Wildcard `*` | Tempting for convenience | **Avoid** — be explicit, especially with credentials |
| `allow_methods` / `allow_headers` | `["*"]` is fine locally | Prefer explicit lists |

> ⚠️ Don't ship `allow_origins=["*"]` for an API that uses cookie auth. Keep origins in configuration (Lesson 45) so dev and prod differ without code changes.

---

## 12. Real-World Use Case — React Frontend + FastAPI Backend

The classic split deployment:

- Frontend (React/Vue/etc.) served from `https://app.mycompany.com`.
- API (FastAPI) served from `https://api.mycompany.com`.

Different hosts → different origins → the browser enforces CORS. Without `CORSMiddleware`, every `fetch` from the app to the API is blocked. With it configured to `allow_origins=["https://app.mycompany.com"]` and `allow_credentials=True` (so the auth cookie/token flows), the frontend works — and no *other* website's JavaScript can read your API using a logged-in user's browser.

This is why CORS config is one of the first things you add when a real frontend enters the picture — and one of the first things to get wrong.

---

## 13. Mini Task

`main.py` has `CORSMiddleware` configured for a couple of allowed origins.

1. Run: `uvicorn main:app --reload`
2. Inspect the CORS headers with curl (simulating what a browser sends):
   ```bash
   # allowed origin -> response includes Access-Control-Allow-Origin
   curl -i -H "Origin: http://localhost:3000" http://127.0.0.1:8000/api/data

   # preflight for a DELETE with auth header
   curl -i -X OPTIONS http://127.0.0.1:8000/api/data \
     -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: DELETE" \
     -H "Access-Control-Request-Headers: authorization"
   ```
3. Try a **disallowed** origin (`Origin: http://evil.com`) and confirm the `Access-Control-Allow-Origin` header is absent — the browser would block that.
4. **Experiment:**
   - Change `allow_credentials=True` while keeping `allow_origins=["*"]` and observe the middleware won't echo `*` with credentials (the wildcard rule).
   - Add a second allowed origin and confirm both get approved.
5. **Bonus:** Serve a tiny HTML page from a *different* port (e.g. `python -m http.server 3000`) that `fetch`es your API, and watch the browser console block or allow it based on your config.

---

## 14. Common Mistakes

| Mistake | Fix |
|---|---|
| "CORS error" → assuming the server is down | The request reached the browser's CORS check; configure `CORSMiddleware`. |
| `allow_origins=["*"]` **and** `allow_credentials=True` | List explicit origins when using credentials. |
| Forgetting the port is part of the origin | `localhost:3000` ≠ `localhost:8000`; both need allowing. |
| Writing your own `OPTIONS` handler | `CORSMiddleware` handles preflight automatically. |
| Treating CORS as API security | It only affects browser JS; use real auth. |
| Shipping wildcard origins to production | Enumerate exact origins in config. |
| Frontend can't read a custom response header | Add it to `expose_headers`. |

---

## 15. Key Takeaways

- The **Same-Origin Policy** stops browser JS from reading responses from a **different origin** by default — a security feature.
- An **origin** = **scheme + host + port**; a different port (or scheme, or host) is a different origin.
- **CORS** is the server's way to *permit* specific origins, via `Access-Control-Allow-*` **response headers**; the **browser** enforces them.
- Most real requests (JSON, `Authorization`, `PUT`/`DELETE`) trigger a **preflight `OPTIONS`** the browser sends automatically.
- Configure it once with **`CORSMiddleware`**: `allow_origins`, `allow_methods`, `allow_headers`, `allow_credentials`, `expose_headers`, `max_age`.
- **You can't combine `allow_origins=["*"]` with `allow_credentials=True`** — enumerate exact origins.
- CORS is **not** server-side security and **not** auth — it only governs browser JavaScript; non-browser clients ignore it.

---

## ➡️ Next Lesson

**Lesson 34 — Rate Limiting**
- Why and where to throttle requests
- `slowapi` for per-IP / per-user limits
- Returning `429 Too Many Requests`
