# Lesson 58 — gRPC alongside FastAPI

> **Goal of this lesson:** Learn **gRPC** — a fast, typed, binary RPC framework — and when to use it **alongside** FastAPI. Understand **Protocol Buffers** (`.proto` service/message definitions), how gRPC differs from REST, its **streaming** modes, and the pragmatic split: **REST for public/browser-facing APIs, gRPC for high-performance internal service-to-service calls.**
>
> `main.py` is a real, runnable gRPC service — a `.proto` compiled to Python code, a gRPC **server**, and a **client** that calls it (unary and server-streaming), all verified end to end.

---

## 1. What Is gRPC?

**gRPC** (gRPC Remote Procedure Call, by Google) lets one program **call a function on another** over the network as if it were local. Instead of "GET this URL," you call `stub.GetUser(request)` and get a typed response back — a **remote procedure call**.

Under the hood it's built for **speed and type-safety**:

- **Protocol Buffers** — a compact **binary** serialization format (far smaller/faster than JSON).
- **HTTP/2** — multiplexed, bidirectional, efficient (vs REST's typical HTTP/1.1).
- **Strongly typed contract** — you define services and messages in a `.proto` file; code is **generated** for client and server in many languages.
- **Streaming** — first-class support for streaming requests and/or responses.

> 🔑 gRPC is **typed, binary, HTTP/2 RPC**: you call remote methods like local functions, with a generated, strongly-typed contract. It trades REST's simplicity and universality for **performance and type-safety** — ideal for internal service-to-service calls.

---

## 2. Protocol Buffers — The Contract

Everything starts with a **`.proto`** file: the schema defining your **messages** (data shapes) and **services** (the callable methods). It's the single source of truth for both client and server.

```proto
syntax = "proto3";

// Messages = the request/response data shapes (like Pydantic models).
message GetUserRequest {
  int32 user_id = 1;            // field number (wire identity), NOT a default
}
message UserReply {
  int32 id = 1;
  string name = 2;
  string email = 3;
}

// A service = a group of callable RPC methods.
service UserService {
  rpc GetUser (GetUserRequest) returns (UserReply);           // unary
  rpc ListUsers (Empty) returns (stream UserReply);           // server streaming
}
```

- **Fields have numbers** (`= 1`, `= 2`) — these identify fields on the wire, enabling forward/backward compatibility (add fields with new numbers without breaking old clients).
- **`service` + `rpc`** define the callable methods and their request/response types.

You then **compile** the `.proto` with `protoc` (via `grpcio-tools`) into generated Python (`*_pb2.py` for messages, `*_pb2_grpc.py` for the service stubs):

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. user.proto
```

> 🔑 The **`.proto`** file is the contract: define **messages** and **services**, compile with `protoc` to generate typed client/server code. Field numbers give schema evolution — add fields without breaking existing clients.

---

## 3. gRPC vs REST

They solve overlapping problems differently:

| | **REST (FastAPI)** | **gRPC** |
|---|---|---|
| Format | JSON (text, human-readable) | Protocol Buffers (binary, compact) |
| Transport | HTTP/1.1 (usually) | HTTP/2 (multiplexed) |
| Contract | OpenAPI (optional, generated) | `.proto` (required, first-class) |
| Style | Resources + verbs (GET/POST) | Method calls (`GetUser()`) |
| Browser support | Native | **No** (needs gRPC-Web + a proxy) |
| Streaming | SSE/WebSockets (bolt-on) | Built-in (4 modes) |
| Performance | Good | **Higher** (binary + HTTP/2) |
| Human-debuggable | Easy (curl, browser) | Harder (binary) |
| Best for | Public APIs, browsers, simplicity | Internal microservice calls, high throughput, polyglot |

> 🔑 REST is **universal, human-friendly, browser-native** — best for public APIs. gRPC is **faster, typed, streaming-first** — best for **internal** service-to-service calls where both ends are yours. Neither replaces the other.

---

## 4. The Four RPC Types

gRPC's streaming support is a standout feature. A method is one of four kinds:

| Type | Request → Response | Example |
|---|---|---|
| **Unary** | one → one | `GetUser(id)` → user (a normal call) |
| **Server streaming** | one → many | `ListUsers()` → a stream of users |
| **Client streaming** | many → one | `UploadMetrics(stream)` → a summary |
| **Bidirectional** | many ↔ many | `Chat(stream)` ↔ `stream` (real-time both ways) |

```proto
rpc GetUser (Req) returns (Reply);              // unary
rpc ListUsers (Req) returns (stream Reply);     // server streaming
rpc Upload (stream Req) returns (Reply);        // client streaming
rpc Chat (stream Req) returns (stream Reply);   // bidirectional
```

Streaming is native and efficient over HTTP/2 — no SSE/WebSocket workarounds. `main.py` demonstrates unary (`GetUser`) and server streaming (`ListUsers`).

> 🔑 gRPC has **four call types** — unary, server-streaming, client-streaming, and bidirectional — all first-class over HTTP/2. Streaming that's awkward in REST is built-in here.

---

## 5. Server and Client (Python)

From the generated code you implement a **server** (subclass the generated servicer) and use a **stub** on the **client**:

```python
# SERVER: implement the service methods
class UserServicer(user_pb2_grpc.UserServiceServicer):
    def GetUser(self, request, context):
        # request.user_id is typed; return a typed reply
        return user_pb2.UserReply(id=1, name="Ada", email="ada@example.com")

server = grpc.server(...)
user_pb2_grpc.add_UserServiceServicer_to_server(UserServicer(), server)
server.add_insecure_port("[::]:50051")   # gRPC default-ish port
server.start()

# CLIENT: call methods through a stub
channel = grpc.insecure_channel("localhost:50051")
stub = user_pb2_grpc.UserServiceStub(channel)
reply = stub.GetUser(user_pb2.GetUserRequest(user_id=1))   # feels like a local call
print(reply.name)   # "Ada"
```

The client calls `stub.GetUser(...)` and gets a typed object — the network, serialization, and HTTP/2 are invisible. That's the RPC illusion: remote calls that look local.

> 🔑 Implement a **servicer** (the methods) on the server; call through a generated **stub** on the client. Both sides share the compiled `.proto` types, so the call is fully typed end to end.

---

## 6. gRPC *Alongside* FastAPI

The key architectural point: gRPC and FastAPI **coexist**, each doing what it's best at.

```
                    ┌─── FastAPI (REST/JSON) ───► browsers, mobile, public clients
Your system:  ──────┤
                    └─── gRPC (Protobuf/HTTP2) ──► other internal services
```

A common pattern: **FastAPI is the public-facing edge** (REST, browser-friendly, great docs), and **internally your services talk gRPC** for speed and type-safety. A FastAPI endpoint might receive a REST request, then call several backend services over **gRPC**, and return JSON to the client.

```python
@app.get("/users/{user_id}")           # public REST endpoint (FastAPI)
def get_user(user_id: int):
    reply = grpc_stub.GetUser(GetUserRequest(user_id=user_id))   # internal gRPC call
    return {"id": reply.id, "name": reply.name}                  # JSON to the client
```

> 🔑 Use **FastAPI (REST) at the public edge** for browsers/clients and **gRPC internally** between your services. A FastAPI endpoint fronting gRPC backends gives you the best of both — public friendliness *and* internal performance/typing.

---

## 7. When to Use gRPC (and When Not)

**Reach for gRPC when:**
- **Internal service-to-service** communication where you control both ends.
- **High throughput / low latency** matters (binary + HTTP/2 beats JSON/HTTP1.1).
- **Streaming** is needed (real-time, large data sets).
- **Polyglot** services — one `.proto` generates clients in Go, Java, Python, etc.
- You want a **strict, versioned contract** enforced by codegen.

**Stick with REST (FastAPI) when:**
- The API is **public** or consumed by **browsers** (gRPC isn't browser-native).
- **Simplicity and debuggability** matter (curl, human-readable JSON).
- Broad ecosystem/tooling and easy caching are priorities.

> 🔑 **gRPC for internal, high-performance, typed, streaming service calls; REST for public, browser-facing, human-debuggable APIs.** Most real systems use **both** — REST at the edge, gRPC in the core.

---

## 8. Trade-offs to Know

gRPC's power has costs:

- **Not browser-native** — needs **gRPC-Web** and a proxy (Envoy) for browsers.
- **Binary = harder to debug** — you can't just `curl` it and read the response.
- **Codegen step** — you must compile `.proto` files (a build step) and regenerate on changes.
- **Steeper learning curve** — proto syntax, streaming, and the toolchain.
- **Less ubiquitous tooling** — REST's ecosystem (caching, gateways, docs) is broader.

> 💡 gRPC adds a build step and reduced debuggability in exchange for speed and type-safety. Worth it inside a service mesh; overkill for a simple public CRUD API.

---

## 9. Real-World Use Case — Edge REST, Internal gRPC

Your auction platform serves a web/mobile frontend and has several backend services (Users, Bids, Payments):

- **FastAPI** is the public **API gateway**: browsers and the mobile app hit REST/JSON endpoints with great docs and easy debugging.
- Internally, when a REST request needs data, FastAPI calls the **Users** and **Bids** services over **gRPC** — binary, typed, fast, and streaming the live bid feed via server-streaming.
- The services are written in different languages (Bids in Go, Users in Python), but all share the same `.proto` contracts, so their generated clients interoperate perfectly.
- Public clients never see gRPC; internal calls never pay the JSON tax.

Public simplicity at the edge, internal performance in the core — the standard, pragmatic architecture that `main.py` demonstrates in miniature.

---

## 10. Mini Task

`main.py` includes a `.proto`, generates the code, runs a gRPC server, and calls it.

1. Install: `pip install grpcio grpcio-tools`.
2. Generate the code (done automatically by `main.py`, or manually):
   ```bash
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. user.proto
   ```
3. Run: `python main.py` → it starts a gRPC server, then a client makes a **unary** call (`GetUser`) and a **server-streaming** call (`ListUsers`), printing the typed replies.
4. Read the `.proto`: note the messages, the `service`, the field numbers, and `stream` on `ListUsers`.
5. **Experiment:**
   - Add a `CreateUser` unary RPC to the `.proto`, regenerate, and implement it.
   - Change `ListUsers` to filter by a field in the request.
   - Add a FastAPI endpoint that calls the gRPC server and returns JSON (the edge-REST/internal-gRPC pattern).
6. **Bonus:** Add a client-streaming or bidirectional RPC and observe the streaming semantics.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Exposing gRPC directly to browsers | Browsers need gRPC-Web + a proxy; use REST at the edge. |
| Using gRPC for a simple public CRUD API | REST is simpler and universal; save gRPC for internal calls. |
| Forgetting to regenerate after editing `.proto` | Re-run `protoc`; stale generated code breaks. |
| Reusing/renumbering proto field numbers | Field numbers are permanent identities — never reuse them. |
| Expecting easy `curl` debugging | gRPC is binary; use `grpcurl`/reflection tools. |
| gRPC where JSON simplicity matters more | The perf gain may not justify the complexity. |
| No contract versioning discipline | Evolve `.proto` additively (new field numbers). |

---

## 12. Key Takeaways

- **gRPC** = typed, binary, HTTP/2 **RPC**: call remote methods like local functions, with a generated strongly-typed contract.
- **Protocol Buffers** (`.proto`) define **messages** and **services**; `protoc` generates client/server code. **Field numbers** enable additive schema evolution.
- **gRPC vs REST**: gRPC is faster, typed, streaming-first, but not browser-native and harder to debug; REST is universal, human-friendly, browser-native.
- gRPC has **four call types**: unary, server/client streaming, and bidirectional — all first-class over HTTP/2.
- Implement a **servicer** on the server, call via a **stub** on the client; both share the compiled types.
- **Use them together**: **REST (FastAPI) at the public edge, gRPC internally** between services.
- Choose **gRPC for internal, high-performance, typed, streaming, polyglot** calls; **REST for public, browser-facing, debuggable** APIs.

---

## ➡️ Next Lesson

**Lesson 59 — LLM/AI API Patterns**
- Streaming responses token-by-token
- Rate limiting per user/token and cost control
- Common patterns for AI-powered API endpoints
