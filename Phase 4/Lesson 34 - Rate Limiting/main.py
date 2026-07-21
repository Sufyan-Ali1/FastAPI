"""
Lesson 34 - Rate Limiting
-------------------------
A runnable app using slowapi to throttle requests and return 429 when a client
exceeds its budget.

    - /limited  is capped at 5 requests / minute (per IP)
    - /login    is capped at 3 requests / minute (stricter - brute-force target)
    - /per-user is capped at 4 / minute keyed by X-User-Id header (per-user)
    - /open     has no limit

Install once:

    pip install fastapi uvicorn slowapi

How to run (from inside this folder):

    uvicorn main:app --reload

Try it (the 6th call to /limited within a minute returns 429):

    for i in $(seq 1 7); do
      curl -s -o /dev/null -w "%{http_code}\\n" http://127.0.0.1:8000/limited
    done
"""

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


# ---------------------------------------------------------------------------
# A custom key function: throttle per authenticated user (X-User-Id header),
# falling back to the client IP for anonymous callers.
# ---------------------------------------------------------------------------
def user_or_ip_key(request: Request) -> str:
    user_id = request.headers.get("X-User-Id")
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


# 1. The limiter. Default key is the client IP; a baseline default_limit
#    applies to routes that have no explicit @limiter.limit decorator.
#    headers_enabled=True adds X-RateLimit-* and Retry-After headers so clients
#    can see their remaining budget and when to retry.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    headers_enabled=True,
)

app = FastAPI(title="Lesson 34 - Rate Limiting")

# 2. Register the limiter + the handler that turns over-limit into a 429.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/")
def root():
    return {"message": "Rate limiting demo. Hammer /limited to see a 429."}


# 3. Per-route limit. NOTE: a limited endpoint MUST accept `request: Request`.
#    With headers_enabled=True it also needs `response: Response` so slowapi can
#    inject the X-RateLimit-* headers into successful responses.
@app.get("/limited")
@limiter.limit("5/minute")
def limited(request: Request, response: Response):
    return {"ok": True, "note": "5 per minute per IP"}


# A stricter limit on a brute-force-sensitive endpoint.
@app.post("/login")
@limiter.limit("3/minute")
def login(request: Request, response: Response):
    return {"ok": True, "note": "3 per minute per IP - protects against brute force"}


# Per-USER limit: two different X-User-Id values get independent budgets.
@app.get("/per-user")
@limiter.limit("4/minute", key_func=user_or_ip_key)
def per_user(request: Request, response: Response):
    return {"ok": True, "note": "4 per minute keyed by X-User-Id"}


# No explicit decorator -> only the Limiter's default_limits (100/minute) apply.
@app.get("/open")
def open_endpoint(request: Request):
    return {"ok": True, "note": "only the default baseline limit applies"}
