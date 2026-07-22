"""
Lesson 57 - Event-Driven Systems
--------------------------------
A runnable, in-process publish/subscribe bus - the exact pattern RabbitMQ/Kafka
provide at scale, but with no broker to install.

    - POST /orders  PUBLISHES an "order.created" event and returns IMMEDIATELY.
    - Multiple independent CONSUMERS (notifications, inventory) each react to the
      same event - one publish, many reactions (pub/sub fan-out).
    - The producer never waits for or knows about the consumers (decoupling).

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Then POST /orders and GET /processed to see every consumer's reaction.
"""

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


# ===========================================================================
# A minimal async pub/sub EventBus (stands in for a message broker).
# ===========================================================================
class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list] = defaultdict(list)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: str, handler) -> None:
        # Register a consumer for an event type. Many handlers per type = fan-out.
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, data: dict) -> None:
        # Fire-and-forget: enqueue the event and return. The producer does NOT
        # wait for consumers.
        await self._queue.put({"type": event_type, "data": data})

    async def _dispatch_loop(self) -> None:
        # A background worker delivering events to all subscribers.
        while True:
            event = await self._queue.get()
            for handler in self._subscribers.get(event["type"], []):
                try:
                    await handler(event["data"])
                except Exception:
                    # A real broker would retry / dead-letter this. Here we just
                    # isolate one failing consumer from the others.
                    pass
            self._queue.task_done()

    def start(self) -> None:
        self._task = asyncio.create_task(self._dispatch_loop())

    async def wait_idle(self) -> None:
        # Demo helper: wait until all published events have been processed.
        await self._queue.join()


bus = EventBus()

# A shared log so we can SEE what each consumer did.
processed: list[dict] = []


# ===========================================================================
# CONSUMERS - independent reactions to "order.created". Each is decoupled: the
# order endpoint knows nothing about them.
# ===========================================================================
async def send_confirmation(data: dict) -> None:
    processed.append({"consumer": "notifications",
                      "action": f"emailed confirmation for order {data['order_id']}"})


async def reserve_inventory(data: dict) -> None:
    processed.append({"consumer": "inventory",
                      "action": f"reserved stock for order {data['order_id']}"})


# ===========================================================================
# APP
# ===========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Wire up subscribers and start the dispatcher.
    bus.subscribe("order.created", send_confirmation)
    bus.subscribe("order.created", reserve_inventory)
    bus.start()
    yield


app = FastAPI(title="Lesson 57 - Event-Driven", lifespan=lifespan)


class OrderCreate(BaseModel):
    customer: str
    item: str


_orders: list[dict] = []


@app.post("/orders", status_code=201)
async def create_order(payload: OrderCreate):
    # 1. Do the core work.
    order = {"id": len(_orders) + 1, **payload.model_dump()}
    _orders.append(order)
    # 2. PUBLISH an event (past tense) and return immediately - the endpoint
    #    does NOT call or wait for notifications/inventory.
    await bus.publish("order.created", {"order_id": order["id"], "customer": payload.customer})
    return {"order": order, "note": "order.created event published (consumers react async)"}


@app.get("/processed")
async def get_processed():
    # Wait for the bus to drain (demo convenience), then show what happened.
    await bus.wait_idle()
    return {"reactions": processed}


@app.post("/reset")
async def reset():
    processed.clear()
    return {"cleared": True}
