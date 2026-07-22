# Lesson 56 — Microservices Architecture with FastAPI

> **Goal of this lesson:** Understand the **microservices** architecture — many small, independently deployable services instead of one big app. Learn how to draw **service boundaries**, how services **communicate** (sync HTTP/gRPC vs async events), the role of an **API gateway** and **database-per-service**, the hard **distributed-systems** trade-offs, and — crucially — **when microservices are worth it (and when they're not).**
>
> `main.py` runs **two FastAPI services** (users + orders) where the orders service makes a real inter-service HTTP call to the users service, including failure handling.

---

## 1. Monolith vs Microservices

Everything you've built so far is a **monolith**: one codebase, one deployable app, one database. That's a perfectly good architecture — most successful apps are monoliths.

**Microservices** split the system into many **small, independent services**, each owning one business capability, each deployable on its own:

```
MONOLITH:                          MICROSERVICES:
┌────────────────────┐            ┌────────┐  ┌────────┐  ┌──────────┐
│  one app           │            │ Users  │  │ Orders │  │ Payments │
│  users + orders    │            │ service│  │ service│  │ service  │
│  + payments        │            └───┬────┘  └───┬────┘  └────┬─────┘
│  one database      │                │           │            │
└────────────────────┘             users DB    orders DB   payments DB
```

| | Monolith | Microservices |
|---|---|---|
| Deploy | One unit | Each service independently |
| Scaling | Scale the whole app | Scale hot services only |
| Team ownership | Shared codebase | Each team owns a service |
| Data | One shared DB | A DB per service |
| Complexity | Simpler | **Distributed-system** complexity |
| Failure | All-or-nothing | Partial (one service can fail) |

> 🔑 Microservices trade **simplicity** for **independence and scalability**. They're not "better" than a monolith — they're a different set of trade-offs that pay off at a certain scale/team size and cost you dearly below it.

---

## 2. What Makes a Service a "Microservice"

A microservice is:

- **Small & focused** — one business capability (users, orders, payments, notifications).
- **Independently deployable** — ships on its own schedule without redeploying everything.
- **Owns its data** — its own database; other services never touch it directly.
- **Loosely coupled** — talks to others only through **APIs** (HTTP, gRPC) or **events**, never shared code/DB internals.
- **Independently scalable** — run 10 copies of the hot service, 1 of a quiet one.

Each service is essentially a small FastAPI app with the production structure from Lesson 44 — just scoped to one domain.

> 🔑 A microservice **owns one business capability and its data**, deploys independently, and communicates only through well-defined **APIs or events** — never by reaching into another service's database or code.

---

## 3. Service Boundaries — The Hardest Part

The single hardest question in microservices: **where do you draw the lines?** Draw them wrong and you get "distributed spaghetti" — services that constantly call each other for every operation, worse than a monolith.

Good boundaries follow **business capabilities** (bounded contexts from Domain-Driven Design): Users, Orders, Payments, Inventory, Notifications. A service should own a cohesive slice of the domain and be able to do most of its work **without** synchronously calling five others.

Signs of a **bad** boundary: two services always deploy together, one can't function without constant calls to another, or a single user action fans out to many services synchronously.

> 🔑 Draw service boundaries around **business capabilities**, not technical layers. A good service does its job mostly on its own; if every operation requires calling several other services, your boundaries are wrong.

---

## 4. How Services Communicate

Services talk in two fundamentally different styles:

### 4.1 Synchronous (request/response)

The caller waits for a response — like a normal API call:

- **HTTP/REST** — the most common; simple, universal (this lesson's demo). One service calls another's endpoint with `httpx`.
- **gRPC** — binary, fast, typed (Lesson 58); good for high-volume internal calls.

```python
# Orders service calls the Users service synchronously:
async with httpx.AsyncClient() as client:
    resp = await client.get(f"{USERS_URL}/users/{user_id}")
    if resp.status_code == 404:
        raise HTTPException(404, "User not found")
```

**Trade-off:** simple and immediate, but creates **temporal coupling** — if the Users service is down or slow, the Orders service is too.

### 4.2 Asynchronous (events/messaging)

The caller publishes an **event** to a message broker (RabbitMQ, Kafka — Lesson 57) and moves on; interested services react later:

```
Orders service ──"order.created"──► [Message Broker] ──► Notifications service
                                                     └──► Inventory service
```

**Trade-off:** resilient and decoupled (a down service catches up later), but **eventually consistent** and harder to reason about.

> 🔑 **Sync (HTTP/gRPC)** is simple but couples services in time (a slow dependency slows you). **Async (events)** decouples them and adds resilience but trades immediate consistency for eventual. Real systems use **both** — sync for queries, async for side effects.

---

## 5. The API Gateway

With many services, you don't want clients calling each one directly. An **API gateway** is a single entry point that routes requests to the right service and handles cross-cutting concerns:

```
              ┌──────────── API Gateway ────────────┐
clients ────► │ routing, auth, rate limiting, TLS,  │ ──► Users service
              │ request aggregation                 │ ──► Orders service
              └─────────────────────────────────────┘ ──► Payments service
```

- **Single entry point** — clients hit one URL; the gateway routes internally.
- **Cross-cutting concerns** — authentication (Lesson 29), rate limiting (Lesson 34), TLS, CORS — done once at the edge instead of in every service.
- **Aggregation** — combine data from several services into one client response.

Options: dedicated gateways (Kong, Traefik, cloud API Gateways) or a thin FastAPI app acting as one.

> 🔑 An **API gateway** gives clients one entry point and centralizes auth, rate limiting, and routing at the edge — so individual services focus on business logic, not repeated cross-cutting concerns.

---

## 6. Database Per Service

The **defining rule** of microservices: **each service owns its own database, and no other service touches it directly.**

```
✅ Orders service ──API call──► Users service ──► users DB
❌ Orders service ──directly queries──► users DB      (FORBIDDEN)
```

Why: a shared database couples every service to one schema — change a table and you break everyone, and you can't deploy or scale independently. Database-per-service is what makes services truly independent.

The cost: data that lived in one database with JOINs and transactions is now **spread across services**. Cross-service queries become API calls, and cross-service consistency needs new patterns (§8).

> 🔑 **Database-per-service** is the rule that makes microservices independent — no shared database, no reaching into another service's data. It's also the source of most microservices complexity (no cross-service JOINs or transactions).

---

## 7. Service Discovery & Config

Services need to **find** each other. "Where is the Users service?" is answered by:

- **Config / environment variables** (Lesson 45) — `USERS_SERVICE_URL=http://users-service:8000` (simple; used in this demo).
- **DNS / service names** — in Docker Compose or Kubernetes, services reach each other by name (Lesson 49).
- **Service discovery systems** — Consul, Eureka, or the orchestrator's built-in discovery (K8s Services) — for dynamic, scaling environments.

> 🔑 Services locate each other via **config/DNS/service names** (simple) or a **service-discovery system** (dynamic). In containers/K8s, service names + the platform's discovery usually suffice — no hardcoded IPs.

---

## 8. The Distributed-Systems Tax

Splitting into services introduces problems a monolith never had. This is the real cost:

| Challenge | In a monolith | In microservices |
|---|---|---|
| **Transactions** | One DB transaction (atomic) | Spread across services → **Saga pattern** (compensating actions) |
| **Consistency** | Immediate | **Eventual** (events propagate over time) |
| **A call fails** | A function returns | **Network partial failure** — timeouts, retries needed |
| **Debugging** | One stack trace | **Distributed tracing** required (Lesson 53) |
| **Deployment** | One deploy | Many services, versioned APIs (Lesson 54) |
| **Testing** | In-process | Integration across services |

The big one: **you can't do a database transaction across services.** "Create an order AND charge payment atomically" becomes a **Saga** — a sequence of steps with **compensating actions** to undo on failure (cancel the order if payment fails). Distributed transactions are hard; this is the price of independence.

> 🔑 Microservices pay a **distributed-systems tax**: no cross-service transactions (use Sagas), eventual consistency, partial failures, and a hard requirement for **distributed tracing** and **observability**. Underestimating this tax is the #1 microservices mistake.

---

## 9. Resilience — Handling Partial Failure

Because any inter-service call can fail (network, a down service), services must be **resilient**:

- **Timeouts** — never wait forever on another service (`httpx` timeout).
- **Retries** — retry transient failures (with backoff), but carefully (avoid retry storms).
- **Circuit breaker** — after repeated failures, stop calling a dead service for a while (fail fast) instead of hammering it.
- **Graceful degradation** — return a sensible fallback when a non-critical dependency is down.

`main.py` shows the basics: the Orders service sets a timeout and returns a clear `503` if the Users service is unreachable, instead of hanging.

> 🔑 Every inter-service call **can and will fail**. Use **timeouts, retries with backoff, circuit breakers, and graceful degradation** — a monolith never needed these, but a distributed system does.

---

## 10. When to Use Microservices (and When Not)

This is the most important takeaway. Microservices solve **organizational and scaling** problems — at a real cost.

**Good reasons:**
- **Large teams** that need to deploy independently without stepping on each other.
- **Different scaling needs** — one part gets 100× the traffic of another.
- **Different tech/teams** per domain.
- **Independent release cadences**.

**Bad reasons (start with a monolith):**
- Small team or early-stage product — the overhead will crush you.
- "It's the modern way" / résumé-driven design.
- You haven't hit scaling or team-coordination pain yet.

The widely-held wisdom: **"Monolith first."** Build a well-structured monolith (Lesson 44); extract services only when you feel real pain that microservices solve. Many teams that jumped straight to microservices regretted it (the "distributed monolith" — all the complexity, none of the benefits).

> 🔑 **Start with a monolith. Extract microservices only when a concrete problem (team scale, independent scaling, release independence) demands it.** Premature microservices add enormous complexity for benefits you don't yet need.

---

## 11. Real-World Use Case — Extracting a Service

Your monolithic auction app has grown; the **notifications** part (emails, SMS, push) is heavily used, has different scaling needs, and a separate team wants to own it. That's a concrete reason to extract it:

- Carve out a **Notifications service** with its own database and deploy.
- The auction app publishes an **event** (`bid.outbid`) to a broker; the Notifications service consumes it asynchronously (Lesson 57) — decoupled, so a notification hiccup never blocks bidding.
- The **API gateway** routes and authenticates; **distributed tracing** (Lesson 53) follows a request across both; each service has its **own DB**.
- The rest of the app stays a monolith — you extracted **one** service for a **real** reason, not split everything on principle.

That surgical extraction — driven by actual pain — is how microservices should enter a codebase.

---

## 12. Mini Task

`main.py` runs a Users service and an Orders service; Orders calls Users over HTTP.

1. Run: `uvicorn main:app --reload` (a small gateway that mounts both, for the demo) → open `/docs`.
2. Create an order for an **existing** user → succeeds (the Orders service called the Users service to validate).
3. Create an order for a **missing** user → `404` (Users returned 404; Orders handled it).
4. Read how the Orders endpoint makes an **inter-service HTTP call** with a timeout, and returns `503` if Users is unreachable.
5. **Experiment:**
   - Point the Orders service at a wrong Users URL and watch it fail gracefully (`503`), not hang.
   - Identify the service boundary: why are Users and Orders separate services here?
   - Sketch how you'd make order-creation notify via an **event** instead of a sync call.
6. **Bonus:** Add a tiny API-gateway route that aggregates a user + their orders from both services into one response.

---

## 13. Common Mistakes

| Mistake | Fix |
|---|---|
| Microservices for a small team/early product | Start with a monolith; extract later. |
| Services sharing one database | Database-per-service; talk via APIs/events. |
| Boundaries by technical layer, not domain | Draw boundaries around business capabilities. |
| No timeouts/retries on inter-service calls | Every call can fail — add resilience. |
| Expecting cross-service transactions | Use Sagas / eventual consistency. |
| No distributed tracing | You can't debug distributed systems without it. |
| A "distributed monolith" (services that deploy together) | Wrong boundaries — services must be independent. |

---

## 14. Key Takeaways

- **Microservices** = many small, independently deployable services, each owning one capability and **its own database**.
- They trade a monolith's **simplicity** for **independence and per-service scalability** — worth it at scale, costly below it.
- Draw **boundaries around business capabilities**; a good service works mostly on its own.
- Services communicate **synchronously** (HTTP/gRPC — simple, coupled in time) or **asynchronously** (events — resilient, eventually consistent); real systems use both.
- An **API gateway** centralizes routing, auth, and rate limiting at the edge; **database-per-service** is the rule that makes services independent.
- They incur a **distributed-systems tax**: no cross-service transactions (**Sagas**), eventual consistency, partial failure (**timeouts/retries/circuit breakers**), and mandatory **tracing**.
- **Start with a monolith; extract services only when a real problem demands it.** Premature microservices are a classic, expensive mistake.

---

## ➡️ Next Lesson

**Lesson 57 — Event-Driven Systems**
- Message brokers (RabbitMQ, Kafka) and the publish/subscribe model
- Producing and consuming events
- Async decoupling between services
