"""app/main.py - the ASSEMBLY point. Thin by design.

It creates the FastAPI app, wires routers, and translates domain errors from
the services layer into HTTP responses. It contains NO business logic itself.

Run with:

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import items
from app.core.config import settings
from app.db.base import Base, engine
from app.services.exceptions import DuplicateSKUError, ItemNotFoundError

# In production this is Alembic (Lesson 24); create_all keeps the demo runnable.
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

# Wire the routers (one per resource).
app.include_router(items.router)


# Translate DOMAIN errors (raised by services) into HTTP responses. The API
# layer owns HTTP; services stay HTTP-agnostic.
@app.exception_handler(ItemNotFoundError)
async def item_not_found_handler(request: Request, exc: ItemNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DuplicateSKUError)
async def duplicate_sku_handler(request: Request, exc: DuplicateSKUError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "docs": "/docs"}
