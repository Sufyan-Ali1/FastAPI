# Lesson 37 — Filtering, Sorting, Searching

> **Goal of this lesson:** Turn a plain list endpoint into a real query API. Learn **filtering** with query parameters, **searching** with case-insensitive partial matching, **sorting** with **safe, whitelisted** fields, and how to **combine** all three with pagination (Lesson 36) into one clean, dynamic query.
>
> `main.py` is a SQLite-backed catalog with a single powerful `GET /products` endpoint; the verification exercises every combination — including the security check that blocks unsafe sort fields.

---

## 1. The Anatomy of a List Endpoint

A production `GET /products` is rarely "return everything." Clients want to **slice** the collection four ways, and a good endpoint supports all of them together:

| Operation | Question it answers | Example |
|---|---|---|
| **Filtering** | "Only rows matching these criteria" | `category=books&in_stock=true` |
| **Searching** | "Rows containing this text" | `q=wireless` |
| **Sorting** | "In this order" | `sort_by=price&order=desc` |
| **Pagination** | "This page of results" (Lesson 36) | `page=2&limit=20` |

```
GET /products?q=wireless&category=electronics&min_price=20&sort_by=price&order=asc&page=1&limit=20
```

These compose: filter down the set, search within it, sort it, then return a page. This lesson is about doing that **cleanly and safely**.

---

## 2. Filtering With Query Parameters

Each filter is an **optional** query parameter. When present, it narrows the result; when absent, it's ignored. Types of filters:

| Filter kind | Query param | SQL |
|---|---|---|
| Exact match | `category=books` | `WHERE category = 'books'` |
| Range (min/max) | `min_price=10&max_price=50` | `WHERE price >= 10 AND price <= 50` |
| Boolean | `in_stock=true` | `WHERE in_stock = true` |
| Multi-value (list) | `tag=a&tag=b` | `WHERE tag IN ('a','b')` |

The key idea: filters are **optional and independent**. You declare each as an optional query param defaulting to `None`, and only apply it if the client sent it.

```python
@app.get("/products")
def list_products(
    category: str | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    in_stock: bool | None = None,
):
    ...
```

---

## 3. Building the Query Dynamically

The clean way to combine an unknown mix of filters is to **start with a base query and conditionally add `.where()` clauses**. SQLAlchemy's `select()` is chainable and immutable-ish, so you build it up:

```python
stmt = select(Product)                                   # base query

if category is not None:
    stmt = stmt.where(Product.category == category)
if min_price is not None:
    stmt = stmt.where(Product.price >= min_price)
if max_price is not None:
    stmt = stmt.where(Product.price <= max_price)
if in_stock is not None:
    stmt = stmt.where(Product.in_stock == in_stock)

rows = db.scalars(stmt).all()
```

Each `if` adds a condition only when that filter was supplied. Multiple `.where()` calls are **AND**-ed together. This scales to any number of filters without a tangle of nested conditionals.

> 🔑 Build queries by **conditionally appending `.where()` clauses** to a base `select()`. This is the standard, readable pattern for dynamic filtering — far better than string-building SQL (which is also a SQL-injection risk).

---

## 4. Searching — Case-Insensitive Partial Matching

**Filtering** is exact ("category equals books"); **searching** is fuzzy ("name *contains* wireless, any case"). Use `ilike` (case-insensitive `LIKE`) with `%` wildcards:

```python
if q:
    term = f"%{q}%"
    stmt = stmt.where(
        Product.name.ilike(term) | Product.description.ilike(term)   # search MULTIPLE fields
    )
```

- **`ilike`** — case-insensitive (`Wireless` matches `wireless`).
- **`%term%`** — matches the term anywhere in the string (partial match).
- The `|` (OR) searches **multiple fields** — a hit in name *or* description counts.

> 🔑 **Filter vs search:** a filter narrows by an exact/known value (`category=books`); a search does fuzzy text matching across one or more fields (`q=wireless`). Offer both — they answer different questions.

---

## 5. Sorting — And the Security Trap

Sorting takes two params: **which field** (`sort_by`) and **which direction** (`order`). The naive implementation is a **serious security hole**:

```python
# ❌ NEVER do this - user input straight into the query
stmt = stmt.order_by(text(sort_by + " " + order))
```

Letting the client put arbitrary text into `ORDER BY` allows **SQL injection** and lets them order by (and probe) columns you never meant to expose. The fix is a **whitelist**: map allowed sort keys to real columns, and reject anything else.

```python
SORTABLE = {                     # the ONLY fields a client may sort by
    "name": Product.name,
    "price": Product.price,
    "created_at": Product.created_at,
}

def apply_sort(stmt, sort_by: str, order: str):
    column = SORTABLE.get(sort_by)
    if column is None:
        raise HTTPException(400, f"Cannot sort by '{sort_by}'")
    return stmt.order_by(column.desc() if order == "desc" else column.asc())
```

- The client's `sort_by` is a **key into a dict you control**, never raw column text.
- An unknown `sort_by` → `400`, not a leaked column or an injection.
- Constrain `order` to `asc`/`desc` (an enum or a validated value).

> 🔑 **Never interpolate a client's sort field into the query.** Whitelist sortable fields via a dict mapping safe keys → columns. This is the single most important security point in this lesson.

---

## 6. Putting It All Together

The full pattern: filter → search → sort → paginate, in that order, on one `select()`:

```python
@app.get("/products")
def list_products(db: DB, q=None, category=None, min_price=None, max_price=None,
                  in_stock=None, sort_by="created_at", order="desc",
                  page=1, limit=20):
    stmt = select(Product)

    # 1. FILTER
    if category is not None: stmt = stmt.where(Product.category == category)
    if min_price is not None: stmt = stmt.where(Product.price >= min_price)
    if max_price is not None: stmt = stmt.where(Product.price <= max_price)
    if in_stock is not None: stmt = stmt.where(Product.in_stock == in_stock)

    # 2. SEARCH
    if q:
        term = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(term) | Product.description.ilike(term))

    # 3. COUNT (of the filtered/searched set, before paginating)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    # 4. SORT (whitelisted)
    stmt = apply_sort(stmt, sort_by, order)

    # 5. PAGINATE
    stmt = stmt.offset((page - 1) * limit).limit(limit)

    rows = db.scalars(stmt).all()
    return {"items": [...], "total": total, "page": page, "limit": limit,
            "filters_applied": {...}}
```

Order matters: filtering and searching define the result **set**; the **count** is taken over that set; sorting orders it; pagination slices it. Get the count **after** filtering but **before** paginating, or `total` will be wrong.

> 🔑 The pipeline is **filter → search → count → sort → paginate**, all on the same `select()`. `total` reflects the filtered set, not the whole table.

---

## 7. Echoing What Was Applied

A professional list response tells the client **what filters were actually applied** (you saw `filters_applied` in the Phase 1 assignments). It aids debugging and makes the API self-describing:

```json
{
  "items": [ ... ],
  "total": 42, "page": 1, "limit": 20,
  "filters_applied": {
    "q": "wireless", "category": "electronics",
    "min_price": 20, "sort_by": "price", "order": "asc"
  }
}
```

---

## 8. Performance Notes

Filtering/sorting/searching hits the database, so at scale:

- **Index** the columns you filter and sort on frequently. An unindexed `WHERE`/`ORDER BY` scans the whole table.
- **Leading-wildcard `ILIKE '%term%'` can't use a normal index** — it scans. Fine for modest data; for serious search use **full-text search** (Postgres `tsvector`, or a search engine like Elasticsearch/Meilisearch). That's beyond this lesson, but know `ilike` doesn't scale to millions of rows.
- Combine with **cursor pagination** (Lesson 36) on large datasets rather than deep offsets.

> 💡 `ILIKE '%...%'` is perfect for learning and small/medium tables. When "search" becomes a core, high-volume feature, graduate to real full-text search.

---

## 9. Real-World Use Case — A Product Catalog

An e-commerce catalog page: the shopper types "wireless" in the search box, ticks "In stock," sets a price slider to $20–$100, picks "Sort by price: low to high," and browses page 2. That single interaction is:

```
GET /products?q=wireless&in_stock=true&min_price=20&max_price=100&sort_by=price&order=asc&page=2&limit=24
```

One endpoint, one dynamically-built query, one consistent response. Every filter is optional, the sort is whitelisted (the shopper can't inject `ORDER BY secret_cost`), and the results are paginated. This is the backbone of virtually every "browse" or "search results" screen.

---

## 10. Mini Task

`main.py` seeds a catalog and exposes one powerful `GET /products`.

1. Run: `uvicorn main:app --reload` → open `/docs`.
2. Try combinations:
   - `?category=electronics` (filter)
   - `?q=wireless` (search — case-insensitive, matches name or description)
   - `?min_price=20&max_price=100` (range)
   - `?in_stock=true` (boolean)
   - `?sort_by=price&order=asc` (sort)
   - all at once, plus `page`/`limit`.
3. **Try to break sorting:** `?sort_by=secret` or `?sort_by=id;DROP TABLE` → confirm a clean `400`, never an error or a leaked column.
4. Inspect `filters_applied` in the response.
5. **Experiment:**
   - Add a `tags` multi-value filter (`?tag=a&tag=b`) using `IN`.
   - Add a `min_rating` filter.
   - Make search also match a `sku` field.
6. **Bonus:** Switch the pagination to cursor-based (Lesson 36) while keeping all the filters.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Interpolating `sort_by` into the query | Whitelist sortable fields via a dict; reject unknowns with `400`. |
| Building SQL with string concatenation | Use SQLAlchemy expressions / parameters (injection-safe). |
| Counting before filtering | Take `total` over the filtered set, before pagination. |
| Case-sensitive search | Use `ilike`, not `like`. |
| Required filters that should be optional | Default filters to `None` and apply only if present. |
| Unbounded `limit` / no default sort | Cap `limit` (Lesson 36); pick a stable default `order_by`. |
| Assuming `ILIKE '%x%'` scales | It scans; use full-text search for large, search-heavy data. |

---

## 12. Key Takeaways

- A real list endpoint combines **filtering + searching + sorting + pagination** on one query.
- **Filter** = exact/range/boolean/multi-value via optional query params; apply each only if present.
- Build the query **dynamically** by conditionally appending `.where()` clauses to a base `select()`.
- **Search** = case-insensitive partial matching with `ilike('%term%')`, often across **multiple fields** with `OR`.
- **Sort** must be **whitelisted**: map safe keys → columns; **never** put client text into `ORDER BY` (SQL-injection / column-exposure risk).
- Pipeline order: **filter → search → count → sort → paginate**; `total` reflects the filtered set.
- **Echo `filters_applied`** for a self-describing API.
- Index filtered/sorted columns; `ILIKE '%...%'` doesn't scale — use full-text search for heavy search.

---

## ➡️ Next Lesson

**Lesson 38 — Internationalization (i18n)** *(optional)*
- Serving responses/messages in multiple languages
- `Accept-Language` negotiation
- Where i18n belongs in an API
