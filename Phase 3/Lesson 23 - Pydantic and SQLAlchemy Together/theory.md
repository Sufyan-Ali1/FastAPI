# Lesson 23 — Pydantic + SQLAlchemy Together

> **Goal of this lesson:** Delete the clunky `to_dict()` helpers from Lesson 22. Learn **`from_attributes=True`** (ORM mode) so Pydantic can read SQLAlchemy objects directly, use **`response_model`** for automatic, filtered responses, and adopt the professional **schema-vs-model separation** pattern (`Create` / `Read` / `Update`).
>
> `main.py` is the same Products API as Lesson 22, rebuilt the clean way. Compare them side by side.

---

## 1. The Problem We're Fixing

In Lesson 22 every endpoint ended with a hand-written serializer:

```python
def product_to_dict(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "sku": p.sku,
            "price": float(p.price), "supplier_id": p.supplier_id}

@app.get("/products/{product_id}")
def get_product(product_id: int, db: DB):
    product = db.get(Product, product_id)
    ...
    return product_to_dict(product)   # manual, repeated everywhere
```

That's tedious and fragile:

- Add a column → you must remember to edit the `to_dict`.
- No output validation — a typo silently ships wrong data.
- No automatic docs schema for the **response**.
- The same conversion is duplicated across every endpoint.

**Why can't we just `return product`?** Because a `Product` is a SQLAlchemy model, not JSON. FastAPI doesn't know how to serialize it by default. The bridge is **Pydantic in ORM mode**.

---

## 2. Two Class Families — Recap

| | **Model** | **Schema** |
|---|---|---|
| Base class | `Base` (SQLAlchemy) | `BaseModel` (Pydantic) |
| Represents | A database table / row | The shape of request or response data |
| Lives for | Persisted in the DB | One request/response |
| Example | `Product(Base)` | `ProductCreate`, `ProductRead` |

They often have similar fields — that's fine. They serve **different jobs**: the model is *storage*, the schema is the *API contract*. Keeping them separate is the whole point of this lesson.

---

## 3. `from_attributes=True` — ORM Mode

By default a Pydantic model is built from a **dict** (`ProductRead(**some_dict)`). ORM mode tells Pydantic it can also be built from an **object** by reading its **attributes** (`product.id`, `product.name`, ...).

```python
from pydantic import BaseModel, ConfigDict

class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # <-- the magic switch

    id: int
    name: str
    sku: str
    price: float
    supplier_id: int
```

Now this works:

```python
product = db.get(Product, 1)          # a SQLAlchemy object
schema = ProductRead.model_validate(product)   # reads attributes off the object
```

| | Without `from_attributes` | With `from_attributes=True` |
|---|---|---|
| Build from | `dict` only | `dict` **or** any object with matching attributes |
| `model_validate(orm_obj)` | ❌ error | ✅ reads `.id`, `.name`, ... |

> 🔑 `from_attributes=True` is Pydantic v2's name for what Pydantic v1 called `orm_mode = True`. Same idea, new name.

---

## 4. `response_model` — Let FastAPI Do It

You *could* call `ProductRead.model_validate(product)` by hand in every endpoint. But FastAPI does it for you via **`response_model`** on the decorator:

```python
@app.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: DB):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    return product          # <-- just return the ORM object!
```

FastAPI takes the `Product` you return and, because `response_model=ProductRead` (with `from_attributes=True`), converts it to JSON matching `ProductRead`. No `to_dict`, no `model_validate` call.

**`response_model` gives you four things at once:**

1. **Serialization** — ORM object → JSON automatically.
2. **Filtering** — only fields declared on `ProductRead` are returned. Anything extra on the model (e.g. an internal `cost` column) is **stripped**.
3. **Validation** — the *output* is validated too; a wrong shape is caught, not silently sent.
4. **Docs** — Swagger shows the exact response schema.

Lists work the same way:

```python
@app.get("/products", response_model=list[ProductRead])
def list_products(db: DB):
    return db.scalars(select(Product)).all()   # list of ORM objects -> JSON
```

> 💡 `response_model` vs the `-> ReturnType` hint: a return-type hint also works as a response model in FastAPI, but `response_model=` is explicit and lets you use a *different* type than what your function literally returns (e.g. return an ORM object, declare a Pydantic schema). Prefer `response_model=` when model and schema differ.

---

## 5. Schema-vs-Model Separation — The Professional Pattern

Here's the pattern used in virtually every production FastAPI codebase. For one resource you define **three schemas**, each for a different direction:

| Schema | Direction | Purpose | Notable fields |
|---|---|---|---|
| `ProductCreate` | **In** (POST) | Data the client must send to create | no `id` (server generates it) |
| `ProductRead` | **Out** (responses) | Data the API returns | includes `id`, uses `from_attributes` |
| `ProductUpdate` | **In** (PATCH/PUT) | Fields allowed to change | usually all **optional** |

Why not one schema for everything?

- **Input and output differ.** The client should *never* send `id` — the DB creates it. But responses *must* include `id`. One shared schema can't express both.
- **Security.** A shared schema risks exposing internal fields (a `password_hash`, a `cost`) or letting clients set fields they shouldn't. Separate schemas make the contract explicit.
- **Evolvability.** You can add an output field without forcing clients to send it.

```python
# INPUT: what a client sends to create
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    sku: str = Field(..., min_length=3, max_length=30)
    price: float = Field(..., gt=0)
    supplier_id: int = Field(..., ge=1)

# OUTPUT: what the API returns
class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sku: str
    price: float
    supplier_id: int

# PARTIAL UPDATE: every field optional
class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    price: float | None = Field(None, gt=0)
    supplier_id: int | None = Field(None, ge=1)
```

> 🔑 Common convention names: `XxxCreate`, `XxxRead` (or `XxxOut`/`XxxResponse`), `XxxUpdate`. Sometimes a `XxxBase` holds the shared fields and the others inherit from it (shown in §8).

---

## 6. Partial Updates with `exclude_unset`

`ProductUpdate` makes every field optional, so a client can send **only** what changes:

```json
PATCH /products/1
{ "price": 19.99 }
```

The trick is to update **only the fields the client actually sent**, not overwrite everything with `None`:

```python
@app.patch("/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: DB):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")

    # exclude_unset=True -> dict of ONLY the fields present in the request
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product
```

- `model_dump(exclude_unset=True)` drops any field the client didn't include (from Lesson 10's `response_model_exclude_unset`, now on the input side).
- Send `{"price": 19.99}` → only `price` changes; `name` and `supplier_id` are untouched.

> 💡 **PUT vs PATCH:** `PUT` = full replacement (client sends every field → use `ProductCreate`). `PATCH` = partial update (client sends a subset → use `ProductUpdate` + `exclude_unset`). This lesson uses `PATCH` to showcase partial updates.

---

## 7. Nested Schemas — Serializing Relationships

Because ORM mode reads attributes, it can follow **relationships** too. Want each product's response to embed its supplier? Nest one read-schema inside another:

```python
class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class ProductWithSupplier(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sku: str
    price: float
    supplier: SupplierRead        # <-- nested; reads product.supplier
```

Return the ORM object as usual:

```python
@app.get("/products/{product_id}/full", response_model=ProductWithSupplier)
def get_product_full(product_id: int, db: DB):
    product = db.get(Product, product_id)
    ...
    return product     # FastAPI reads product.supplier and nests it
```

Response:

```json
{
  "id": 1, "name": "Keyboard", "sku": "KB-001", "price": 25.0,
  "supplier": { "id": 1, "name": "Acme Inc" }
}
```

The `SupplierRead` schema also **filters** the nested object — even if `Supplier` had 10 columns, only `id` and `name` appear. This is how you avoid over-exposing related data.

> ⚠️ Relationship access can trigger extra queries (the **N+1 problem**, Lesson 48). For now it just works; we'll optimize loading later.

---

## 8. Optional: `Base` Schema to Avoid Repetition

Notice `name`, `sku`, `price` repeat across schemas. A shared base cuts duplication:

```python
class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    sku: str = Field(..., min_length=3, max_length=30)
    price: float = Field(..., gt=0)
    supplier_id: int = Field(..., ge=1)

class ProductCreate(ProductBase):
    pass                                   # same fields as base

class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: int                                # adds the server-generated id
```

Use it when it genuinely reduces repetition; don't force it when schemas diverge a lot.

---

## 9. Before / After — The Whole Point

**Lesson 22 (manual):**

```python
def product_to_dict(p): return {"id": p.id, "name": p.name, ...}

@app.get("/products/{product_id}")
def get_product(product_id: int, db: DB):
    product = db.get(Product, product_id)
    if product is None: raise HTTPException(404, "...")
    return product_to_dict(product)        # manual conversion
```

**Lesson 23 (clean):**

```python
@app.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: DB):
    product = db.get(Product, product_id)
    if product is None: raise HTTPException(404, "...")
    return product                         # FastAPI + Pydantic do the rest
```

Less code, validated output, automatic docs, and no field can silently leak. Multiply that across every endpoint.

---

## 10. Real-World Use Case — Hiding Internal Fields

Imagine the `Product` model gains an internal `cost` column (what you paid the supplier) that must **never** be exposed to customers:

```python
class Product(Base):
    ...
    cost: Mapped[float]        # internal only!
```

With manual dicts you'd have to remember to omit it everywhere. With `response_model=ProductRead` — which simply doesn't declare `cost` — it's **automatically stripped from every response**. The output schema is a hard boundary. That safety is the real reason separation matters in production.

---

## 11. Mini Task

`main.py` is the Lesson 22 Products API rebuilt with schemas + `response_model`.

1. Run it: `uvicorn main:app --reload` → open `/docs`.
2. In Swagger, notice each endpoint now shows a precise **response schema** (not a generic object).
3. Try:
   - `POST /suppliers`, then `POST /products` → response matches `ProductRead` (includes `id`, **no** internal `cost`).
   - `GET /products/{id}/full` → response embeds the nested `supplier`.
   - `PATCH /products/{id}` with only `{"price": 9.99}` → only price changes (`exclude_unset`).
   - Try to send `id` in a `POST /products` body → it's **ignored** (not in `ProductCreate`).
4. Open the model in `main.py`: the `Product` has a `cost` column. Confirm it **never** appears in any response — that's `response_model` filtering.
5. **Bonus:**
   - Add a `SupplierWithProducts` schema that nests `products: list[ProductRead]`, and an endpoint `GET /suppliers/{id}/full` returning it.
   - Add a `ProductRead`-style field the model doesn't have and watch FastAPI raise on response validation — proof the output is validated.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Returning an ORM object without `from_attributes=True` | Add `model_config = ConfigDict(from_attributes=True)` to the read schema. |
| Using one schema for input and output | Split into `Create` / `Read` / `Update`. |
| Letting clients send `id` | Keep `id` out of `Create`; only `Read` has it. |
| Overwriting fields with `None` on partial update | Use `model_dump(exclude_unset=True)`. |
| Exposing internal columns | Declare only public fields on the `Read` schema; `response_model` strips the rest. |
| Forgetting `response_model` on list endpoints | Use `response_model=list[XxxRead]`. |

---

## 13. Key Takeaways

- **Model ≠ Schema.** SQLAlchemy models store data; Pydantic schemas define the API contract. Keep them separate.
- **`from_attributes=True`** (ORM mode) lets Pydantic build a schema from an ORM object's attributes.
- **`response_model=`** makes FastAPI serialize, **filter**, validate, and document responses — so you can just `return product`.
- Use the **`Create` / `Read` / `Update`** trio: no `id` on input, `id` on output, all-optional for partial updates.
- **`model_dump(exclude_unset=True)`** applies only the fields the client actually sent (partial `PATCH`).
- **Nested read schemas** serialize relationships and filter the nested object too.
- `response_model` is a **security boundary**: undeclared fields (like an internal `cost`) never leak.

---

## ➡️ Next Lesson

**Lesson 24 — Alembic (Database Migrations)**
- Why `create_all` isn't enough once the schema changes
- `alembic init`, autogenerate, `upgrade`, `downgrade`
- Versioning your database schema like you version your code
