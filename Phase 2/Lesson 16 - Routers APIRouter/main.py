"""
Lesson 16 — Routers (APIRouter)
---------------------------------
This file is the entry point. Its ONLY job is to:
  1. Create the FastAPI app
  2. Add middleware
  3. Include routers with their prefixes, tags, and dependencies

All actual route logic lives in routers/users.py, routers/items.py,
and routers/admin.py.

Run:
    uvicorn main:app --reload

Test:
    http://127.0.0.1:8000/docs
    Notice the routes are grouped into "Users", "Items", and "Admin" sections.
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dependencies import require_admin
from routers import admin, items, users

app = FastAPI(
    title="Lesson 16 - Routers",
    description="A multi-file FastAPI app demonstrating APIRouter.",
)

# ── Middleware ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────

# Public — no auth required on the router itself
# (individual endpoints may still require auth via their own Depends)
app.include_router(users.router)
app.include_router(items.router)

# Protected — require_admin applied to EVERY route in admin.router
app.include_router(
    admin.router,
    dependencies=[Depends(require_admin)],
)


# ── App-level health check ───────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
