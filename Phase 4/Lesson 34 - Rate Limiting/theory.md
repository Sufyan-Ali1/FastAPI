# Lesson 34 — Rate Limiting

> **Goal of this lesson:** Stop clients from overwhelming (or abusing) your API. Learn **why** and **where** to throttle, the common rate-limiting **algorithms**, how to add limits with **`slowapi`**, how to key limits **per-IP** and **per-user**, and how to return a proper **`429 Too Many Requests`**.
>
> `main.py` is a runnable app with real limits; the verification hammers an endpoint and shows the `429` kick in.

---

## 1. Why Rate Limit?

Without limits, a single client can send thousands of requests per second. That's a problem for several reasons:

| Reason | Example |
|---|---|
| **Abuse / DoS** | One client floods the API and degrades it for everyone. |
| **Brute force** | Attacker tries millions of passwords against `/login`. |
| **Cost control** | Each request hits a paid database / LLM / third-party API. |
| **Fairness** | One heavy user shouldn't starve the rest. |
| **Scraping** | Bots harvesting your whole dataset via pagination. |

Rate limiting caps how many requests a given client may make in a time window. Over the cap → the server rejects extra requests with **`429 Too Many Requests`** instead of doing the work.

> 🔑 Rate limiting is about **fairness and protection**, not correctness. It's one of the first hardening steps for any public or authenticated API — especially on expensive or security-sensitive endpoints like `/login`.

---

## 2. The Core Idea — Limits Over a Window

A rate limit is "**N requests per time window** per client":

```
"5 per minute"     -> a client may make 5 requests each minute
"100 per hour"     -> ...100 per hour
"1000 per day"     -> ...1000 per day
```

Two questions define any limit:

1. **Who is the "client"?** — the **key**. Usually the IP address, or the authenticated user id, or an API key.
2. **How do we count within the window?** — the **algorithm**.

---

## 3. Rate-Limiting Algorithms

You don't implement these by hand (the library does), but knowing them explains the behavior.

| Algorithm | How it counts | Trade-off |
|---|---|---|
| **Fixed window** | Count resets at fixed boundaries (e.g. each minute) | Simple, but allows bursts at the window edges |
| **Sliding window** | Counts over a rolling window ending now | Smoother, more accurate; a bit more work |
| **Token bucket** | Tokens refill at a steady rate; each request spends one | Allows controlled bursts up to bucket size |
| **Leaky bucket** | Requests drain at a fixed rate; overflow rejected | Smooths output to a constant rate |

### The fixed-window "burst" gotcha

With a fixed window of "5 per minute," a client could send 5 requests at `12:00:59` and 5 more at `12:01:00` — **10 requests in one second**, because the counter reset at the minute boundary. **Sliding window** and **token bucket** avoid this. `slowapi` uses fixed-window-style counting by default via the `limits` library, which is fine for most cases; be aware of the edge behavior.

> 🔑 For most APIs, a simple per-window limit is plenty. Reach for token bucket when you specifically want to allow short bursts but cap the sustained rate.

---

## 4. `slowapi` — Rate Limiting for FastAPI

**`slowapi`** is the standard rate-limiting library for FastAPI/Starlette (a port of Flask-Limiter, built on the `limits` package). Setup has four parts:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# 1. Create a Limiter with a "key function" that identifies the client.
limiter = Limiter(key_func=get_remote_address)   # key = client IP

app = FastAPI()

# 2. Register the limiter and the handler that turns limit-exceeded into 429.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Then decorate routes with limits:

```python
# 3. Apply a limit to a route. The endpoint MUST take `request: Request`.
@app.get("/ping")
@limiter.limit("5/minute")
def ping(request: Request):
    return {"pong": True}
```

| Piece | Role |
|---|---|
| `Limiter(key_func=...)` | The limiter; `key_func` returns the "who" (IP by default) |
| `app.state.limiter` | slowapi looks here for the limiter |
| `RateLimitExceeded` handler | Converts an over-limit into a `429` response |
| `@limiter.limit("5/minute")` | The limit string on a route |

> ⚠️ **The decorated endpoint must have a `request: Request` parameter** (and, if async, works the same). slowapi reads the request from it to compute the key. Forgetting `request` is the #1 slowapi error.

Limit string format: `"<count>/<period>"` — e.g. `"5/minute"`, `"100/hour"`, `"10/second"`, or combined `"5/minute;100/hour"`.

---

## 5. The `429 Too Many Requests` Response

When a client exceeds the limit, slowapi's handler returns **`429 Too Many Requests`**. A good `429` includes a **`Retry-After`** header telling the client how long to wait:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 42
{"error": "Rate limit exceeded: 5 per 1 minute"}
```

`429` is the correct, standard status code for throttling (distinct from `403` Forbidden or `503` Service Unavailable). Well-behaved clients read `Retry-After` and back off.

> 🔑 Return **`429`** for rate limiting, and include **`Retry-After`** so clients know when to try again. slowapi's default handler does this for you.

---

## 6. Per-IP vs Per-User

The **key function** decides *who* a limit applies to. This is the heart of "per-IP vs per-user."

### 6.1 Per-IP (the default)

```python
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)   # each IP gets its own budget
```

Simple and needs no login. But: users behind the same NAT/proxy share an IP (a whole office counts as one client), and a determined attacker can rotate IPs.

### 6.2 Per-User (authenticated)

Once you have auth (Lesson 29), key by **user id** so each account gets its own budget regardless of IP:

```python
def user_key(request: Request) -> str:
    user = getattr(request.state, "user", None)     # set by your auth layer
    if user is not None:
        return f"user:{user.id}"
    return get_remote_address(request)              # fall back to IP for anonymous

limiter = Limiter(key_func=user_key)
```

### 6.3 Per-API-key or per-tier

For machine clients, key by the API key; you can even vary the *limit* by plan (free vs pro). A common pattern: stricter limits for anonymous/free, looser for authenticated/paid.

| Key by | Good for | Caveat |
|---|---|---|
| **IP** | Public endpoints, no login needed | Shared IPs; IP rotation |
| **User id** | Authenticated APIs, fair per-account limits | Requires auth first |
| **API key** | Service clients, tiered plans | Key management |

> 🔑 Choose the key by *what "one client" means for you*. Public login page → per-IP (slow brute force). Authenticated SaaS → per-user (fair budgets). The `key_func` is where you encode that decision.

---

## 7. Where to Apply Limits

- **Per-route** — decorate specific endpoints (strict on `/login`, `/signup`, expensive search; loose on cheap reads).
- **Global default** — `Limiter(default_limits=["200/minute"])` applies a baseline to everything, which per-route limits can override.
- **Different limits per route** — a login endpoint might be `"5/minute"` while a public catalog is `"100/minute"`.

```python
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

@app.post("/login")
@limiter.limit("5/minute")          # stricter than the global default
def login(request: Request): ...
```

> 💡 Put the **tightest** limits on **security-sensitive** (login, password reset, OTP) and **expensive** (search, report generation, LLM) endpoints.

---

## 8. Storage — In-Memory vs Redis

Rate limits need to **count** requests somewhere. slowapi's default storage is **in-memory** — fine for a single process, but with a catch:

- **In-memory** counters live in one process. If you run **multiple workers/servers** (Lesson 50), each has its own counter — so "5/minute" effectively becomes "5/minute × number of workers." The limit leaks.
- **Redis** (or Memcached) gives **shared** counters across all workers, so the limit is enforced globally.

```python
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",   # shared across all workers
)
```

> 🔑 In-memory limiting is per-process. For any multi-worker or multi-server deployment, use a **shared store like Redis** so the limit is accurate. (Same single-process caveat you saw for WebSockets in Lesson 31.)

---

## 9. Rate Limiting Isn't Everything

Rate limiting is one layer. It complements — doesn't replace — other protections:

- It doesn't authenticate (Lesson 29) or authorize.
- A determined distributed attack (many IPs) needs upstream defenses (WAF, CDN, cloud DDoS protection) too.
- Very high-scale throttling is often done at the **gateway / load balancer / CDN** layer (nginx, Cloudflare, API gateways) *in front of* your app, with app-level limits as a second line.

> 🔑 App-level rate limiting (slowapi) protects against ordinary abuse and accidental floods. Serious DDoS is handled upstream. Use both where it matters.

---

## 10. Real-World Use Case — Protecting Login

Your `/token` login endpoint (Lesson 29) is a brute-force target: an attacker scripts thousands of username/password guesses. Add `@limiter.limit("5/minute")` keyed per-IP and the attacker gets **5 tries a minute** instead of thousands a second — brute forcing becomes impractical, and legitimate users are unaffected. Meanwhile your public catalog endpoint can allow `"100/minute"`, and authenticated API calls can be keyed per-user so one noisy account can't hurt others. Same tool, three policies chosen per endpoint.

---

## 11. Mini Task

`main.py` applies a `5/minute` limit to `/limited` and a stricter `3/minute` to `/login`.

1. Install: `pip install slowapi`
2. Run: `uvicorn main:app --reload`
3. Hit the limited endpoint repeatedly and watch it flip to `429`:
   ```bash
   for i in $(seq 1 7); do curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/limited; done
   ```
   The first 5 return `200`, then `429`.
4. Inspect the `429` response and its `Retry-After` header:
   ```bash
   curl -i http://127.0.0.1:8000/limited   # after exceeding the limit
   ```
5. **Experiment:**
   - Lower `/login` to `"2/minute"` and confirm it trips faster.
   - Add a `default_limits` baseline to the `Limiter` and see it apply to an un-decorated route.
   - Switch the `key_func` to a custom one that keys off an `X-User-Id` header, and confirm two different users get independent budgets.
6. **Bonus:** Point `storage_uri` at Redis (if available) and reason about why that matters once you run more than one worker.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Forgetting `request: Request` on a limited endpoint | slowapi needs it to compute the key. |
| `headers_enabled=True` but no `response: Response` param | To inject `X-RateLimit-*`/`Retry-After` headers, a limited endpoint must also accept `response: Response`. |
| Not registering the `RateLimitExceeded` handler | Over-limit won't become a proper `429`. |
| Using in-memory storage with multiple workers | Limit leaks; use Redis for shared counting. |
| Returning `403`/`503` for throttling | Use `429 Too Many Requests` with `Retry-After`. |
| Only limiting per-IP behind a proxy | The proxy's IP may be seen; read the real client IP correctly. |
| Rate limiting instead of auth | They're different layers; do both. |
| Same limit everywhere | Tighten on login/expensive routes, loosen on cheap reads. |

---

## 13. Key Takeaways

- **Rate limiting** caps requests per client per time window to protect against abuse, brute force, cost blowups, and unfairness.
- A limit is defined by a **key** (who) and an **algorithm** (fixed/sliding window, token/leaky bucket).
- **`slowapi`**: create a `Limiter(key_func=...)`, register `app.state.limiter` + the `RateLimitExceeded` handler, decorate routes with `@limiter.limit("5/minute")` (endpoint needs `request: Request`).
- Over the limit → **`429 Too Many Requests`** with a **`Retry-After`** header.
- **Per-IP** (`get_remote_address`) needs no login but shares budgets across NAT; **per-user** (custom `key_func`) gives fair per-account limits after auth.
- Apply the **tightest** limits to **login and expensive** endpoints; use `default_limits` for a baseline.
- In-memory counters are **per-process** — use **Redis** storage for accurate limits across multiple workers.
- App-level limiting complements, but doesn't replace, auth and upstream (gateway/CDN) DDoS protection.

---

## ➡️ Next Lesson

**Lesson 35 — Caching**
- In-memory caching and Redis caching
- `fastapi-cache2` for response caching
- Cache keys, TTLs, and invalidation (building on Lesson 27)
