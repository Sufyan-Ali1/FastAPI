# Lesson 31 — WebSockets

> **Goal of this lesson:** Break out of the request/response box. Learn **WebSockets** for real-time, two-way communication over a single persistent connection, the **Connection Manager** pattern for tracking many clients, and **broadcasting** a message to everyone at once.
>
> `main.py` is a runnable multi-user chat: open two browser tabs and watch messages appear live in both. It's also tested with `TestClient`'s WebSocket support.

---

## 1. The Problem — HTTP Can't Push

Everything so far has been **HTTP request/response**: the client asks, the server answers, the connection closes. That's perfect for CRUD, but it has a fundamental limitation:

- The **client must always initiate.** The server can never speak first.
- Each exchange is a **new connection** (or a reused one, but still one round-trip per message).

So how do you build a **chat**, a **live dashboard**, a **notification** that appears instantly, or a **collaborative editor**? With plain HTTP you'd have to **poll** — hammer the server every second asking "anything new?" — which is wasteful and laggy.

**WebSockets** solve this: one connection stays open, and **either side can send a message at any time.**

---

## 2. What Is a WebSocket?

A **WebSocket** is a **persistent, full-duplex** connection between client and server.

- **Persistent** — opened once, kept alive; no reconnecting per message.
- **Full-duplex** — both sides can send **at any time, independently** (not turn-based).
- **Low overhead** — after the initial handshake, messages are tiny frames, no HTTP headers per message.

The URL scheme is `ws://` (or `wss://` for TLS, the secure version — always use `wss://` in production).

```
HTTP:        client ──request──►  server
                    ◄─response──         (then closed; client must ask again)

WebSocket:   client ◄──────────►  server
                   (one open pipe; either side sends whenever it wants)
```

---

## 3. HTTP vs WebSocket

| | HTTP request/response | WebSocket |
|---|---|---|
| Connection | New per exchange | One, persistent |
| Direction | Client asks, server answers | **Both** sides send freely |
| Server push? | No (must poll) | **Yes** |
| Best for | CRUD, REST APIs | Chat, live feeds, notifications, games |
| Overhead per message | Full HTTP headers | Tiny frame |
| Scheme | `http://` / `https://` | `ws://` / `wss://` |

> 🔑 Use WebSockets when the server needs to **push** data or when there's **frequent two-way** traffic. For ordinary request/response, plain HTTP is simpler and correct — don't reach for WebSockets when REST fits.

---

## 4. The WebSocket Lifecycle

A WebSocket starts life as an HTTP request, then **upgrades**:

1. **Handshake** — the client sends an HTTP request with `Upgrade: websocket`. The server **accepts**, switching the protocol.
2. **Open** — the connection is now a live two-way pipe.
3. **Messages** — either side sends text or binary frames, any time, any order.
4. **Close** — either side closes; the other is notified.

In FastAPI you handle exactly these steps.

---

## 5. WebSockets in FastAPI

FastAPI (via Starlette) has built-in support. Use the `@app.websocket` decorator and a `WebSocket` object:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

@app.websocket("/ws/echo")
async def echo(websocket: WebSocket):
    await websocket.accept()               # 1. complete the handshake
    try:
        while True:
            text = await websocket.receive_text()   # 2. wait for a message
            await websocket.send_text(f"echo: {text}")  # 3. send one back
    except WebSocketDisconnect:
        print("client disconnected")       # 4. client closed the connection
```

Key pieces:

- **`@app.websocket("/path")`** — declares a WebSocket route (not `@app.get`).
- The handler is **`async def`** and receives a **`WebSocket`** object.
- **`await websocket.accept()`** — you must accept to complete the handshake before sending/receiving.
- **`receive_text()` / `send_text()`** — the basic message calls (also `receive_json`/`send_json`, `receive_bytes`/`send_bytes`).
- The **`while True`** loop keeps the connection open, handling message after message.
- **`WebSocketDisconnect`** is raised when the client disconnects — catch it to clean up.

> 🔑 WebSocket handlers are **always `async def`** and everything is `await`ed — this is exactly the async model from Lesson 28. A long-lived connection that `await`s incoming messages yields the event loop while waiting, so one server can hold **many** open connections cheaply.

---

## 6. From One Client to Many — The Connection Manager

An echo endpoint only talks to the client that connected. Real apps (chat, dashboards) need the server to reach **all connected clients** — so you must **keep track of every open connection**. That's the **Connection Manager** pattern: a small class that owns the list of active connections.

```python
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active.remove(websocket)

    async def send_personal(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active:
            await connection.send_text(message)

manager = ConnectionManager()
```

- **`connect`** accepts the handshake and records the connection.
- **`disconnect`** removes it (call on `WebSocketDisconnect`).
- **`send_personal`** targets one client.
- **`broadcast`** loops over everyone and sends to all — this is the whole point.

---

## 7. Broadcasting — A Multi-User Chat

With the manager, a chat endpoint is short. On connect, announce the join; on each message, broadcast it; on disconnect, announce the leave:

```python
@app.websocket("/ws/{client_id}")
async def chat(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)
    await manager.broadcast(f"Client {client_id} joined")
    try:
        while True:
            text = await websocket.receive_text()
            await manager.broadcast(f"{client_id}: {text}")   # to EVERYONE
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client {client_id} left")
```

Every connected client receives every broadcast — that's real-time chat. Open two browser tabs against `main.py` and you'll see each message appear in both instantly.

> 🔑 The Connection Manager is the standard FastAPI WebSocket pattern. It centralizes the connection list and the send/broadcast logic so endpoints stay tiny. Extend it with **rooms** (a dict of `room_name -> list[WebSocket]`) to broadcast only within a group.

---

## 8. Sending JSON and Structured Messages

Real apps send structured data, not raw strings. Use the JSON helpers:

```python
await websocket.send_json({"type": "message", "user": "alice", "text": "hi"})
data = await websocket.receive_json()      # -> a dict
```

A common convention is a `type` field (`"message"`, `"join"`, `"typing"`, `"error"`) so the client can react differently to each kind of event. There's also `send_bytes`/`receive_bytes` for binary data.

---

## 9. Handling Disconnects Cleanly

Clients vanish — tabs close, networks drop. **Always** catch `WebSocketDisconnect` and remove the connection, or your manager's list fills with dead connections and broadcasts start failing:

```python
try:
    while True:
        ...
except WebSocketDisconnect:
    manager.disconnect(websocket)     # critical cleanup
```

You can also close from the server side with `await websocket.close(code=1000)`.

---

## 10. Authentication with WebSockets

Browsers **can't** set custom `Authorization` headers when opening a WebSocket, so the Bearer-token approach from Lesson 29 doesn't transfer directly. Common patterns:

- Pass a **token as a query parameter**: `ws://.../ws?token=<jwt>`, validated in the handler before `accept()`.
- Authenticate on the **first message** after connecting.
- Use a **cookie** (sent automatically on the handshake).

```python
@app.websocket("/ws")
async def ws(websocket: WebSocket, token: str):
    user = validate_token(token)          # reuse your Lesson 29 decode logic
    if user is None:
        await websocket.close(code=1008)  # policy violation
        return
    await websocket.accept()
    ...
```

> 🔑 Validate the token **before** `accept()`, and close with an appropriate code if it's invalid. Never trust an unauthenticated socket.

---

## 11. The Scaling Limitation (be honest)

The in-memory `ConnectionManager` holds connections **for one process only.** If you run multiple worker processes or servers (Lesson 50), each has its *own* list — a broadcast from worker A won't reach clients connected to worker B.

The production fix is a **shared message backbone** — usually **Redis Pub/Sub** (or a broker): each worker publishes broadcasts to Redis and subscribes to deliver them to its own local sockets. That's beyond this lesson; the point is to **know the in-memory manager is single-process** and what to reach for when you scale out.

| Setup | Broadcast reaches |
|---|---|
| One process, in-memory manager | All clients (fine for learning / small apps) |
| Many processes/servers | Only that process's clients — need **Redis Pub/Sub** |

---

## 12. Real-World Use Case — Live Features

WebSockets power the "it updates by itself" experiences:

- **Chat / messaging** — the canonical example (this lesson).
- **Live dashboards** — metrics, prices, order status pushed as they change.
- **Notifications** — "you have a new message" without refreshing.
- **Collaborative editing** — Google-Docs-style shared cursors and edits.
- **Multiplayer games** — low-latency two-way state.
- **Live progress** — a long job pushing progress updates to the browser.

Anything where the server must tell the client something *before* the client asks is a WebSocket job. (For **one-way** server→client streaming, the lighter **Server-Sent Events** — Lesson 32 — is often a better fit.)

---

## 13. Mini Task

`main.py` is a runnable multi-user chat with an in-browser client.

1. Run: `uvicorn main:app --reload`
2. Open **two** browser tabs at `http://127.0.0.1:8000/`. Each is a chat client.
3. Type in one tab and hit send → the message appears **instantly in both tabs** (broadcast). Watch join/leave notices too.
4. Close one tab → the other shows a "left" message (disconnect handling).
5. Try the raw echo socket in the docs or with a WS client: connect to `/ws/echo` and send text.
6. **Experiment:**
   - Add a `send_json` message with a `type` field and update the client to render `join`/`leave`/`message` differently.
   - Add simple **rooms**: change the manager to hold `dict[str, list[WebSocket]]` and broadcast only within a room from `/ws/{room}/{client_id}`.
7. **Bonus:** Require a `?token=` query parameter and reject the connection (close code `1008`) if it's missing — reuse the JWT decode idea from Lesson 29.

---

## 14. Common Mistakes

| Mistake | Fix |
|---|---|
| Forgetting `await websocket.accept()` | You must accept before sending/receiving. |
| Not catching `WebSocketDisconnect` | Dead connections pile up and broadcasts break. |
| Not removing a socket on disconnect | Always `manager.disconnect(...)` in the except block. |
| Using `@app.get` for a WebSocket | Use `@app.websocket(...)`. |
| Declaring `/ws/{id}` before a static `/ws/echo` | Static WS routes must come **before** dynamic ones, or they're shadowed (same rule as HTTP — Lesson 4). |
| Expecting the in-memory manager to work across workers | Use Redis Pub/Sub for multi-process broadcasting. |
| Sending `Authorization` header from a browser WS | Use a query-param token or cookie; validate before `accept()`. |
| Blocking the event loop inside the handler | It's `async def` — `await` I/O, keep it non-blocking (Lesson 28). |

---

## 15. Key Takeaways

- A **WebSocket** is a persistent, full-duplex connection: **either side can send at any time**, enabling server **push**.
- Use `@app.websocket(...)`, an `async def` handler, `await websocket.accept()`, then `receive_*`/`send_*` in a loop.
- Catch **`WebSocketDisconnect`** and clean up the connection.
- The **Connection Manager** pattern tracks all active connections and centralizes **broadcast** / personal-send logic.
- **Broadcasting** = loop over all connections and send — the basis of chat, live dashboards, and notifications.
- Send structured data with **`send_json`/`receive_json`**; use a `type` field to distinguish events.
- **Authenticate before `accept()`** using a query-param token or cookie (browsers can't set WS auth headers).
- The in-memory manager is **single-process**; multi-worker broadcasting needs **Redis Pub/Sub**.

---

## ➡️ Next Lesson

**Lesson 32 — Server-Sent Events (SSE) / Streaming Responses**
- `StreamingResponse` for one-way server→client streams
- SSE vs WebSockets — when each fits
- The LLM token-by-token streaming use case
