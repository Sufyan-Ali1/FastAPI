# Lesson 1 — What is FastAPI?

> **Goal of this lesson:** Understand what FastAPI is, why it exists, and how it works at a high level — before writing serious code.

---

## 1. What is FastAPI?

FastAPI is a **modern Python web framework** for building **APIs** (HTTP services).

It is built on top of two well-known libraries:

| Layer | Library | Job |
|-------|---------|-----|
| Web layer | **Starlette** | Routing, requests, responses, async support |
| Data layer | **Pydantic** | Data validation, parsing, serialization |

In short:
> FastAPI = Starlette (speed + async) + Pydantic (types + validation) + auto-generated docs.

---

## 2. Why does FastAPI exist?

Before FastAPI, Python developers had two main options:

### ❌ Flask
- Easy to start with
- But: no built-in validation, no async support, no auto-generated docs
- You had to manually write Swagger/OpenAPI specs

### ❌ Django REST Framework (DRF)
- Powerful and feature-rich
- But: heavy, lots of boilerplate, slower
- Tied to Django's ecosystem

Developers wanted a framework that was:

1. ⚡ **Fast** — comparable to Node.js / Go
2. 🧠 **Type-safe** — catch bugs *before* they hit production
3. 📜 **Auto-documented** — no manual Swagger writing
4. 🔄 **Async by default** — handle thousands of concurrent requests

**FastAPI solved all four problems at once** — and that's why it became the most loved Python web framework in just a few years.

---

## 3. How FastAPI works internally (simple view)

When a request hits your FastAPI app, here is what happens:

```
Client (Browser / Mobile App / curl)
        │
        │  HTTP Request
        ▼
   Uvicorn (ASGI Server)
        │
        ▼
   FastAPI Application
        │
        ▼
   Starlette Router  ──►  matches URL to a Python function
        │
        ▼
   Pydantic           ──►  validates incoming JSON / query / path data
        │
        ▼
   Your Python Function   ──►  runs your business logic
        │
        ▼
   Pydantic           ──►  serializes response back to JSON
        │
        ▼
   HTTP Response back to Client
```

### The "magic" of FastAPI: one type hint = three jobs

```python
def get_user(user_id: int):
    ...
```

That single `int` type hint:
1. **Validates** that `user_id` is actually an integer
2. **Generates Swagger docs** showing `user_id` as integer
3. **Serializes** values correctly when returning data

You write the type once — FastAPI uses it everywhere.

---

## 4. Real-World Use Cases

FastAPI is used in production by:

- **Netflix** — internal ML & data tools
- **Uber** — microservices
- **Microsoft** — ML APIs
- **Most AI startups** — because it's perfect for serving ML models

Typical projects you can build:

| Project Type | Example |
|--------------|---------|
| 🛒 E-commerce backend | Products, cart, orders APIs |
| 🤖 ML model serving | `/predict` endpoint that loads a model once |
| 💬 Real-time apps | Chat, notifications via WebSockets |
| 🔐 Auth service | JWT, OAuth login APIs |
| 📱 Mobile app backend | Clean JSON APIs for iOS / Android |

---

## 5. Mini Task

Inside this lesson folder, open `main.py` and run it:

```bash
uvicorn main:app --reload
```

Then visit:

| URL | What you'll see |
|-----|-----------------|
| `http://127.0.0.1:8000/` | `{"message": "Hello, FastAPI!"}` |
| `http://127.0.0.1:8000/about` | `{"name": "...", "role": "FastAPI Learner"}` |
| `http://127.0.0.1:8000/docs` | **Swagger UI** — auto-generated docs |
| `http://127.0.0.1:8000/redoc` | **ReDoc** — alternative docs |

✅ Try editing the messages, save the file, and see how the server auto-reloads.

---

## 6. Key Takeaways

- FastAPI is **Starlette + Pydantic + auto-docs**.
- **Type hints** are the heart of the framework.
- It's **fast, async, type-safe, and self-documenting**.
- Used everywhere from startups to FAANG companies — especially for **AI/ML APIs**.

---

## ➡️ Next Lesson

**Lesson 2 — Installation & Project Setup**
- Virtual environments
- Installing FastAPI + Uvicorn
- Setting up a clean project folder
