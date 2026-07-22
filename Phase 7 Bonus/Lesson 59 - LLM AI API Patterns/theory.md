# Lesson 59 — LLM / AI API Patterns

> **Goal of this lesson:** Build FastAPI endpoints that front an **LLM** well. Learn **token-by-token streaming** (the ChatGPT/Claude "typing" UX), **token-based cost and counting**, and **rate limiting per user *and* per token/budget** — the patterns every AI-powered API needs. Ties together SSE streaming (Lesson 32) and rate limiting (Lesson 34).
>
> `main.py` runs a **simulated** LLM chat API (no API key needed): SSE token streaming, per-user token budgets, and usage tracking. A short, accurate snippet shows how to wire a real provider stream in.

---

## 1. What Makes LLM APIs Different

An LLM endpoint isn't a normal CRUD route. Four properties shape every design decision:

| Property | Consequence |
|---|---|
| **Slow** | A full response can take many seconds → **stream** it, don't block. |
| **Token-priced** | Cost = input tokens + output tokens → **count and budget** tokens, not just requests. |
| **Variable cost per call** | A long prompt costs far more than a short one → per-request cost isn't constant. |
| **Non-deterministic** | Same input → different output → caching and testing need care. |

These flip the usual assumptions (fast, flat-cost, deterministic), so AI endpoints get their own patterns.

> 🔑 LLM calls are **slow, token-priced, and non-deterministic.** Design for streaming, token accounting, and per-user cost control — not the flat request/response model of ordinary endpoints.

---

## 2. Token-by-Token Streaming — The Core UX

Waiting 8 seconds for a full answer feels broken. Streaming each **token** as the model produces it makes the reply appear progressively — perceived latency drops from seconds to ~200ms even though total time is unchanged. This is exactly the SSE pattern from Lesson 32.

```
Without streaming:  [ 8s spinner ] → whole answer appears
With streaming:     t→ok → answer → appears → word → by → word (feels instant)
```

The FastAPI side is a `StreamingResponse` over an async generator that yields tokens as SSE events:

```python
async def token_stream(prompt: str):
    async for token in produce_tokens(prompt):     # from your model
        yield f"data: {json.dumps({'token': token})}\n\n"
    yield "data: [DONE]\n\n"                        # completion sentinel

@app.get("/chat/stream")
async def chat(prompt: str):
    return StreamingResponse(token_stream(prompt), media_type="text/event-stream")
```

> 🔑 Stream LLM output **token-by-token over SSE** (Lesson 32). Flush each token immediately for the "typing" effect, and send a `[DONE]` sentinel so the client knows the stream ended.

---

## 3. Wiring a Real Provider Stream

`main.py` uses a fake token generator so it runs with no API key. In production, the generator wraps your LLM provider's **streaming** API — the FastAPI plumbing is identical. Using Anthropic's Claude API (the current SDK) it looks like this:

```python
from anthropic import AsyncAnthropic
client = AsyncAnthropic()   # reads ANTHROPIC_API_KEY from the environment

async def token_stream(prompt: str):
    async with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:          # tokens as they arrive
            yield f"data: {json.dumps({'token': text})}\n\n"
        final = await stream.get_final_message()        # usage/token counts
        yield f"data: {json.dumps({'done': True, 'output_tokens': final.usage.output_tokens})}\n\n"
```

- **`messages.stream(...)`** with `async for text in stream.text_stream` yields tokens; **default to streaming** for LLM calls so a long generation doesn't hit an HTTP timeout.
- **`get_final_message()`** gives the complete message plus **`usage`** (real input/output token counts) — which you use for budgeting (§4).
- Each provider exposes an equivalent streaming call; the FastAPI `StreamingResponse` wrapper doesn't change.

> 💡 Your FastAPI endpoint is a **thin async pass-through**: read the provider's token stream and re-emit it as SSE. Keep the endpoint `async def` and `await`/`async for` the provider (Lesson 28) so one worker can hold many concurrent chat streams.

---

## 4. Token Counting & Cost

LLM pricing is **per token**, split into cheaper **input** (the prompt) and pricier **output** (the completion). So:

- Cost of a request = `input_tokens × input_price + output_tokens × output_price`.
- A request with a huge prompt or long answer costs far more than a short one — **per-request cost is not flat.**
- You must **count tokens** to budget, meter, and bill.

Count tokens with the **provider's tokenizer**, not a generic one:

```python
# Count BEFORE sending, to enforce a budget or estimate cost (Claude API):
count = client.messages.count_tokens(model="claude-opus-4-8", messages=messages)
estimated_input_tokens = count.input_tokens
# Actual output tokens come back on the response's `usage` after generation.
```

> ⚠️ Don't estimate token counts with a different provider's tokenizer (e.g. `tiktoken` for a non-OpenAI model) — it can be off by 15–30%, breaking your budgets and cost math. Use the model's own `count_tokens`, and read real usage off the response.

> 🔑 LLM cost is **per token (input + output)** and varies per request. **Count tokens** with the provider's tokenizer to budget and bill, and read the real `usage` off each response for accurate accounting.

---

## 5. Rate Limiting — Per User *and* Per Token

Ordinary rate limiting (Lesson 34) caps **requests per minute**. LLM APIs need more, because a single request can be arbitrarily expensive:

| Limit dimension | Caps | Why |
|---|---|---|
| **Requests / minute** (per user) | Burst/abuse | Standard throttling (Lesson 34) |
| **Tokens / day** (per user) | **Cost** | One user can't run up an unbounded bill |
| **Concurrent streams** (per user) | Resource use | Prevent one user opening 100 streams |
| **Tokens / request** (`max_tokens`) | Runaway outputs | Cap a single generation's length |

The key addition is a **token budget/quota per user** — a bucket of tokens each user may spend over a window. Every request debits the tokens it used; when the bucket is empty, further requests get **`429`** until it refills.

```python
def check_token_budget(user_id: str, tokens_needed: int):
    remaining = budget.remaining(user_id)
    if tokens_needed > remaining:
        raise HTTPException(429, "Token budget exceeded",
                            headers={"Retry-After": str(budget.seconds_until_reset(user_id))})
    budget.debit(user_id, tokens_needed)
```

> 🔑 For LLM APIs, rate-limit on **tokens**, not just requests — a per-user **token budget** is what actually controls cost. Combine it with request-rate limits, a per-user concurrent-stream cap, and a per-request `max_tokens` ceiling.

---

## 6. Conversation State

The Messages API (like most LLM APIs) is **stateless** — the model remembers nothing between calls. To hold a conversation, **you** send the **full message history** every turn:

```python
messages = [
    {"role": "user", "content": "My name is Ada."},
    {"role": "assistant", "content": "Nice to meet you, Ada!"},
    {"role": "user", "content": "What's my name?"},   # model needs the history to answer
]
```

Your FastAPI app stores the conversation (in a DB — Phase 3) and rebuilds the `messages` list on each request. Note: **history grows the input token count every turn**, which feeds directly into your cost and budget math (§4–5). Long conversations get expensive; techniques like summarizing/truncating old turns keep them bounded.

> 🔑 LLM APIs are **stateless** — resend the full conversation history each turn. That history grows input tokens (and cost) every message, so budget for it and prune long conversations.

---

## 7. Other Essential AI Patterns

Beyond streaming, tokens, and limits:

- **Timeouts** — LLM calls can hang; set a client timeout and handle it (an `async def` endpoint shouldn't wait forever).
- **Retries with backoff** — providers return `429`/`529` under load; retry transient failures (SDKs often do this for you).
- **Caching** — cache identical, deterministic requests (or use the provider's prompt caching to cut input cost on repeated context). Be careful: LLM output is non-deterministic, so cache deliberately.
- **Cost guards** — hard caps: max prompt length, `max_tokens` per request, a global daily spend limit.
- **Moderation / guardrails** — validate/filter user input and model output where the domain requires it.
- **Graceful errors** — surface provider errors (rate limit, content refusal) as clean API responses, not 500s.

> 🔑 Production AI endpoints add **timeouts, retries, caching, cost guards, and guardrails** on top of streaming and token budgets. These turn a demo into something safe to expose to real users and real bills.

---

## 8. Real-World Use Case — A Chat API Endpoint

Your app offers an AI assistant to logged-in users. The `POST /chat` (streaming) endpoint:

- Requires a valid JWT (Lesson 29); the **user id** keys the token budget.
- Loads the conversation history from the database (Phase 3) and appends the new user message.
- Checks the user's **token budget** (§5) and **request-rate limit** (Lesson 34) → `429` if exceeded, with `Retry-After`.
- Streams the model's tokens back over **SSE** (§2–3) so the UI types the answer out live.
- On completion, **debits** the real `usage.output_tokens` from the budget, persists the assistant turn, and records usage for billing.
- Caps `max_tokens`, sets a timeout, and returns clean errors on provider failures.

That single endpoint combines auth, database state, SSE streaming, token accounting, and per-user cost control — the full stack of this course applied to AI. `main.py` demonstrates the AI-specific core of it.

---

## 9. Mini Task

`main.py` is a simulated LLM chat API (no API key needed).

1. Install: `pip install fastapi uvicorn`
2. Run: `uvicorn main:app --reload`.
3. Stream a completion (per-user via `X-User-Id`):
   ```bash
   curl -N -H "X-User-Id: alice" "http://127.0.0.1:8000/chat/stream?prompt=hello"
   ```
   Watch the tokens arrive one at a time, then `[DONE]`.
4. Check your usage: `GET /usage` (with the same `X-User-Id`) → tokens consumed.
5. **Exhaust the budget:** send several long prompts until you get a **`429`** with `Retry-After` — the per-user token budget in action.
6. **Experiment:**
   - Lower the daily token budget and watch it trip sooner.
   - Add a per-request `max_tokens` cap and reject prompts that would exceed it.
   - Add a second user (`X-User-Id: bob`) and confirm budgets are independent.
7. **Bonus:** Replace the fake token generator with a real provider stream (see §3), keeping the SSE wrapper and budget logic unchanged.

---

## 10. Common Mistakes

| Mistake | Fix |
|---|---|
| Blocking on the full LLM response | Stream token-by-token over SSE. |
| Rate limiting only by requests/minute | Add a per-user **token budget** — cost scales with tokens. |
| Estimating tokens with the wrong tokenizer | Use the provider's `count_tokens`; read real `usage` off responses. |
| Forgetting per-request `max_tokens` | Cap output length to avoid runaway cost. |
| Losing conversation context | Resend the full history each turn (the API is stateless). |
| No timeout on the LLM call | Set one; don't let an `async` endpoint hang forever. |
| Caching non-deterministic output blindly | Cache deliberately (or use provider prompt caching for input). |

---

## 11. Key Takeaways

- LLM APIs are **slow, token-priced, and non-deterministic** — design around streaming, token accounting, and cost control.
- **Stream token-by-token over SSE** (Lesson 32) for the "typing" UX; send a `[DONE]` sentinel.
- Your FastAPI endpoint is a **thin async pass-through** wrapping the provider's stream in a `StreamingResponse`.
- Cost is **per token (input + output)** and varies per request — **count tokens** with the provider's tokenizer and read real `usage`.
- Rate-limit on **tokens**, not just requests: a **per-user token budget** controls cost, plus request-rate limits, concurrent-stream caps, and per-request `max_tokens`.
- LLM APIs are **stateless** — resend full history each turn; that history grows input tokens (and cost).
- Add **timeouts, retries, caching, cost guards, and guardrails** for production AI endpoints.

---

## ➡️ Next Lesson

**Lesson 60 — Final Capstone Project**
- Combine everything: a production-grade FastAPI application end to end
- Database + auth + real-time + testing + deployment
- The culmination of the entire course
