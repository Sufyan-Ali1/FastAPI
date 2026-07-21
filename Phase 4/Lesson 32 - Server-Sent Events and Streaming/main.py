"""
Lesson 32 - Server-Sent Events (SSE) & Streaming Responses
----------------------------------------------------------
Runnable demos of one-way, incremental server -> client streaming:

    /                     in-browser client: type a prompt, watch the answer
                          stream in token-by-token (the ChatGPT/Claude effect)
    /llm-stream           SSE endpoint that streams a simulated LLM response
    /sse/clock            SSE endpoint that pushes the time a few times
    /stream-text          plain StreamingResponse (chunked text)
    /download/report.csv  StreamingResponse as a streamed CSV file download

No extra installs - StreamingResponse is built into FastAPI.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Then open http://127.0.0.1:8000/ and send a prompt.
"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI(title="Lesson 32 - SSE & Streaming")

# Recommended headers so proxies (e.g. nginx) don't buffer the stream.
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

TOKEN_DELAY = 0.05  # seconds between "tokens" - tune to change typing speed


# A canned "LLM" answer. In a real app these tokens come from your LLM
# provider's streaming API; the FastAPI-side SSE wrapping is identical.
def fake_llm_tokens(prompt: str):
    answer = (
        f"You asked: '{prompt}'. Here is a streamed reply. Server-Sent Events "
        f"let the server push each token as soon as it is ready, so the client "
        f"renders text progressively instead of waiting for the whole response."
    )
    for word in answer.split(" "):
        yield word + " "


# ---------------------------------------------------------------------------
# LLM-STYLE SSE STREAM - the headline use case
# ---------------------------------------------------------------------------
async def llm_event_stream(prompt: str):
    for token in fake_llm_tokens(prompt):
        # Each SSE message: "data: <payload>\n\n"  (the blank line is required!)
        yield f"data: {json.dumps({'token': token})}\n\n"
        await asyncio.sleep(TOKEN_DELAY)  # await -> does not block the event loop
    yield "data: [DONE]\n\n"  # completion sentinel so the client can close


@app.get("/llm-stream")
async def llm_stream(prompt: str = "Explain SSE"):
    return StreamingResponse(
        llm_event_stream(prompt),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


# ---------------------------------------------------------------------------
# CLOCK SSE STREAM - pushes the server time a few times
# ---------------------------------------------------------------------------
async def clock_stream(ticks: int):
    for _ in range(ticks):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        yield f"data: {now}\n\n"
        await asyncio.sleep(1)
    yield "data: [DONE]\n\n"


@app.get("/sse/clock")
async def sse_clock(ticks: int = 5):
    return StreamingResponse(
        clock_stream(ticks), media_type="text/event-stream", headers=SSE_HEADERS
    )


# ---------------------------------------------------------------------------
# PLAIN STREAMING (not SSE) - chunked text
# ---------------------------------------------------------------------------
async def text_chunks():
    for i in range(1, 6):
        yield f"chunk {i}\n"
        await asyncio.sleep(0.1)


@app.get("/stream-text")
async def stream_text():
    return StreamingResponse(text_chunks(), media_type="text/plain")


# ---------------------------------------------------------------------------
# STREAMED FILE DOWNLOAD - generate a CSV row-by-row without buffering it all
# ---------------------------------------------------------------------------
def csv_rows(count: int):
    yield "id,name,price\n"
    for i in range(1, count + 1):
        yield f"{i},item-{i},{i * 1.5:.2f}\n"


@app.get("/download/report.csv")
def download_csv(count: int = 100):
    return StreamingResponse(
        csv_rows(count),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=report.csv"},
    )


# ---------------------------------------------------------------------------
# IN-BROWSER CLIENT - EventSource consuming the LLM SSE stream
# ---------------------------------------------------------------------------
PAGE = """
<!doctype html>
<html>
<head><title>Lesson 32 - SSE Streaming</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 680px; margin: 2rem auto; }
  #out { border: 1px solid #ccc; min-height: 160px; padding: 12px; border-radius: 6px;
         background: #fafafa; white-space: pre-wrap; line-height: 1.5; }
  form { display: flex; gap: 8px; margin-bottom: 12px; }
  input { flex: 1; padding: 8px; } button { padding: 8px 16px; }
  .cursor { animation: blink 1s step-end infinite; }
  @keyframes blink { 50% { opacity: 0; } }
</style></head>
<body>
  <h2>SSE Token Streaming (simulated LLM)</h2>
  <form id="form">
    <input id="prompt" type="text" value="Explain server-sent events" />
    <button>Send</button>
  </form>
  <div id="out"></div>
<script>
  const form = document.getElementById("form");
  const out = document.getElementById("out");
  let source = null;

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (source) source.close();
    out.textContent = "";
    const prompt = document.getElementById("prompt").value;
    source = new EventSource("/llm-stream?prompt=" + encodeURIComponent(prompt));
    source.onmessage = (ev) => {
      if (ev.data === "[DONE]") { source.close(); return; }
      const { token } = JSON.parse(ev.data);
      out.textContent += token;      // append each token -> "typing" effect
    };
    source.onerror = () => { source.close(); };
  });
</script>
</body>
</html>
"""


@app.get("/")
def client():
    return HTMLResponse(PAGE)
