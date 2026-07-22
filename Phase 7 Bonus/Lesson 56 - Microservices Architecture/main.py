"""
Lesson 56 - Microservices Architecture
--------------------------------------
Two independent FastAPI services demonstrating inter-service communication:

    - Users service:  owns users + their data (GET /users/{id})
    - Orders service: owns orders; to create one it makes a real HTTP call to
      the Users service to validate the customer exists.

In production these run as SEPARATE deployments, each with its own database,
reachable by a URL from config (service discovery). Here they run in one
process for a self-contained, testable demo - the Orders service calls the
Users service in-process via httpx's ASGI transport (simulating the network).

    pip install fastapi uvicorn httpx

How to run (from inside this folder):

    uvicorn main:app --reload
"""

import os

import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

# ===========================================================================
# USERS SERVICE - owns users. Independent app + (in real life) its own DB.
# ===========================================================================
users_app = FastAPI(title="Users Service")

_USERS = {1: {"id": 1, "name": "Ada"}, 2: {"id": 2, "name": "Alan"}}


@users_app.get("/users/{user_id}")
def get_user(user_id: int):
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


# ===========================================================================
# ORDERS SERVICE - owns orders. Talks to the Users service over HTTP.
# ===========================================================================
orders_app = FastAPI(title="Orders Service")

_ORDERS: list[dict] = []

# Where is the Users service? From config (env var) - NOT hardcoded. In Docker/
# K8s this is a service name like http://users-service:8000.
USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://users-service")


def get_users_client() -> httpx.AsyncClient:
    """Returns an HTTP client pointed at the Users service.

    For this in-process demo it routes to users_app via ASGI transport (no real
    network). Override this dependency in tests, or swap the transport for a
    real base_url in production - the calling code doesn't change.
    """
    transport = httpx.ASGITransport(app=users_app)
    return httpx.AsyncClient(
        transport=transport, base_url=USERS_SERVICE_URL, timeout=2.0  # never hang forever
    )


class OrderCreate(BaseModel):
    user_id: int
    item: str


@orders_app.post("/orders", status_code=201)
async def create_order(
    payload: OrderCreate,
    users: httpx.AsyncClient = Depends(get_users_client),
):
    # INTER-SERVICE CALL: validate the user via the Users service.
    async with users:
        try:
            resp = await users.get(f"/users/{payload.user_id}")
        except httpx.RequestError:
            # The Users service is unreachable/timed out -> fail fast, don't hang.
            raise HTTPException(503, "Users service unavailable")

    if resp.status_code == 404:
        raise HTTPException(404, f"User {payload.user_id} does not exist")
    if resp.status_code != 200:
        raise HTTPException(502, "Unexpected response from Users service")

    user = resp.json()
    order = {"id": len(_ORDERS) + 1, "user_id": user["id"],
             "user_name": user["name"], "item": payload.item}
    _ORDERS.append(order)
    return order


# ===========================================================================
# A tiny API GATEWAY (for the demo) that mounts both services under one app so
# uvicorn main:app serves them together. In production these are separate.
# ===========================================================================
app = FastAPI(title="Lesson 56 - Microservices (gateway view)")
app.mount("/users-service", users_app)
app.mount("/orders-service", orders_app)


@app.get("/")
def root():
    return {
        "services": {
            "users": "/users-service/users/{id}",
            "orders": "/orders-service/orders (POST)",
        }
    }
