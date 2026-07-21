"""
Lesson 55 - API Documentation Customization
-------------------------------------------
Applies every OpenAPI customization technique so /docs and /redoc read like a
polished, public API:

    - app metadata (title, Markdown description, version, contact, license)
    - openapi_tags with descriptions + ordering
    - per-endpoint summary / description / response_description / deprecated
    - request-body examples (Field examples + multiple named openapi_examples)
    - documented non-200 responses (404, 409)
    - a hidden internal endpoint (include_in_schema=False)
    - a custom_openapi() override adding a servers list + logo

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Then open /docs, /redoc, and GET /openapi.json.
"""

from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Path
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

# --- tag metadata: describe + order the doc sections ------------------------
tags_metadata = [
    {"name": "books", "description": "Browse and manage the **book catalog**."},
    {
        "name": "authors",
        "description": "Author profiles.",
        "externalDocs": {"description": "Author guide", "url": "https://example.com/authors"},
    },
]

app = FastAPI(
    title="Bookstore API",
    summary="Browse, search, and manage a book catalog.",
    description=(
        "A demo **public** API showing OpenAPI customization.\n\n"
        "- Rich Markdown descriptions\n"
        "- Request/response examples\n"
        "- Documented error responses"
    ),
    version="2.1.0",
    terms_of_service="https://example.com/terms",
    contact={"name": "API Support", "url": "https://example.com/support", "email": "api@example.com"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=tags_metadata,
)


# --- schemas with examples -------------------------------------------------
class BookCreate(BaseModel):
    title: str = Field(..., examples=["The Pragmatic Programmer"])
    isbn: str = Field(..., examples=["978-0-13-595705-9"])
    price: float = Field(..., gt=0, examples=[42.0])


class BookRead(BookCreate):
    id: int


_BOOKS: dict[int, dict] = {}
_next = {"id": 1}


# --- endpoints with rich metadata ------------------------------------------
@app.post(
    "/books",
    response_model=BookRead,
    status_code=201,
    tags=["books"],
    summary="Create a book",
    response_description="The created book with its generated id.",
    responses={409: {"description": "A book with this ISBN already exists."}},
)
def create_book(
    book: Annotated[
        BookCreate,
        Body(openapi_examples={   # MULTIPLE named examples -> a dropdown in Swagger
            "normal": {"summary": "A typical book",
                       "value": {"title": "Dune", "isbn": "978-0-441-17271-9", "price": 9.99}},
            "textbook": {"summary": "An expensive textbook",
                         "value": {"title": "SICP", "isbn": "978-0-262-51087-5", "price": 89.0}},
        }),
    ],
):
    """Add a new book to the catalog. The **ISBN must be unique**."""
    if any(b["isbn"] == book.isbn for b in _BOOKS.values()):
        raise HTTPException(409, "A book with this ISBN already exists.")
    book_id = _next["id"]
    _next["id"] += 1
    _BOOKS[book_id] = {"id": book_id, **book.model_dump()}
    return _BOOKS[book_id]


@app.get(
    "/books/{book_id}",
    response_model=BookRead,
    tags=["books"],
    summary="Get one book",
    responses={404: {"description": "Book not found",
                     "content": {"application/json": {"example": {"detail": "Book not found"}}}}},
)
def get_book(book_id: Annotated[int, Path(ge=1, examples=[1])]):
    book = _BOOKS.get(book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    return book


@app.get("/books", response_model=list[BookRead], tags=["books"], summary="List books")
def list_books():
    return list(_BOOKS.values())


@app.get(
    "/authors/legacy",
    tags=["authors"],
    summary="Legacy author endpoint",
    deprecated=True,     # marked deprecated in the docs (Lesson 54)
)
def legacy_authors():
    return {"note": "use /api/v2 instead"}


# --- HIDDEN endpoint: works, but absent from /docs and /openapi.json --------
@app.get("/internal/ping", include_in_schema=False)
def internal_ping():
    return {"pong": True}


# ---------------------------------------------------------------------------
# CUSTOM OpenAPI schema override: add a `servers` list + a ReDoc logo, things
# the standard FastAPI() args don't expose directly.
# ---------------------------------------------------------------------------
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema          # cache: build once
    schema = get_openapi(
        title=app.title, version=app.version, summary=app.summary,
        description=app.description, tags=app.openapi_tags, routes=app.routes,
        # Forward the metadata too, or the override would drop it:
        contact=app.contact, license_info=app.license_info,
        terms_of_service=app.terms_of_service,
    )
    schema["servers"] = [
        {"url": "https://api.example.com", "description": "Production"},
        {"url": "https://sandbox.example.com", "description": "Sandbox"},
    ]
    schema["info"]["x-logo"] = {"url": "https://example.com/logo.png"}
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
