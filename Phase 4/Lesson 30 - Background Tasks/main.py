"""
Lesson 30 - Background Tasks
----------------------------
A runnable demo of FastAPI's built-in BackgroundTasks. Each task appends an
entry (with a timestamp) to an in-memory activity log, so you can SEE that:

    - the endpoint responds immediately
    - the tasks run AFTER the response is sent
    - multiple tasks run in the order they were added
    - tasks can also be added from a dependency

Then GET /logs to view what the background tasks recorded.

No extra installs - BackgroundTasks is built into FastAPI.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Then open http://127.0.0.1:8000/docs
"""

import time
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Lesson 30 - Background Tasks")

# A simple in-memory log the background tasks write to (a stand-in for a real
# email service, audit table, notification system, etc.).
ACTIVITY_LOG: list[dict] = []


def log(action: str, detail: str) -> None:
    ACTIVITY_LOG.append(
        {"at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
         "action": action, "detail": detail}
    )


# ---------------------------------------------------------------------------
# Task functions - these are what run AFTER the response is sent.
# They are plain `def`, so FastAPI runs them in a threadpool (blocking is fine).
# ---------------------------------------------------------------------------
def send_welcome_email(email: str) -> None:
    time.sleep(0.2)  # simulate a slow SMTP call
    log("email.sent", f"welcome email delivered to {email}")


def write_audit(action: str, detail: str) -> None:
    log("audit.written", f"{action}: {detail}")


def send_receipt(email: str, order_id: int) -> None:
    time.sleep(0.1)
    log("email.sent", f"receipt for order {order_id} sent to {email}")


def notify_warehouse(order_id: int) -> None:
    log("warehouse.notified", f"order {order_id} queued for fulfilment")


# ===========================================================================
# SCHEMAS
# ===========================================================================
class SignupIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")


class OrderIn(BaseModel):
    customer_email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    item: str = Field(..., min_length=1)


# ===========================================================================
# ENDPOINTS
# ===========================================================================
@app.post("/signup", status_code=201)
def signup(payload: SignupIn, background_tasks: BackgroundTasks):
    # The "real" work: create the account (instant here).
    user_id = len(ACTIVITY_LOG) + 1

    # Schedule slow side-effects to run AFTER this response is sent.
    background_tasks.add_task(send_welcome_email, payload.email)
    background_tasks.add_task(write_audit, "user.created", f"username={payload.username}")

    # Returned immediately; the two tasks above run afterward.
    return {"message": "Signed up", "user_id": user_id}


@app.post("/orders", status_code=201)
def create_order(payload: OrderIn, background_tasks: BackgroundTasks):
    order_id = 1000 + len(ACTIVITY_LOG)

    # Three tasks - they run in the order added, after the response.
    background_tasks.add_task(write_audit, "order.created", f"order={order_id}")
    background_tasks.add_task(send_receipt, payload.customer_email, order_id)
    background_tasks.add_task(notify_warehouse, order_id)

    return {"message": "Order placed", "order_id": order_id}


# ---------------------------------------------------------------------------
# Background task added from a DEPENDENCY (cross-cutting request logging).
# Any endpoint that depends on this gets an after-response log entry.
# ---------------------------------------------------------------------------
def log_request(background_tasks: BackgroundTasks):
    background_tasks.add_task(write_audit, "request.logged", "protected endpoint accessed")


@app.get("/reports", dependencies=[Depends(log_request)])
def get_reports():
    # The dependency queued a background task; it runs after this response.
    return {"reports": ["daily", "weekly"], "note": "a request-log task was queued"}


@app.get("/logs")
def get_logs():
    """Inspect what the background tasks have recorded so far."""
    return {"count": len(ACTIVITY_LOG), "entries": ACTIVITY_LOG}


@app.delete("/logs", status_code=204)
def clear_logs():
    ACTIVITY_LOG.clear()
