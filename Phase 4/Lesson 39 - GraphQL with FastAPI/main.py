"""
Lesson 39 - GraphQL with FastAPI (via Strawberry)   [optional]
--------------------------------------------------------------
A GraphQL API (books + authors) mounted at /graphql, ALONGSIDE a normal REST
route - GraphQL does not replace REST, it is just another router.

    - @strawberry.type      -> GraphQL object types (Author, Book)
    - @strawberry.field     -> query resolvers (book, books, authors)
    - @strawberry.mutation  -> write operations (add_book)
    - GraphQLRouter mounts the schema at a single POST /graphql endpoint
    - an interactive GraphiQL explorer is served at /graphql in the browser

Install once:

    pip install "fastapi" uvicorn "strawberry-graphql[fastapi]"

How to run (from inside this folder):

    uvicorn main:app --reload

Then open http://127.0.0.1:8000/graphql and try:

    query { books { title author { name } } }
    mutation { addBook(title: "New", authorId: 1) { id title } }
"""

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

# ---------------------------------------------------------------------------
# In-memory data (a real app would use the database from Phase 3).
# ---------------------------------------------------------------------------
AUTHORS = [
    {"id": 1, "name": "Frank Herbert"},
    {"id": 2, "name": "Ursula K. Le Guin"},
]
BOOKS = [
    {"id": 1, "title": "Dune", "author_id": 1},
    {"id": 2, "title": "The Left Hand of Darkness", "author_id": 2},
    {"id": 3, "title": "Children of Dune", "author_id": 1},
]


# ===========================================================================
# GRAPHQL TYPES - defined with plain Python type hints
# ===========================================================================
@strawberry.type
class Author:
    id: int
    name: str

    @strawberry.field
    def books(self) -> list["Book"]:
        # Resolver for a nested relationship: this author's books.
        return [Book(id=b["id"], title=b["title"], author_id=b["author_id"])
                for b in BOOKS if b["author_id"] == self.id]


@strawberry.type
class Book:
    id: int
    title: str
    author_id: int

    @strawberry.field
    def author(self) -> Author | None:
        # Resolver: follow the relationship to the book's author.
        a = next((a for a in AUTHORS if a["id"] == self.author_id), None)
        return Author(id=a["id"], name=a["name"]) if a else None


def _to_book(b: dict) -> Book:
    return Book(id=b["id"], title=b["title"], author_id=b["author_id"])


# ===========================================================================
# QUERIES (read) - each @strawberry.field is a resolver
# ===========================================================================
@strawberry.type
class Query:
    @strawberry.field
    def books(self) -> list[Book]:
        return [_to_book(b) for b in BOOKS]

    @strawberry.field
    def book(self, id: int) -> Book | None:
        b = next((b for b in BOOKS if b["id"] == id), None)
        return _to_book(b) if b else None

    @strawberry.field
    def authors(self) -> list[Author]:
        return [Author(id=a["id"], name=a["name"]) for a in AUTHORS]


# ===========================================================================
# MUTATIONS (write)
# ===========================================================================
@strawberry.type
class Mutation:
    @strawberry.mutation
    def add_book(self, title: str, author_id: int) -> Book:
        new = {"id": max(b["id"] for b in BOOKS) + 1, "title": title,
               "author_id": author_id}
        BOOKS.append(new)
        return _to_book(new)


# ===========================================================================
# MOUNT GraphQL alongside REST
# ===========================================================================
schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)   # serves POST /graphql + GraphiQL explorer

app = FastAPI(title="Lesson 39 - GraphQL with FastAPI")
app.include_router(graphql_app, prefix="/graphql")


# A plain REST route, to contrast the FIXED shape with GraphQL's flexibility.
@app.get("/rest/books")
def rest_books():
    return {"books": BOOKS, "note": "REST returns a fixed shape; GraphQL lets the "
                                     "client pick fields at /graphql"}


@app.get("/")
def root():
    return {"message": "GraphQL at /graphql (GraphiQL explorer in a browser); "
                       "REST at /rest/books"}
