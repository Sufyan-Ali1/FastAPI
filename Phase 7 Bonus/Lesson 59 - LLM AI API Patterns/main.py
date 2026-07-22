"""
Lesson 59 - LLM / AI API Patterns
---------------------------------
A SIMULATED LLM chat API (no API key needed) demonstrating the AI-specific
FastAPI patterns:

    - token-by-token SSE STREAMING (the ChatGPT/Claude "typing" effect)
    - per-user TOKEN BUDGET (rate limiting on TOKENS, not just requests) -> 429
    - usage tracking (input + output tokens consumed)

In production the fake token generator is replaced by a real provider's
streaming API (see theory.md section 3); the SSE wrapper and budget logic are
identical.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Try:
    curl -N -H "X-User-Id: alice" "http://127.0.0.1:8000/chat/stream?prompt=hello"
"""

import asyncio
import json
import time
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

app = FastAPI(title="Lesson 59 - LLM API Patterns")

TOKEN_DELAY = 0.04           # seconds between tokens (the typing speed)
DAILY_TOKEN_BUDGET = 200     # per-user token budget (small, so it's easy to hit)
BUDGET_WINDOW = 86400        # seconds (24h)


# ---------------------------------------------------------------------------
# A per-user TOKEN BUDGET - the LLM-specific rate limit. Each request debits
# the tokens it uses; when the bucket is empty, further requests get 429.
# ---------------------------------------------------------------------------
class TokenBudget:
    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self._used: dict[str, list] = {}  # user -> [(timestamp, tokens), ...]

    def _prune(self, user: str) -> None:
        cutoff = time.time() - self.window
        self._used[user] = [(t, n) for (t, n) in self._used.get(user, []) if t > cutoff]

    def used(self, user: str) -> int:
        self._prune(user)
        return sum(n for _, n in self._used.get(user, []))

    def remaining(self, user: str) -> int:
        return max(0, self.limit - self.used(user))

    def debit(self, user: str, tokens: int) -> None:
        self._used.setdefault(user, []).append((time.time(), tokens))

    def seconds_until_reset(self, user: str) -> int:
        self._prune(user)
        entries = self._used.get(user, [])
        if not entries:
            return 0
        oldest = min(t for t, _ in entries)
        return max(1, int(oldest + self.window - time.time()))


budget = TokenBudget(DAILY_TOKEN_BUDGET, BUDGET_WINDOW)


# ---------------------------------------------------------------------------
# The "LLM" - a fake generator. Its token count feeds cost/budget accounting.
# In production this is a real provider stream (theory.md section 3).
# ---------------------------------------------------------------------------
def fake_completion_tokens(prompt: str) -> list[str]:
    reply = (
        f"Here is a streamed reply to '{prompt}'. Each token arrives as its own "
        f"SSE event, so the client renders the answer progressively instead of "
        f"waiting for the whole thing."
    )
    return [w + " " for w in reply.split(" ")]


def estimate_input_tokens(prompt: str) -> int:
    # A rough word-based estimate for the demo. A real app uses the provider's
    # count_tokens (NOT a foreign tokenizer) - see theory.md section 4.
    return max(1, len(prompt.split()))


def get_user(x_user_id: Annotated[str | None, Header()] = None) -> str:
    if not x_user_id:
        raise HTTPException(401, "Missing X-User-Id header")
    return x_user_id


# ---------------------------------------------------------------------------
# STREAMING chat endpoint with a per-user token budget.
# ---------------------------------------------------------------------------
@app.get("/chat/stream")
async def chat_stream(
    prompt: Annotated[str, Query(min_length=1, max_length=1000)],
    x_user_id: Annotated[str | None, Header()] = None,
):
    user = get_user(x_user_id)

    # Estimate the cost (input + expected output tokens) and enforce the budget
    # BEFORE streaming, so we never start a stream we can't afford.
    input_tokens = estimate_input_tokens(prompt)
    output_tokens = len(fake_completion_tokens(prompt))
    needed = input_tokens + output_tokens

    if needed > budget.remaining(user):
        raise HTTPException(
            status_code=429,
            detail=f"Token budget exceeded ({budget.remaining(user)} left, {needed} needed)",
            headers={"Retry-After": str(budget.seconds_until_reset(user))},
        )

    async def event_stream():
        produced = 0
        for token in fake_completion_tokens(prompt):
            yield f"data: {json.dumps({'token': token})}\n\n"
            produced += 1
            await asyncio.sleep(TOKEN_DELAY)
        # Debit the ACTUAL tokens used (input + produced output) once done.
        budget.debit(user, input_tokens + produced)
        yield f"data: {json.dumps({'done': True, 'input_tokens': input_tokens, 'output_tokens': produced})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/usage")
def usage(x_user_id: Annotated[str | None, Header()] = None):
    user = get_user(x_user_id)
    return {
        "user": user,
        "tokens_used": budget.used(user),
        "tokens_remaining": budget.remaining(user),
        "daily_limit": DAILY_TOKEN_BUDGET,
    }


@app.get("/")
def root():
    return {"message": "LLM API patterns demo. Stream at /chat/stream, check /usage."}
