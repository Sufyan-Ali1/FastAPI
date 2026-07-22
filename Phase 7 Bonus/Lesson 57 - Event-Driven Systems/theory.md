# Lesson 57 — Event-Driven Systems

> **Goal of this lesson:** Decouple services with **events** instead of direct calls. Learn the **publish/subscribe** model, the role of a **message broker** (**RabbitMQ** vs **Kafka**), how producers and consumers work, **delivery guarantees** and **idempotency**, and when event-driven beats the synchronous calls from Lesson 56.
>
> `main.py` runs a real in-process async **pub/sub bus**: publishing one `order.created` event fans out to multiple independent consumers (notifications, inventory) — the exact pattern RabbitMQ/Kafka provide at scale.

---

## 1. The Problem — Synchronous Coupling

In Lesson 56, the Orders service **called** the Notifications and Inventory services directly (sync HTTP). That works, but it couples them **in time**:

- If Notifications is down or slow, creating an order is slow or fails.
- Orders must **know about** every service that cares about a new order.
- Adding a new consumer (say, Analytics) means changing the Orders code.

**Event-driven** flips this: Orders just **announces** "an order was created" and moves on. Whoever cares **subscribes** and reacts — Orders doesn't know or wait for them.

```
Synchronous (coupled):        Orders ──calls──► Notifications
                                     ──calls──► Inventory
                                     ──calls──► Analytics   (Orders must know all)

Event-driven (decoupled):     Orders ──"order.created"──► [Broker] ──► Notifications
                                                                   ──► Inventory
                                                                   ──► Analytics
                              (Orders announces once, doesn't know or wait)
```

> 🔑 Synchronous calls **couple services in time** (a slow dependency slows you) and in **knowledge** (the caller must know all dependents). **Events decouple both**: the producer announces and moves on; consumers react independently.

---

## 2. Commands vs Events

The mental shift is from **commands** (telling a specific service to do something) to **events** (announcing that something happened):

| | Command | Event |
|---|---|---|
| Intent | "Do X" (imperative) | "X happened" (past tense) |
| Direction | Sent to a **specific** handler | Broadcast to **whoever cares** |
| Coupling | Sender knows the receiver | Sender doesn't know consumers |
| Example | `sendEmail(user)` | `order.created` |

Events are named in the **past tense** (`order.created`, `payment.failed`, `user.registered`) because they describe a fact that already occurred — not a request.

> 🔑 Think in **events** ("something happened", past tense), not **commands** ("do this"). The producer states a fact; any number of consumers decide what to do about it. That inversion is what enables decoupling.

---

## 3. The Message Broker

Producers and consumers don't talk directly — a **message broker** sits between them, receiving published events and delivering them to subscribers. It's the async equivalent of the API gateway:

```
Producer ──publish──► [ Message Broker ] ──deliver──► Consumer(s)
                       (RabbitMQ, Kafka)
                       - stores events durably
                       - routes to subscribers
                       - handles retries, ordering
```

The broker provides:
- **Durability** — events persist until consumed (survive a consumer restart).
- **Routing** — deliver each event to the right subscribers.
- **Buffering** — absorb bursts; consumers process at their own pace.
- **Retries / dead-lettering** — re-deliver failed events; park un-processable ones.

> 🔑 A **message broker** decouples producers from consumers: the producer publishes to the broker (not to consumers directly), and the broker durably delivers to whoever subscribed. It's the backbone of event-driven systems.

---

## 4. Publish/Subscribe vs Queues

Two core delivery patterns brokers support:

| Pattern | Delivery | Use for |
|---|---|---|
| **Pub/Sub (fan-out)** | **Every** subscriber gets a copy of each event | Notify many services of one event (`order.created` → notifications + inventory + analytics) |
| **Work queue (competing consumers)** | **One** of N workers processes each message | Distribute work / load-balance tasks (5 workers share a queue of jobs) |

```
Pub/Sub (fan-out):                    Work queue (one worker each):
event ──► Consumer A (gets it)        job ──► Worker 1  (or)
      ──► Consumer B (gets it)              ──► Worker 2  (or)
      ──► Consumer C (gets it)              ──► Worker 3   (exactly one handles it)
```

`main.py` demonstrates **pub/sub**: one event reaches all subscribers. Work queues are how you scale a single kind of processing across workers.

> 🔑 **Pub/sub** fans one event out to **all** subscribers (different services react); a **work queue** distributes messages so **one** of many workers handles each (scaling a task). Brokers do both.

---

## 5. Producers and Consumers

Two roles:

- **Producer (publisher)** — code that publishes events. In FastAPI, an endpoint publishes after doing its work: create the order, then publish `order.created`.
- **Consumer (subscriber)** — code that subscribes to an event type and reacts. Consumers usually run as **separate processes/workers** listening to the broker.

```python
# Producer: the Orders endpoint
@app.post("/orders")
async def create_order(payload: OrderCreate):
    order = save_order(payload)
    await broker.publish("order.created", {"order_id": order.id, ...})  # fire-and-forget
    return order                                                        # returns immediately

# Consumer: a separate worker subscribing to the event
@broker.subscribe("order.created")
async def send_confirmation(event):
    await email.send(event["customer_email"], "Your order is confirmed")
```

The producer **doesn't wait** for consumers — it publishes and returns. Consumers process asynchronously, at their own pace.

> 🔑 A **producer** publishes an event and returns immediately (fire-and-forget); **consumers** subscribe and react asynchronously, typically as separate workers. The producer's latency doesn't depend on the consumers.

---

## 6. RabbitMQ vs Kafka

The two dominant brokers, with different designs:

| | **RabbitMQ** | **Kafka** |
|---|---|---|
| Model | Traditional **message broker** (queues, exchanges) | Distributed **event log / streaming** |
| Metaphor | A smart post office (routes & deletes messages) | An append-only log you replay |
| Message lifetime | Deleted once consumed (usually) | **Retained** for a period; consumers track position |
| Replay past events | No (gone once acked) | **Yes** (re-read from any offset) |
| Throughput | High | **Very high** (millions/sec) |
| Ordering | Per-queue | Per-partition |
| Best for | Task queues, routing, RPC, general messaging | Event streaming, analytics, high-volume pipelines, event sourcing |

- **RabbitMQ** — flexible routing (exchanges/bindings), great for work queues and complex routing; messages are consumed and gone.
- **Kafka** — an ordered, durable **log** that consumers read at their own offset and can **replay**; built for massive event streams and multiple independent consumer groups.

> 🔑 **RabbitMQ** is a message broker (route + deliver + delete); **Kafka** is a durable, replayable event log (retain + read by offset). Choose RabbitMQ for task queues/routing, Kafka for high-volume event streaming and replay.

---

## 7. Delivery Guarantees & Idempotency

Distributed messaging can't be perfect; brokers offer different **delivery guarantees**:

| Guarantee | Meaning | Risk |
|---|---|---|
| **At-most-once** | Delivered 0 or 1 times | May **lose** messages |
| **At-least-once** ⭐ | Delivered 1+ times | May **duplicate** messages |
| **Exactly-once** | Delivered exactly once | Hard/expensive; limited support |

Most systems use **at-least-once** — which means consumers **must tolerate duplicates**. The solution is **idempotency**: processing the same event twice has the same effect as once.

```python
async def handle_order_created(event):
    if already_processed(event["event_id"]):   # dedupe by a unique event id
        return                                  # skip duplicates
    charge_payment(event["order_id"])
    mark_processed(event["event_id"])
```

> 🔑 Assume **at-least-once** delivery: events **can arrive more than once**. Make consumers **idempotent** (dedupe by a unique event id) so duplicates don't double-charge, double-ship, or double-send. This is non-negotiable in event systems.

---

## 8. The Challenges

Event-driven systems bring their own hard problems:

- **Eventual consistency** — consumers react *after* the event; the system is briefly inconsistent (an order exists before its confirmation email is sent). You must design for this.
- **Ordering** — events may arrive out of order (except within a Kafka partition); don't assume strict order unless the broker guarantees it.
- **Duplicates** — handled by idempotency (§7).
- **Poison messages** — an event that always fails; brokers park these in a **dead-letter queue** (DLQ) instead of retrying forever.
- **Debugging** — a flow spans producer → broker → multiple consumers; **distributed tracing** (Lesson 53) is essential.
- **No immediate response** — the producer can't get a result back synchronously (it's fire-and-forget).

> 🔑 Events buy decoupling but cost **eventual consistency, possible reordering/duplication, and harder debugging**. Design for out-of-order, at-least-once delivery, use **dead-letter queues** for poison messages, and trace flows across services.

---

## 9. Event Patterns

Three common ways to use events (increasing in ambition):

- **Event notification** — a thin event ("order 42 created"); interested consumers call back for details if needed. Simplest.
- **Event-carried state transfer** — the event **carries the data** consumers need (the whole order), so they don't call back. Reduces coupling further.
- **Event sourcing** — store the **stream of events** as the source of truth; rebuild state by replaying them (Kafka excels here). Powerful but advanced.

> 💡 Start with **event notification** or **event-carried state transfer**. **Event sourcing** is powerful (full audit log, time-travel) but a big commitment — adopt it deliberately, not by default.

---

## 10. Real-World Use Case — Order Fulfillment

A customer places an order in the auction/shop system. Synchronously, the Orders service would have to call five services and wait. Event-driven instead:

- Orders saves the order and publishes **`order.created`** (with the order details) — then returns to the customer **immediately**.
- Independent consumers each react: **Notifications** sends a confirmation email, **Inventory** decrements stock, **Payments** captures the charge, **Analytics** records the sale, **Shipping** schedules dispatch.
- Each consumer is **idempotent** (dedupes by order/event id) because delivery is at-least-once.
- Adding **Loyalty points** later means writing one new consumer — **no change to Orders**.
- A failed consumer (Notifications is down) doesn't block the order; the broker re-delivers when it recovers.

The order flow is fast, resilient, and extensible — exactly what `main.py` demonstrates with its fan-out to multiple consumers.

---

## 11. Mini Task

`main.py` runs an in-process pub/sub bus (the pattern RabbitMQ/Kafka provide).

1. Install: `pip install fastapi uvicorn` (the bus is pure asyncio — no broker needed).
2. Run: `uvicorn main:app --reload`.
3. `POST /orders` → the endpoint **publishes** `order.created` and returns immediately.
4. `GET /processed` → see that **multiple independent consumers** (notifications, inventory) each handled the same event — one publish, many reactions.
5. Note the producer never waited for or knew about the consumers.
6. **Experiment:**
   - Add a third consumer (analytics) subscribing to `order.created` — **without touching** the order endpoint (the extensibility payoff).
   - Make a consumer publish a follow-up event (`inventory.low`) and have another consumer react (event chains).
   - Add an `event_id` and make a consumer idempotent (skip duplicates).
7. **Bonus (conceptual):** Map the in-memory bus to RabbitMQ (an exchange + queues) or Kafka (a topic + consumer groups).

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Using events where a sync call is simpler | Events for decoupled side-effects; sync for a needed immediate answer. |
| Consumers that break on duplicate events | Make them **idempotent** (dedupe by event id). |
| Assuming strict global ordering | Don't, unless the broker guarantees it (e.g. Kafka partition). |
| Expecting immediate consistency | Events are eventually consistent; design for the gap. |
| No dead-letter queue | Poison messages retry forever; route them to a DLQ. |
| Naming events as commands | Name events in the **past tense** (`order.created`). |
| No tracing across the event flow | Add distributed tracing; event flows are hard to debug otherwise. |

---

## 13. Key Takeaways

- **Event-driven** systems decouple services: producers **announce events**; consumers **react** — no direct calls, no waiting, no knowing each other.
- Think **events** (past-tense facts), not **commands**; the producer publishes and returns (fire-and-forget).
- A **message broker** (RabbitMQ/Kafka) sits between producers and consumers, delivering durably.
- **Pub/sub** fans an event out to all subscribers; a **work queue** distributes messages across competing workers.
- **RabbitMQ** = route-and-delete message broker (queues, task work); **Kafka** = durable, replayable event log (streaming, event sourcing).
- Assume **at-least-once** delivery → make consumers **idempotent** (dedupe by event id).
- Costs: **eventual consistency**, possible **reordering/duplication**, **dead-letter queues** for poison messages, and harder debugging (need tracing).
- Use events for **decoupled side-effects and extensibility**; keep synchronous calls for when you truly need an immediate answer.

---

## ➡️ Next Lesson

**Lesson 58 — gRPC alongside FastAPI**
- gRPC vs REST: binary, typed, high-performance RPC
- Protocol Buffers and service definitions
- When to use gRPC for internal service-to-service calls
