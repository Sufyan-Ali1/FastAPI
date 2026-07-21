# Lesson 39 — GraphQL with FastAPI *(optional, via Strawberry)*

> **Goal of this lesson:** Understand **GraphQL** as an alternative to REST, how it differs (one endpoint, client-chosen fields, a typed schema), and how to add a GraphQL API to FastAPI with **Strawberry** — types, queries, mutations, and resolvers. Then, honestly: **when GraphQL is worth it and when REST is still the better choice.**
>
> This is an **optional** lesson. `main.py` mounts a real GraphQL endpoint at `/graphql` (with an interactive explorer) alongside normal REST routes.

---

## 1. What Is GraphQL?

**GraphQL** is a **query language for APIs**: instead of many REST endpoints each returning a fixed shape, you expose **one endpoint** and the **client asks for exactly the fields it wants** in a single request.

```graphql
# The client sends a query describing precisely what it needs:
query {
  book(id: 1) {
    title
    author { name }        # follow a relationship in the same request
  }
}
```

```json
// The server returns exactly that shape - no more, no less:
{ "data": { "book": { "title": "Dune", "author": { "name": "Herbert" } } } }
```

Created by Facebook (2015), GraphQL is **not** tied to any language or database — it's a spec. In Python, **Strawberry** is the modern, type-hints-based implementation that pairs naturally with FastAPI.

---

## 2. The Problems GraphQL Addresses

REST works well, but two friction points motivated GraphQL:

### 2.1 Over-fetching

A REST `GET /users/1` returns the **whole** user object even if the client only needs the name. Bytes wasted on fields nobody wanted.

### 2.2 Under-fetching (the N+1 round trip)

To render "a user and their posts and each post's comments," a REST client makes **several** calls: `/users/1`, then `/users/1/posts`, then `/posts/{id}/comments` for each. Many round trips.

```
REST:     GET /users/1  →  GET /users/1/posts  →  GET /posts/5/comments  →  ...
GraphQL:  one query asks for user + posts + comments, server returns it all at once
```

> 🔑 GraphQL lets the **client** decide exactly which fields and relationships to fetch **in one request** — eliminating over-fetching and multi-round-trip under-fetching. That flexibility is its core value proposition.

---

## 3. GraphQL vs REST

| | **REST** | **GraphQL** |
|---|---|---|
| Endpoints | Many (`/users`, `/posts`, …) | **One** (`/graphql`) |
| Response shape | Fixed by the server | **Chosen by the client** |
| Over/under-fetching | Common | Avoided |
| HTTP methods | GET/POST/PUT/DELETE | Usually **POST** (queries + mutations) |
| Caching | Easy (HTTP caching per URL) | **Harder** (one URL, POST bodies) |
| Schema/types | Optional (OpenAPI) | **Built-in, required, strongly typed** |
| File uploads, streaming | Natural | Awkward |
| Learning curve | Low | Higher |
| Best for | Most APIs, public APIs, simple CRUD | Complex/nested data, many clients with different needs |

> 🔑 GraphQL isn't "better than REST" — it's a **trade-off**. You gain client-driven flexibility and a typed schema; you lose easy HTTP caching and simplicity, and you take on more server complexity. Most APIs are still fine (often better) as REST.

---

## 4. The Three Core Concepts

Every GraphQL API is built from three operation types plus a schema:

| Concept | REST analogy | Purpose |
|---|---|---|
| **Query** | `GET` | Read data |
| **Mutation** | `POST`/`PUT`/`DELETE` | Change data |
| **Subscription** | (WebSockets) | Real-time updates |
| **Schema** | OpenAPI | The typed definition of everything available |

The **schema** is the heart: a strongly-typed contract listing every type, field, query, and mutation. Clients (and tools) introspect it to know exactly what's available — a big GraphQL selling point.

---

## 5. Strawberry — GraphQL the Python Way

**Strawberry** defines the schema with **Python type hints and decorators** (very FastAPI-like). You describe types as classes:

```python
import strawberry

@strawberry.type
class Author:
    id: int
    name: str

@strawberry.type
class Book:
    id: int
    title: str
    author: Author        # a nested/related type
```

Then a **Query** type whose methods are **resolvers** — functions that return the data for a field:

```python
@strawberry.type
class Query:
    @strawberry.field
    def book(self, id: int) -> Book | None:
        return get_book_from_db(id)      # your data source

    @strawberry.field
    def books(self) -> list[Book]:
        return get_all_books()
```

- `@strawberry.type` → a GraphQL object type.
- `@strawberry.field` → a resolver; its **return type hint** defines the field's type, its **parameters** become GraphQL arguments (`book(id: 1)`).
- Nested types (`author: Author`) let clients traverse relationships.

---

## 6. Mutations — Changing Data

Reads are queries; writes are **mutations**. Same idea, a `Mutation` type:

```python
@strawberry.type
class Mutation:
    @strawberry.mutation
    def add_book(self, title: str, author_id: int) -> Book:
        return create_book(title, author_id)
```

A client calls it like:

```graphql
mutation {
  addBook(title: "New Book", authorId: 2) {
    id
    title
  }
}
```

Note the mutation **returns a type** too, so the client picks which fields of the newly created object it wants back — the same field-selection flexibility as queries.

---

## 7. Mounting GraphQL on FastAPI

Strawberry provides a `GraphQLRouter` you mount like any router (Lesson 16). GraphQL lives **alongside** your REST routes — it's not either/or:

```python
import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import FastAPI

schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")   # one endpoint for all GraphQL

@app.get("/rest/health")     # normal REST routes still work
def health():
    return {"status": "ok"}
```

- Everything GraphQL goes through the single **`POST /graphql`** endpoint.
- Strawberry serves an interactive **GraphiQL explorer** at `/graphql` in the browser — try queries live, with autocomplete from the schema.
- You can run **REST and GraphQL in the same app**, migrating or offering both.

> 🔑 GraphQL in FastAPI is just another **router**. You don't replace REST — you **add** a `/graphql` endpoint. Many teams expose both and let clients choose.

---

## 8. The Trade-offs — Honestly

GraphQL's flexibility has real costs you must weigh:

**Advantages**
- Clients fetch **exactly** what they need — no over/under-fetching.
- **One request** for complex, nested data.
- **Strongly-typed, introspectable schema** — great tooling and autocomplete.
- One endpoint evolves without versioning churn.

**Drawbacks**
- **Caching is harder** — REST leans on HTTP caching per URL; GraphQL is one POST URL, so you need app-level/GraphQL-specific caching.
- **The N+1 problem moves server-side** — a nested query can fire many DB queries; you need **DataLoader** batching to avoid it.
- **Complexity/security** — clients can request deeply nested, expensive queries; you need **query depth/complexity limits** and rate control.
- **Steeper learning curve** for the whole team.
- File uploads, streaming, and simple CRUD are **more awkward** than REST.

> 🔑 Reach for GraphQL when you have **complex, deeply related data** and **many different clients** (web, mobile, partners) each needing different slices. Stick with **REST** for straightforward CRUD, public APIs that benefit from HTTP caching, or when simplicity matters. **Both are legitimate; neither is a default winner.**

---

## 9. Real-World Use Case — A Mobile + Web + Partner API

You back three very different clients:

- A **web dashboard** needs rich, deeply-nested data on one screen.
- A **mobile app** wants minimal payloads (bandwidth-constrained) — just a few fields.
- **Partners** query your data in shapes you can't predict.

With REST you'd build many tailored endpoints (or ship over-fetching payloads and force multiple round trips). With **GraphQL**, each client sends **one query for exactly its shape** — the web app asks for everything, mobile asks for three fields, partners compose their own — all against one schema. This "many clients, divergent needs, nested data" situation is GraphQL's sweet spot. A simple internal CRUD service, by contrast, gains little from GraphQL's overhead — REST is the cleaner choice there.

---

## 10. Mini Task

`main.py` mounts a GraphQL API (books + authors) at `/graphql` next to a REST route.

1. Install: `pip install "strawberry-graphql[fastapi]"`
2. Run: `uvicorn main:app --reload`
3. Open **`http://127.0.0.1:8000/graphql`** — the interactive GraphiQL explorer.
4. Run a query, asking for only the fields you want:
   ```graphql
   query {
     books { title author { name } }
   }
   ```
   Then request just `title` and see how the response shrinks — **client-chosen fields**.
5. Fetch one book by argument:
   ```graphql
   query { book(id: 1) { id title } }
   ```
6. Run a mutation and pick the return fields:
   ```graphql
   mutation { addBook(title: "New Title", authorId: 1) { id title author { name } } }
   ```
7. Compare: hit the REST route `/rest/books` and notice it returns a **fixed** shape, while GraphQL let you choose.
8. **Experiment:**
   - Add an `authors` query and a nested `author { books { title } }` traversal.
   - Add a `deleteBook(id)` mutation.
   - Ask for a field that doesn't exist and see the schema-driven error.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Choosing GraphQL by default / hype | Weigh the trade-offs; REST is fine (often better) for simple APIs. |
| Ignoring the server-side N+1 | Use DataLoader batching for nested resolvers. |
| No query depth/complexity limits | Malicious deep queries can DoS you; cap depth/complexity. |
| Expecting HTTP caching to "just work" | GraphQL needs app-level caching (one POST URL). |
| Replacing REST entirely overnight | Mount GraphQL alongside REST; migrate gradually. |
| Forgetting it's still one endpoint to secure | Apply auth/rate limits to `/graphql` too. |

---

## 12. Key Takeaways

- **GraphQL** = one endpoint + a typed schema where the **client chooses exactly which fields/relations** to fetch in a single request.
- It solves REST's **over-fetching** and **under-fetching (multi-round-trip)** problems.
- Core concepts: **queries** (read), **mutations** (write), **subscriptions** (real-time), all defined by a strongly-typed **schema**.
- **Strawberry** builds the schema from Python **type hints** (`@strawberry.type`, `@strawberry.field`, `@strawberry.mutation`) and mounts on FastAPI via **`GraphQLRouter`** at `/graphql`, **alongside REST**.
- Trade-offs: harder **caching**, server-side **N+1** (needs DataLoader), **query-complexity** risks, steeper learning curve.
- **Use GraphQL for complex, nested data and many divergent clients; use REST for simple CRUD, public/cacheable APIs, and when simplicity wins.** Both are valid.

---

## 🎉 Phase 4 Complete

You've covered the advanced feature set: async internals, authentication/authorization, background tasks, WebSockets, SSE/streaming, CORS, rate limiting, caching, pagination, filtering/sorting/searching, i18n, and GraphQL. Your APIs can now be real-time, secure, performant, and flexible.

## ➡️ Next Lesson

**Lesson 40 — Testing Fundamentals** (start of Phase 5)
- `TestClient` (sync) and `httpx.AsyncClient` (async)
- `pytest` basics
- Writing your first API tests
