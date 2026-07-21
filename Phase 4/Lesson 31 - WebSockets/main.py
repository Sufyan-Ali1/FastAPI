"""
Lesson 31 - WebSockets
----------------------
A runnable multi-user chat over WebSockets, demonstrating:

    - a WebSocket endpoint (@app.websocket) with accept / receive / send
    - the Connection Manager pattern (track all active connections)
    - broadcasting a message to every connected client
    - clean disconnect handling (WebSocketDisconnect)
    - a raw echo socket for testing

It also serves a tiny in-browser chat client at "/", so you can open two tabs
and watch messages appear live in both.

No extra installs - WebSocket support is built into FastAPI/Starlette.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Then open http://127.0.0.1:8000/ in TWO browser tabs and chat.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="Lesson 31 - WebSockets")


# ===========================================================================
# THE CONNECTION MANAGER - owns the list of active connections and the
# broadcast/personal-send logic. Endpoints stay tiny by delegating to it.
# ===========================================================================
class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()          # complete the handshake
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def send_personal(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        for connection in self.active:
            await connection.send_text(message)


manager = ConnectionManager()


# ===========================================================================
# ECHO WEBSOCKET - the simplest possible socket, for testing.
# NOTE: this static route MUST be declared BEFORE the dynamic /ws/{client_id}
# route below, or "/ws/echo" would match {client_id}="echo" and be shadowed.
# (Same static-before-dynamic rule as HTTP routes - Phase 1 Lesson 4.)
# ===========================================================================
@app.websocket("/ws/echo")
async def echo(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_text(f"echo: {text}")
    except WebSocketDisconnect:
        pass


# ===========================================================================
# CHAT WEBSOCKET - connect, announce join, broadcast messages, announce leave
# ===========================================================================
@app.websocket("/ws/{client_id}")
async def chat(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)
    await manager.broadcast(f"[system] {client_id} joined "
                            f"({len(manager.active)} online)")
    try:
        while True:
            text = await websocket.receive_text()   # wait for this client's msg
            await manager.broadcast(f"{client_id}: {text}")  # send to EVERYONE
    except WebSocketDisconnect:
        manager.disconnect(websocket)               # critical cleanup
        await manager.broadcast(f"[system] {client_id} left "
                                f"({len(manager.active)} online)")


# ===========================================================================
# IN-BROWSER CHAT CLIENT (served at "/") - open two tabs to see broadcasting
# ===========================================================================
PAGE = """
<!doctype html>
<html>
<head><title>Lesson 31 - WebSocket Chat</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; }
  #log { border: 1px solid #ccc; height: 320px; overflow-y: auto; padding: 8px;
         background: #fafafa; border-radius: 6px; }
  .system { color: #888; font-style: italic; }
  form { display: flex; gap: 8px; margin-top: 8px; }
  input[type=text] { flex: 1; padding: 8px; }
  button { padding: 8px 16px; }
</style></head>
<body>
  <h2>WebSocket Chat</h2>
  <p>Your id: <b id="me"></b> — open this page in another tab to chat.</p>
  <div id="log"></div>
  <form id="form">
    <input id="msg" type="text" autocomplete="off" placeholder="Type a message..." />
    <button>Send</button>
  </form>
<script>
  const clientId = "user-" + Math.floor(Math.random() * 10000);
  document.getElementById("me").textContent = clientId;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/${clientId}`);
  const log = document.getElementById("log");

  function add(text, system) {
    const div = document.createElement("div");
    if (system) div.className = "system";
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }
  ws.onmessage = (e) => add(e.data, e.data.startsWith("[system]"));
  ws.onclose = () => add("[disconnected]", true);

  document.getElementById("form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("msg");
    if (input.value) { ws.send(input.value); input.value = ""; }
  });
</script>
</body>
</html>
"""


@app.get("/")
def client():
    return HTMLResponse(PAGE)
