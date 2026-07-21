# Lesson 32 — Server-Sent Events (SSE) & Streaming Responses

> **Goal of this lesson:** Send data to the client **incrementally**, as it's produced, instead of waiting for the whole response. Learn **`StreamingResponse`**, the **Server-Sent Events (SSE)** protocol for one-way server→client push, how SSE differs from WebSockets, and the headline modern use case: **LLM token-by-token streaming**.
>
> `main.py` includes a live in-browser demo that "types out" a simulated LLM response token by token — the exact UX you see in ChatGPT/Claude.

---

## 1. Where We Are

Lesson 31's WebSockets gave **two-way** real-time communication. But a huge number of "real-time" needs are actually **one-way**: the server pushes updates to the client, and the client never needs to push back mid-stream.

- An LLM streaming its answer token by token.
- A progress bar for a long job.
- A live log tail or a metrics feed.
- Downloading a large report generated on the fly.

For these, a full WebSocket is overkill. You want **streaming over plain HTTP** — and the two tools are **`StreamingResponse`** and **SSE**.

---

## 2. The Problem — Don't Wait for the Whole Response

Normally FastAPI builds the **entire** response, then sends it. If the body is large or produced slowly, the client sees **nothing** until it's all done:

```python
@app.get("/report")
def report():
    rows = build_10mb_report()   # takes 5 seconds, holds it all in memory
    return rows                  # client waits 5s, then gets everything at once
```

Two problems: the client waits the full time before *any* output, and the whole thing sits in memory. **Streaming** fixes both — send pieces as they're ready.

---

## 3. `StreamingResponse` — Stream Anything

`StreamingResponse` takes a **generator** (sync or async) and sends each yielded chunk as it's produced, keeping the connection open until the generator finishes.

```python
from fastapi.responses import StreamingResponse

def generate_rows():
    yield "id,name\n"
    for i in range(1000):
        yield f"{i},item-{i}\n"      # each chunk flushed to the client as produced

@app.get("/download")
def download():
    return StreamingResponse(generate_rows(), media_type="text/csv")
```

- Pass a **generator** (something that `yield`s). Each `yield`ed piece is sent immediately.
- Set the right **`media_type`** (`text/csv`, `application/json`, `text/plain`, `text/event-stream`…).
- Memory stays low — you never hold the whole body at once.

### 3.1 Async generators

For non-blocking streaming (the usual case), use an **async generator** with `await` between chunks — this respects the Lesson 28 rule (don't block the event loop while streaming):

```python
import asyncio

async def generate():
    for chunk in produce_chunks():
        yield chunk
        await asyncio.sleep(0)     # yield control to the event loop
```

> 🔑 `StreamingResponse` + a generator = send the body in pieces. The client starts receiving immediately and memory stays flat. This is the foundation for both big downloads **and** SSE.

---

## 4. What Is SSE (Server-Sent Events)?

**Server-Sent Events** is a simple standard protocol for a server to **push a stream of events to the client over one long-lived HTTP response.** It's `StreamingResponse` with a specific **format** and **content type**.

- **One-way**: server → client only. (The client opens it with a normal GET.)
- Runs over **plain HTTP** — no protocol upgrade like WebSockets.
- The browser has a **built-in client** (`EventSource`) with **automatic reconnection**.
- Content type is **`text/event-stream`**.

```
HTTP GET /events        (client opens once)
        ◄── data: first update\n\n
        ◄── data: second update\n\n
        ◄── data: third update\n\n
        ... (stays open, server pushes when it has something)
```

---

## 5. The SSE Message Format

SSE messages are plain text with a tiny structure. Each message is one or more `field: value` lines, terminated by a **blank line** (`\n\n`):

```
data: Hello                    ← the payload

data: {"token": "world"}       ← payload can be JSON (you serialize it)

event: progress                ← optional: a named event type
data: 42

id: 7                          ← optional: an event id (for resuming)
retry: 3000                    ← optional: reconnect delay in ms
data: with metadata
```

| Field | Meaning |
|---|---|
| `data:` | The message payload (required). Multiple `data:` lines are joined with `\n`. |
| `event:` | A custom event name the client can listen for specifically. |
| `id:` | An id; the browser sends `Last-Event-ID` on reconnect so you can resume. |
| `retry:` | How long the browser waits before reconnecting, in milliseconds. |

> 🔑 The critical detail: **every message ends with a blank line (`\n\n`).** Forget it and the client buffers forever, seeing nothing. This is the #1 SSE bug.

---

## 6. SSE in FastAPI

SSE is just a `StreamingResponse` with `media_type="text/event-stream"` and correctly formatted chunks:

```python
import asyncio, json
from fastapi.responses import StreamingResponse

async def event_stream():
    for i in range(5):
        payload = json.dumps({"count": i})
        yield f"data: {payload}\n\n"        # note the double newline
        await asyncio.sleep(1)

@app.get("/sse")
async def sse():
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Recommended headers for reliability behind proxies:

```python
headers = {
    "Cache-Control": "no-cache",      # don't cache the stream
    "X-Accel-Buffering": "no",        # tell nginx not to buffer it
}
return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
```

> 💡 The `sse-starlette` library provides an `EventSourceResponse` that formats fields, sends keep-alive pings, and handles disconnects for you. It's a nice convenience, but you can do SSE with the built-in `StreamingResponse` — which is what this lesson uses so you understand the raw format.

---

## 7. The Browser Client — `EventSource`

Browsers consume SSE with the built-in **`EventSource`** API — no library needed, and it **auto-reconnects** if the connection drops:

```javascript
const source = new EventSource("/sse");
source.onmessage = (e) => console.log("got:", e.data);   // default 'message' events
source.addEventListener("progress", (e) => ...);          // named events
source.onerror = () => console.log("reconnecting...");    // auto-retries
```

That built-in reconnection is a real advantage of SSE over rolling your own polling or WebSocket reconnect logic.

---

## 8. SSE vs WebSockets

Both give real-time server→client updates. Choose by **directionality and complexity**:

| | **SSE** | **WebSockets** |
|---|---|---|
| Direction | **One-way** (server → client) | **Two-way** (full duplex) |
| Protocol | Plain HTTP (`text/event-stream`) | Upgraded protocol (`ws://`) |
| Browser client | Built-in `EventSource` | Built-in `WebSocket` |
| Auto-reconnect | **Yes**, built in | No (you implement it) |
| Data type | Text only | Text **and** binary |
| Complexity | Simple | More involved |
| Best for | LLM streams, feeds, progress, notifications | Chat, games, collaborative editing |

> 🔑 **If the client only needs to receive, use SSE.** It's simpler, runs over normal HTTP, and reconnects itself. Reach for WebSockets only when the client must also **send** continuously (chat, multiplayer). Don't use a WebSocket where SSE suffices.

---

## 9. The Headline Use Case — LLM Token Streaming

Modern AI chat UIs (ChatGPT, Claude) feel responsive because they **stream the answer token by token** instead of making you wait for the whole reply. That's SSE (or a similar chunked stream) in action.

The pattern: as the model produces each token, yield it as an SSE event; the browser appends it to the screen, creating the "typing" effect.

```python
async def stream_answer(prompt: str):
    async for token in call_llm_streaming(prompt):   # provider's streaming API
        yield f"data: {json.dumps({'token': token})}\n\n"
    yield "data: [DONE]\n\n"                          # a sentinel to signal completion

@app.get("/chat")
async def chat(prompt: str):
    return StreamingResponse(stream_answer(prompt), media_type="text/event-stream")
```

- Each token is flushed **immediately**, so the user sees text appear progressively.
- A sentinel like `[DONE]` tells the client the stream is complete so it can close.
- `main.py` simulates this with a canned response split into tokens — the FastAPI streaming mechanics are identical whether the tokens come from a fake generator or a real model's streaming API.

> 💡 In a real app, the tokens come from your LLM provider's **streaming** endpoint (each provider exposes one). The FastAPI side — wrapping those tokens in SSE and flushing them — is exactly what you see here.

---

## 10. Streaming Large Data & Files

`StreamingResponse` isn't only for SSE. It's the right tool whenever the body is **large** or **generated on the fly**:

- **CSV/JSON exports** — yield rows as you read them from the DB, never loading all into memory.
- **File downloads** — stream a file in chunks (also `FileResponse` for static files).
- **Proxying** — stream another service's response through as it arrives.

```python
@app.get("/export.csv")
def export():
    def rows():
        yield "id,name,price\n"
        for p in iter_products_from_db():          # a generator, not a full list
            yield f"{p.id},{p.name},{p.price}\n"
    return StreamingResponse(rows(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"})
```

The `Content-Disposition: attachment` header makes the browser download it as a file.

---

## 11. Gotchas

| Gotcha | Fix |
|---|---|
| Client sees nothing | Each SSE message must end with a **blank line** (`\n\n`). |
| Stream buffered by a proxy (nginx) | Send `X-Accel-Buffering: no` and `Cache-Control: no-cache`. |
| Blocking the event loop while streaming | Use an **async** generator and `await` between chunks. |
| Connection never closes | Send a completion sentinel (e.g. `[DONE]`) and/or handle client disconnect. |
| Trying to send binary over SSE | SSE is text-only; use WebSockets or a raw stream for binary. |

---

## 12. Real-World Use Case — A Chat Endpoint

Your app has an AI assistant. Without streaming, the user clicks "send" and stares at a spinner for 8 seconds until the full answer appears. With SSE:

- The endpoint returns a `StreamingResponse` of `text/event-stream`.
- Tokens flush as the model generates them; the browser's `EventSource` appends each to the chat bubble.
- The user sees words appear immediately — perceived latency drops from 8s to ~200ms even though total time is the same.
- If the network blips, `EventSource` reconnects automatically.

Same technique powers live progress bars, log tailing, and dashboards — anywhere the server produces output over time.

---

## 13. Mini Task

`main.py` demonstrates streaming and SSE, including a live LLM-style typing demo.

1. Run: `uvicorn main:app --reload`
2. Open `http://127.0.0.1:8000/` → type a prompt and watch the answer **stream in token by token** (the ChatGPT effect), powered by SSE + `EventSource`.
3. In the docs or browser, hit:
   - `/sse/clock` → an SSE stream pushing the time a few times.
   - `/download/report.csv` → a streamed CSV download.
4. Open your browser dev tools → Network → watch the SSE request stay **open** and receive events over time.
5. **Experiment:**
   - Change the token delay in `main.py` and watch the typing speed change.
   - Add an `event:` name to the clock stream and listen for it specifically with `addEventListener` in a small client.
6. **Bonus:** Add a `/progress` SSE endpoint that streams `data: {"percent": n}` from 0 to 100 and render it as a progress bar in a tiny HTML client.

---

## 14. Common Mistakes

| Mistake | Fix |
|---|---|
| Missing the blank line after each SSE message | End every message with `\n\n`. |
| Wrong media type | Use `text/event-stream` for SSE. |
| Returning a full list instead of a generator | Pass a generator so chunks flush incrementally. |
| Blocking generator on the event loop | Use an async generator with `await` between yields. |
| Using WebSockets for one-way streaming | Prefer SSE — simpler and auto-reconnecting. |
| No completion signal | Send a sentinel (`[DONE]`) so the client can close. |
| Proxy buffering hides the stream | Disable buffering with the right headers. |

---

## 15. Key Takeaways

- **`StreamingResponse`** sends a response body in **pieces** from a generator — low memory, immediate first byte.
- **SSE** is one-way server→client streaming over plain HTTP with `media_type="text/event-stream"`.
- SSE messages are `data: ...` lines ending in a **blank line (`\n\n`)**; optional `event:`, `id:`, `retry:`.
- Browsers consume SSE with the built-in **`EventSource`**, which **auto-reconnects**.
- **SSE vs WebSockets:** one-way + simple + auto-reconnect (SSE) vs two-way + binary (WebSockets). Use SSE when the client only receives.
- **LLM token streaming** is the flagship use case: flush each token as an SSE event for the "typing" effect.
- `StreamingResponse` also streams **large files/exports** without loading them fully into memory.
- Use **async generators**, end messages with `\n\n`, send a completion sentinel, and disable proxy buffering.

---

## ➡️ Next Lesson

**Lesson 33 — CORS (Cross-Origin Resource Sharing)**
- Why browsers block cross-origin requests
- `CORSMiddleware` configuration for frontend integration
- Allowed origins, methods, headers, and credentials
