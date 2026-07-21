"""
Lesson 47 - Security Best Practices
-----------------------------------
Demonstrates two concrete defenses:

    1. A secure-headers middleware adding the core browser security headers to
       every response.
    2. A REAL SQL injection: the /users/unsafe endpoint builds SQL with string
       formatting and gets exploited by  ' OR '1'='1  ; the /users/safe
       endpoint uses a parameterized query and defeats the same payload.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Try:
    curl -i http://127.0.0.1:8000/
    curl "http://127.0.0.1:8000/users/unsafe?username=' OR '1'='1"   # exploited
    curl "http://127.0.0.1:8000/users/safe?username=' OR '1'='1"     # safe
"""

import sqlite3

from fastapi import FastAPI, Request

app = FastAPI(title="Lesson 47 - Security")


# ---------------------------------------------------------------------------
# An in-memory SQLite DB with a couple of users, for the injection demo.
# (Kept in memory here purely to make the attack demonstrable.)
# ---------------------------------------------------------------------------
def _build_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, secret TEXT)")
    conn.executemany(
        "INSERT INTO users (username, secret) VALUES (?, ?)",
        [("alice", "alice-private"), ("bob", "bob-private")],
    )
    conn.commit()
    return conn


db = _build_db()


# ---------------------------------------------------------------------------
# SECURE HEADERS middleware - adds core security headers to EVERY response.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"          # no MIME sniffing
    response.headers["X-Frame-Options"] = "DENY"                    # no framing
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=()"
    # HSTS should only be sent over HTTPS in production:
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.get("/")
def root():
    return {"message": "Inspect the response headers, and try the injection demo."}


# ---------------------------------------------------------------------------
# UNSAFE: builds SQL by string formatting -> VULNERABLE to SQL injection.
# DO NOT DO THIS. It exists only to show the attack working.
# ---------------------------------------------------------------------------
@app.get("/users/unsafe")
def lookup_unsafe(username: str):
    # ❌ user input concatenated straight into the SQL string
    query = f"SELECT username FROM users WHERE username = '{username}'"
    rows = db.execute(query).fetchall()
    return {"query": query, "matched": [r["username"] for r in rows]}


# ---------------------------------------------------------------------------
# SAFE: parameterized query -> the value can NEVER become SQL.
# ---------------------------------------------------------------------------
@app.get("/users/safe")
def lookup_safe(username: str):
    # ✅ the "?" placeholder binds the value as DATA, not SQL
    rows = db.execute(
        "SELECT username FROM users WHERE username = ?", (username,)
    ).fetchall()
    return {"matched": [r["username"] for r in rows]}
