"""
Lesson 27 - NoSQL Integration (MongoDB + Redis)
-----------------------------------------------
A MongoDB-style DOCUMENT api (via the Motor async API) fronted by a Redis
CACHE (cache-aside pattern with TTL + invalidation).

RUNS WITH NO SERVERS. By default it uses in-memory fakes that expose the exact
same API as the real clients:
    - mongomock-motor  stands in for  motor (real MongoDB)
    - fakeredis        stands in for  redis.asyncio (real Redis)

Because the fakes share the real API, switching to real servers is ONE line:
set USE_FAKES = False (and have MongoDB + Redis running).

Every product read response includes a "_source" field ("database" or "cache")
so you can SEE the cache working.

Install (for the runnable fakes):

    pip install fastapi uvicorn motor mongomock-motor fakeredis redis

How to run (from inside this folder):

    uvicorn main:app --reload

Then open:
    http://127.0.0.1:8000/docs
"""

import json
from contextlib import asynccontextmanager
from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

# ===========================================================================
# CLIENTS - fakes by default; flip USE_FAKES to False for real servers.
# The ENDPOINT CODE BELOW IS IDENTICAL either way (same API).
# ===========================================================================
USE_FAKES = True

MONGO_URL = "mongodb://localhost:27017"
REDIS_URL = "redis://localhost:6379"
CACHE_TTL_SECONDS = 60


def make_mongo_client():
    if USE_FAKES:
        from mongomock_motor import AsyncMongoMockClient

        return AsyncMongoMockClient()
    from motor.motor_asyncio import AsyncIOMotorClient  # real MongoDB

    return AsyncIOMotorClient(MONGO_URL)


def make_redis_client():
    if USE_FAKES:
        import fakeredis.aioredis

        return fakeredis.aioredis.FakeRedis()
    import redis.asyncio as redis  # real Redis

    return redis.from_url(REDIS_URL)


# ===========================================================================
# SCHEMAS (Pydantic) - documents are schemaless, so we validate at the edge.
# ===========================================================================
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    sku: str = Field(..., min_length=3, max_length=30)
    price: float = Field(..., gt=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    price: float | None = Field(None, gt=0)


def doc_to_dict(doc: dict) -> dict:
    """Convert a Mongo document to a JSON-safe dict (ObjectId -> str id)."""
    return {
        "id": str(doc["_id"]),  # ObjectId is not JSON serializable
        "name": doc["name"],
        "sku": doc["sku"],
        "price": doc["price"],
    }


def parse_object_id(product_id: str) -> ObjectId:
    try:
        return ObjectId(product_id)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")


# ===========================================================================
# APP + LIFESPAN (create clients once; close on shutdown)
# ===========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo = make_mongo_client()
    app.state.products = mongo["shop"]["products"]  # database -> collection
    app.state.redis = make_redis_client()
    yield
    await app.state.redis.aclose()
    mongo.close()


app = FastAPI(title="Lesson 27 - NoSQL (MongoDB + Redis)", lifespan=lifespan)


# Dependencies that hand endpoints the shared clients created in lifespan.
ProductsColl = Annotated[object, Depends(lambda: app.state.products)]
Redis = Annotated[object, Depends(lambda: app.state.redis)]


@app.get("/")
async def root():
    return {
        "message": "See /docs. MongoDB-style documents + Redis cache-aside.",
        "using_fakes": USE_FAKES,
    }


# ---------------------------------------------------------------------------
# CREATE - insert a document (Motor: insert_one)
# ---------------------------------------------------------------------------
@app.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, products: ProductsColl):
    # Enforce unique sku ourselves (Mongo is schemaless - no UNIQUE by default).
    if await products.find_one({"sku": payload.sku}) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"SKU '{payload.sku}' exists")

    result = await products.insert_one(payload.model_dump())
    doc = await products.find_one({"_id": result.inserted_id})
    return doc_to_dict(doc)


# ---------------------------------------------------------------------------
# READ one - CACHE-ASIDE: try Redis first, fall back to Mongo, fill cache.
# ---------------------------------------------------------------------------
@app.get("/products/{product_id}")
async def get_product(product_id: str, products: ProductsColl, redis: Redis):
    key = f"product:{product_id}"

    # 1. Try the cache.
    cached = await redis.get(key)
    if cached is not None:
        data = json.loads(cached)
        data["_source"] = "cache"  # so you can SEE it was a cache hit
        return data

    # 2. Cache miss -> hit the database.
    oid = parse_object_id(product_id)
    doc = await products.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    data = doc_to_dict(doc)

    # 3. Fill the cache with a TTL, then return.
    await redis.set(key, json.dumps(data), ex=CACHE_TTL_SECONDS)
    data["_source"] = "database"
    return data


# ---------------------------------------------------------------------------
# LIST - Motor find() with a $gt query operator (not cached, for contrast)
# ---------------------------------------------------------------------------
@app.get("/products")
async def list_products(
    products: ProductsColl,
    min_price: float | None = Query(None, ge=0),
):
    query = {}
    if min_price is not None:
        query["price"] = {"$gt": min_price}  # Mongo query operator
    docs = await products.find(query).to_list(length=100)
    return [doc_to_dict(d) for d in docs]


# ---------------------------------------------------------------------------
# UPDATE - Motor update_one, then INVALIDATE the cache key.
# ---------------------------------------------------------------------------
@app.patch("/products/{product_id}")
async def update_product(
    product_id: str, payload: ProductUpdate, products: ProductsColl, redis: Redis
):
    oid = parse_object_id(product_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")

    result = await products.update_one({"_id": oid}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    await redis.delete(f"product:{product_id}")  # <-- critical: invalidate cache
    doc = await products.find_one({"_id": oid})
    return doc_to_dict(doc)


# ---------------------------------------------------------------------------
# DELETE - Motor delete_one, then invalidate the cache key.
# ---------------------------------------------------------------------------
@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, products: ProductsColl, redis: Redis):
    oid = parse_object_id(product_id)
    result = await products.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    await redis.delete(f"product:{product_id}")  # keep cache consistent
