"""
Admin router — protected routes under /admin.
The require_admin dependency is applied to the whole router
in main.py via include_router(dependencies=[...]).
Individual endpoints don't need to declare it again.
"""

from fastapi import APIRouter
from routers import users as users_router
from routers import items as items_router

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
def get_stats():
    """
    Returns basic stats about users and items.
    Protected at the router level — no auth code needed here.
    """
    return {
        "total_users": len(users_router._db),
        "total_items": len(items_router._db),
    }


@router.get("/users")
def admin_list_users():
    """Admin view of all users (no pagination limit)."""
    return {"users": list(users_router._db.values())}


@router.get("/items")
def admin_list_items():
    """Admin view of all items (no pagination limit)."""
    return {"items": list(items_router._db.values())}
