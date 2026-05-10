"""
Lesson 18 — Headers & Cookies
-------------------------------
Demonstrates:
  - Header() for reading request headers
  - Underscore → hyphen auto-conversion
  - Setting response headers via Response object
  - Cookie() for reading cookies
  - response.set_cookie() with security flags
  - response.delete_cookie() on logout
  - Secure session pattern (token_urlsafe, httponly, samesite)
  - Location header on 201 Created

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
"""

import secrets
from datetime import datetime, timedelta

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 18 - Headers & Cookies")


# ============================================================
# 1. Reading request headers
# ============================================================

@app.get("/headers")
def read_headers(
    user_agent: str | None       = Header(None),   # User-Agent
    accept_language: str | None  = Header(None),   # Accept-Language
    x_request_id: str | None     = Header(None),   # X-Request-ID (custom)
    authorization: str | None    = Header(None),   # Authorization
):
    """
    FastAPI converts underscores → hyphens automatically.
    x_request_id reads the X-Request-ID header.
    """
    return {
        "User-Agent":       user_agent,
        "Accept-Language":  accept_language,
        "X-Request-ID":     x_request_id,
        "Authorization":    authorization,
    }


# ============================================================
# 2. Setting response headers
# ============================================================

@app.get("/set-headers")
def set_headers(response: Response):
    """Adds custom and standard headers to the response."""
    response.headers["X-Custom-Header"]  = "hello-from-fastapi"
    response.headers["X-App-Version"]    = "1.0.0"
    response.headers["Cache-Control"]    = "max-age=60, public"
    return {"message": "Check the response headers in the Network tab"}


@app.get("/location-demo")
def location_demo(response: Response):
    """Demonstrates the Location header pattern used on 201 Created."""
    response.headers["Location"] = "/users/42"
    response.status_code = status.HTTP_201_CREATED
    return {"id": 42, "message": "Resource created at Location header"}


# ============================================================
# 3. Cookie-based session — login / profile / logout
# ============================================================

# Fake user store and session store
FAKE_USERS: dict[str, str] = {
    "sufyan": "secret",
    "admin":  "admin123",
}
sessions: dict[str, dict] = {}


@app.post("/login")
def login(
    response: Response,
    username: str,
    password: str,
):
    """
    Validates credentials, creates a cryptographically random session ID,
    and sets a cookie with all production security flags.
    """
    if FAKE_USERS.get(username) != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "user":    username,
        "expires": datetime.utcnow() + timedelta(hours=1),
    }

    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=3600,       # 1 hour
        httponly=True,      # JS cannot read this cookie
        secure=False,       # Set True in production (needs HTTPS)
        samesite="lax",     # Prevents CSRF in most cases
        path="/",
    )
    return {"message": f"Welcome, {username}!"}


def get_session(session_id: str | None = Cookie(None)) -> dict:
    """Dependency: validates session cookie and returns session data."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please log in",
        )
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired",
        )
    if session["expires"] < datetime.utcnow():
        del sessions[session_id]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please log in again",
        )
    return session


@app.get("/profile")
def get_profile(session: dict = Depends(get_session)):
    """Protected by cookie session. Requires prior POST /login."""
    return {
        "user":       session["user"],
        "expires_at": session["expires"].isoformat(),
    }


@app.post("/logout")
def logout(
    response: Response,
    session_id: str | None = Cookie(None),
):
    """Invalidates the session server-side and clears the cookie."""
    if session_id and session_id in sessions:
        del sessions[session_id]
    response.delete_cookie("session_id", path="/")
    return {"message": "Logged out successfully"}


# ============================================================
# 4. Preference cookie — non-sensitive, readable by JS
# ============================================================

@app.post("/theme")
def set_theme(
    theme: str,
    response: Response,
):
    """
    Stores a UI preference. No httponly — JS needs to read it.
    No sensitive data, so that's fine.
    """
    if theme not in ("light", "dark", "system"):
        raise HTTPException(status_code=400, detail="Theme must be light, dark, or system")

    response.set_cookie(
        key="theme",
        value=theme,
        max_age=60 * 60 * 24 * 365,   # 1 year
        httponly=False,                 # JS is allowed to read this one
        samesite="lax",
    )
    return {"theme": theme}


@app.get("/theme")
def get_theme(theme: str | None = Cookie(None)):
    """Reads the stored theme preference."""
    return {"theme": theme or "system"}


# ============================================================
# 5. API key via custom header
# ============================================================

VALID_API_KEYS = {"key-abc-123", "key-xyz-789"}


def require_api_key(x_api_key: str = Header(..., description="Your API key")):
    """Dependency: reads X-API-Key header and validates it."""
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-API-Key",
        )
    return x_api_key


@app.get("/protected-data")
def protected_data(api_key: str = Depends(require_api_key)):
    """Requires X-API-Key: key-abc-123 (or key-xyz-789)."""
    return {"secret": "This data is protected by API key", "key_used": api_key}
