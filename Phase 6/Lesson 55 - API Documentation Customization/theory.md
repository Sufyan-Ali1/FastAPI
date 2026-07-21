# Lesson 55 — API Documentation Customization

> **Goal of this lesson:** Turn FastAPI's automatic docs into **professional, polished API documentation**. Customize the **OpenAPI schema** (metadata, tags, contact/license), add rich **examples** and descriptions, **hide** internal endpoints, and override the generated schema when you need full control.
>
> `main.py` shows every technique; the verification inspects the generated `/openapi.json` to confirm each customization landed.

---

## 1. You Already Have Docs — Now Make Them Great

Since Lesson 1, FastAPI has auto-generated interactive docs at **`/docs`** (Swagger UI) and **`/redoc`** (ReDoc) from your code, backed by an **OpenAPI schema** at **`/openapi.json`**. That's a huge feature you got for free.

But the *default* docs are functional, not polished. For a **public** API — one that partners, other teams, or customers integrate against — the docs are the **product's front door**. Good documentation is the difference between "I integrated in 10 minutes" and "I gave up." This lesson makes your auto-docs production-quality.

> 🔑 FastAPI's docs are auto-generated, but **great** docs are customized. For any API others consume, the documentation *is* the developer experience — invest in it.

---

## 2. What Is OpenAPI?

**OpenAPI** (formerly Swagger) is the industry-standard, language-agnostic format for describing REST APIs — every endpoint, parameter, request/response schema, and status code as a JSON document. FastAPI generates it from your **type hints, Pydantic models, and route metadata** automatically.

```
your code (types + models + metadata)
        │  FastAPI generates
        ▼
   /openapi.json   ──renders──►  /docs (Swagger UI) and /redoc (ReDoc)
```

Everything in this lesson works by **enriching the metadata** FastAPI uses to build that `/openapi.json` — which then flows into the rendered docs.

> 🔑 Customizing docs = enriching the **OpenAPI schema**. You add metadata to your app, routes, and models; FastAPI folds it into `/openapi.json`, and Swagger/ReDoc render it.

---

## 3. App-Level Metadata

Start with the top-level info — this appears at the top of the docs page:

```python
app = FastAPI(
    title="Bookstore API",
    description="A public API for browsing and managing books.\n\nSupports **Markdown**.",
    summary="Browse, search, and manage a book catalog.",
    version="2.1.0",
    terms_of_service="https://example.com/terms",
    contact={"name": "API Support", "url": "https://example.com/support",
             "email": "api@example.com"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
)
```

| Field | Shows |
|---|---|
| `title` / `version` | The API name and version at the top |
| `description` | A rich intro — **Markdown supported** (headings, links, code) |
| `summary` | A one-line tagline |
| `contact` / `license_info` / `terms_of_service` | Support and legal info |

> 🔑 Set `title`, `description` (Markdown!), `version`, `contact`, and `license` — the professional header every public API's docs should have.

---

## 4. Tags — Grouping and Describing Sections

**Tags** group endpoints into sections in the docs. Beyond attaching a `tags=[...]` to routes (Lesson 16), you can give each tag a **description** and control ordering via `openapi_tags`:

```python
tags_metadata = [
    {"name": "books", "description": "Browse and manage the **book catalog**."},
    {"name": "authors", "description": "Author profiles and their books.",
     "externalDocs": {"description": "Author guide", "url": "https://.../authors"}},
]

app = FastAPI(openapi_tags=tags_metadata)

@app.get("/books", tags=["books"])
def list_books(): ...
```

The docs then show a **"books"** section with its description, a **"authors"** section with a link to external docs, in the order you listed them.

> 🔑 Use **`openapi_tags`** to describe and order the doc sections. Well-grouped, described tags turn a flat endpoint list into navigable documentation.

---

## 5. Per-Endpoint Metadata

Each route can carry rich documentation:

```python
@app.post(
    "/books",
    tags=["books"],
    summary="Create a book",                     # short label in the list
    description="Add a new book to the catalog. Requires a unique ISBN.",
    response_description="The created book with its generated id.",
    status_code=201,
)
def create_book(book: BookCreate):
    """You can also write the description as the function **docstring**
    (Markdown supported) instead of the `description=` argument."""
    ...
```

| Argument | Effect in docs |
|---|---|
| `summary` | Short label next to the endpoint |
| `description` (or the **docstring**) | Full description, Markdown-supported |
| `response_description` | Describes the success response |
| `deprecated=True` | Marks the endpoint as deprecated (strikethrough) |
| `tags` | Which section it belongs to |

> 🔑 Give each endpoint a **`summary`**, a **description** (or docstring), and a **`response_description`**. Mark old ones **`deprecated=True`** (pairs with Lesson 54's versioning).

---

## 6. Examples — The Highest-Value Customization

**Examples** are what make docs genuinely useful — they show integrators exactly what a request/response looks like, and pre-fill Swagger's "Try it out." Several ways to add them:

**On a Pydantic field:**
```python
class BookCreate(BaseModel):
    title: str = Field(..., examples=["The Pragmatic Programmer"])
    isbn: str = Field(..., examples=["978-0-13-595705-9"])
```

**A full-model example via `model_config`:**
```python
class BookCreate(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [{"title": "Dune", "isbn": "978-0-441-17271-9", "price": 9.99}]
        }
    }
```

**Multiple named examples with `Body(openapi_examples=...)`** (Swagger shows a dropdown to pick between them):
```python
@app.post("/books")
def create_book(book: Annotated[BookCreate, Body(openapi_examples={
    "normal": {"summary": "A typical book", "value": {"title": "Dune", "isbn": "...", "price": 9.99}},
    "discounted": {"summary": "On sale", "value": {"title": "1984", "isbn": "...", "price": 1.99}},
})]): ...
```

> 🔑 **Examples are the single highest-value doc customization** — they show integrators exactly what to send and pre-fill "Try it out." Use `Field(examples=)`, `json_schema_extra`, or `Body(openapi_examples=)` for multiple named examples.

---

## 7. Documenting Responses

By default the docs show your `response_model` for the success case. Real endpoints return **multiple** status codes — document them with the **`responses`** argument:

```python
@app.get("/books/{book_id}", response_model=BookRead,
    responses={
        404: {"description": "Book not found",
              "content": {"application/json": {"example": {"detail": "Book not found"}}}},
        409: {"description": "Conflict"},
    })
def get_book(book_id: int): ...
```

Now the docs list the `200`, `404`, and `409` responses, each with a description and example — so integrators know every outcome to handle, not just the happy path.

> 🔑 Document **all** the status codes an endpoint can return with `responses={...}`, not just the success case. Integrators need to know about the `404`/`409`/`422` responses to handle them.

---

## 8. Hiding Endpoints

Some routes shouldn't appear in public docs — internal admin tools, debug endpoints, health checks. Hide them with **`include_in_schema=False`**:

```python
@app.get("/internal/debug", include_in_schema=False)   # works, but absent from docs
def debug(): ...

@app.get("/health", include_in_schema=False)           # health checks clutter docs
def health(): ...
```

The endpoint still **works** — it's just omitted from `/openapi.json` and therefore from `/docs`. Great for internal-only or noise endpoints.

> 🔑 Hide internal/health/debug routes from public docs with **`include_in_schema=False`** — they keep working but don't clutter (or expose) the documentation.

---

## 9. The Docs URLs — Customize or Disable

You can rename, move, or disable the doc endpoints:

```python
app = FastAPI(
    docs_url="/documentation",   # move Swagger UI (default /docs)
    redoc_url=None,              # disable ReDoc
    openapi_url="/api/openapi.json",   # move the schema
)
# Disable ALL docs (e.g. for an internal API): openapi_url=None
```

Some teams **disable docs in production** for private APIs (`openapi_url=None`), or protect them behind auth. Public APIs keep them on and polished.

> 💡 You can move, rename, or **disable** the docs (`docs_url`/`redoc_url`/`openapi_url`). Disable or protect them for private APIs; keep them prominent and polished for public ones.

---

## 10. Overriding the OpenAPI Schema

For full control, override FastAPI's schema generation with a **`custom_openapi`** function — to add a logo, servers list, custom security schemes, or any OpenAPI field FastAPI doesn't expose directly:

```python
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema                 # cache
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schema["info"]["x-logo"] = {"url": "https://example.com/logo.png"}   # ReDoc logo
    schema["servers"] = [{"url": "https://api.example.com", "description": "Production"}]
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi
```

This is the escape hatch: generate the default schema, then mutate it. Cache the result (`app.openapi_schema`) so it's built once.

> 🔑 For anything the standard args don't cover (logo, `servers`, custom extensions), override `app.openapi` with a **`custom_openapi`** function that generates and then augments the schema. Cache it.

---

## 11. Real-World Use Case — A Public API's Front Door

You're launching the bookstore API publicly. Documentation polish:

- **App metadata**: a clear title, a Markdown description with a quick-start, version `2.1.0`, contact and license — the professional header.
- **Tags**: `books`, `authors`, `orders` sections, each described and ordered logically.
- **Examples**: every request body has a realistic example (and the order endpoint offers "normal" vs "gift order" named examples) so integrators can copy-paste.
- **Responses**: each endpoint documents its `404`/`409`/`422` outcomes, not just `200`.
- **Hidden**: `/health` and internal admin routes are `include_in_schema=False`.
- **Custom schema**: a company logo (ReDoc) and a `servers` list (production + sandbox URLs).
- Deprecated v1 endpoints are marked `deprecated=True` (Lesson 54).

A partner lands on `/docs`, reads the intro, browses well-grouped endpoints with copy-paste examples, and integrates in an afternoon. That polished front door is a competitive advantage — and it's almost entirely metadata.

---

## 12. Mini Task

`main.py` applies every customization.

1. Run: `uvicorn main:app --reload` → open `/docs` and `/redoc`. Note the title, description, tag sections, examples, and documented responses.
2. Fetch the raw schema: `GET /openapi.json` and find the metadata, tags, and examples in it.
3. Confirm the **hidden** endpoint (`/internal/ping`) **works** but does **not** appear in `/docs` or `/openapi.json`.
4. In Swagger, use "Try it out" on the create endpoint — the **example** pre-fills the body; the multi-example endpoint shows a **dropdown**.
5. **Experiment:**
   - Add a `contact` and `license_info` and see them in the docs header.
   - Add a `409` response to an endpoint's `responses`.
   - Add a second named `openapi_examples` entry and pick it in Swagger.
6. **Bonus:** Add a `custom_openapi` that injects a `servers` list, and confirm it appears in `/openapi.json`.

---

## 13. Common Mistakes

| Mistake | Fix |
|---|---|
| Shipping default, unpolished docs for a public API | Add metadata, tags, examples, response docs. |
| No request/response examples | Add them — the highest-value doc improvement. |
| Only documenting the success case | List `404`/`409`/`422` in `responses={...}`. |
| Internal/health routes cluttering public docs | `include_in_schema=False`. |
| Leaving docs fully public on a private API | Disable (`openapi_url=None`) or protect them. |
| Fighting the standard args for custom fields | Override `app.openapi` for full control. |
| Descriptions with no structure | Use Markdown in descriptions and docstrings. |

---

## 14. Key Takeaways

- FastAPI auto-generates docs (`/docs`, `/redoc`) from an **OpenAPI schema** (`/openapi.json`); customizing = **enriching that schema's metadata**.
- Set **app metadata** (`title`, Markdown `description`, `version`, `contact`, `license`) — the professional header.
- Describe and order sections with **`openapi_tags`**; give each endpoint a **`summary`**, description, and `response_description`; mark old ones `deprecated=True`.
- **Examples** are the highest-value customization (`Field(examples=)`, `json_schema_extra`, `Body(openapi_examples=)` for named examples) — they pre-fill "Try it out."
- Document **all** status codes with **`responses={...}`**, not just success.
- **Hide** internal/health routes with **`include_in_schema=False`**; **move/disable** the docs URLs as needed.
- For anything the args don't cover, override **`app.openapi`** with a custom schema function (logo, `servers`, extensions) and cache it.
- Great docs are the **front door** of any public API — mostly metadata, hugely valuable.

---

## 🎉 Phase 6 Complete — and the Core Course

You've finished Phase 6: production project structure, configuration, logging, security, performance, Docker, production servers, deployment, CI/CD, monitoring, versioning, and documentation. Combined with Phases 1–5, you can now **build, test, secure, deploy, monitor, and evolve** a production-grade FastAPI application end to end.

## ➡️ What's Next — Bonus / Expert Topics

**Lessons 56–60** cover advanced/optional territory: **microservices**, **event-driven systems** (RabbitMQ/Kafka), **gRPC alongside FastAPI**, **LLM/AI API patterns**, and a **final capstone project** that combines everything.
