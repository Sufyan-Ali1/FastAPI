# Lesson 36 — Pagination

> **Goal of this lesson:** Serve large collections in **pages** instead of all at once. Learn **limit/offset** pagination (simple, page-numbered), its real problems at scale, and **cursor-based (keyset)** pagination (fast, stable), plus how to design a **consistent paginated response**.
>
> `main.py` is a SQLite-backed API implementing both styles, and the verification demonstrates the offset "drift" bug that cursors fix.

---

## 1. The Problem — Don't Return Everything

`GET /products` on a table with 500,000 rows should **never** return all 500,000. It would:

- Take seconds and a huge payload.
- Exhaust memory on the server and the client.
- Waste bandwidth when the user only looks at the first screen.

**Pagination** returns a small **slice** (a "page") at a time, with a way to fetch the next slice. You've used a basic version since the Phase 1 assignments (`page` + `limit`); this lesson makes it rigorous and adds the scalable variant.

> 🔑 Any list endpoint that can grow unbounded **must** paginate. Returning an entire table is one of the most common backend mistakes.

---

## 2. Limit/Offset Pagination

The most common and intuitive style: **skip N rows, take M rows.**

```
GET /items?page=1&limit=20     -> rows 1–20     (OFFSET 0,  LIMIT 20)
GET /items?page=2&limit=20     -> rows 21–40    (OFFSET 20, LIMIT 20)
GET /items?page=3&limit=20     -> rows 41–60    (OFFSET 40, LIMIT 20)
```

The math: `offset = (page - 1) * limit`. In SQL / SQLAlchemy:

```python
offset = (page - 1) * limit
stmt = select(Item).order_by(Item.id).offset(offset).limit(limit)
rows = db.scalars(stmt).all()
```

`ORDER BY` is **mandatory** — without a stable sort, "page 2" is meaningless because the database doesn't guarantee row order.

### 2.1 A consistent offset response

Return the page **plus** the metadata the client needs to build a pager:

```json
{
  "items": [ ... 20 items ... ],
  "page": 2,
  "limit": 20,
  "total": 1543,
  "total_pages": 78,
  "has_next": true,
  "has_prev": true
}
```

> 🔑 Offset pagination's superpower is **random access**: you can jump straight to page 50. That's why UIs with numbered page buttons use it.

---

## 3. The Problems With Offset

Offset is simple but has two real weaknesses at scale.

### 3.1 Deep offset is slow

`OFFSET 100000 LIMIT 20` forces the database to **scan and discard** the first 100,000 rows before returning 20. The deeper the page, the slower the query — offset pagination gets **linearly slower** as users page further in.

```
OFFSET 0      -> fast
OFFSET 100000 -> the DB counts through 100,000 rows first, then returns 20
```

### 3.2 Drift — skipped and duplicated rows

If rows are **inserted or deleted** while a user pages, offsets shift under them:

```
Page 1 (offset 0, limit 3):  [A, B, C]
   ... a new row X is inserted at the top ...
Page 2 (offset 3, limit 3):  [C, D, E]   <- C appears AGAIN (was pushed down)
```

Because "skip 3" now points at a different row than before, the user sees a **duplicate** (or, on deletion, a **skipped** row). On a busy, frequently-changing dataset this is a genuine correctness bug.

> 🔑 Offset pagination is fine for **small or slowly-changing** datasets and for UIs needing numbered pages. It degrades on **deep pages** and **high-churn** data — that's exactly what cursor pagination fixes.

---

## 4. Cursor-Based (Keyset) Pagination

Instead of "skip N rows," cursor pagination says **"give me rows *after* this specific point."** The "point" is a **cursor** — usually the value of a stable, ordered column (the last row's `id` or `created_at`).

```
Page 1:  SELECT ... WHERE id > 0     ORDER BY id LIMIT 20   -> last id = 20
Page 2:  SELECT ... WHERE id > 20    ORDER BY id LIMIT 20   -> last id = 40
Page 3:  SELECT ... WHERE id > 40    ORDER BY id LIMIT 20
```

```python
stmt = select(Item).order_by(Item.id).limit(limit)
if cursor is not None:
    stmt = stmt.where(Item.id > cursor)      # start AFTER the cursor
rows = db.scalars(stmt).all()
next_cursor = rows[-1].id if rows else None
```

### 4.1 Why it fixes both problems

- **Fast at any depth:** `WHERE id > 40 LIMIT 20` uses the index to jump straight to the right spot — no scanning-and-discarding. Performance is **constant** regardless of how deep you are.
- **Stable under inserts/deletes:** the cursor points at a **specific row's value**, not a positional offset. New rows inserted elsewhere don't shift what "after id 40" means — **no duplicates, no skips.**

### 4.2 The cursor response shape

```json
{
  "items": [ ... 20 items ... ],
  "next_cursor": "NDA=",       // opaque token; pass it back to get the next page
  "has_more": true
}
```

The client just keeps sending back the `next_cursor` until `has_more` is false. Note there's usually **no `total` and no page numbers** — cursor pagination trades random access for speed and stability.

### 4.3 Opaque cursors

The cursor is often **base64-encoded** so clients treat it as an **opaque token** rather than a meaningful id they might tamper with:

```python
import base64
def encode_cursor(value: int) -> str:
    return base64.urlsafe_b64encode(str(value).encode()).decode()
def decode_cursor(token: str) -> int:
    return int(base64.urlsafe_b64decode(token).decode())
```

Encoding it means you can later change what's *inside* the cursor (e.g. switch from `id` to a `(created_at, id)` tuple) without breaking clients.

---

## 5. Offset vs Cursor — The Comparison

| | **Limit/Offset** | **Cursor (Keyset)** |
|---|---|---|
| Jump to any page | ✅ Yes (page 50 directly) | ❌ No (only next/prev) |
| Performance on deep pages | ❌ Degrades (scans skipped rows) | ✅ Constant (index seek) |
| Stable under inserts/deletes | ❌ No (drift) | ✅ Yes |
| Total count / page numbers | ✅ Natural | ❌ Usually omitted |
| Complexity | Simple | Slightly more |
| Best for | Admin tables, small data, numbered UIs | Feeds, infinite scroll, big/real-time data |

> 🔑 **Offset for page-numbered UIs on modest data; cursor for infinite scroll, feeds, and large/high-churn datasets.** Twitter/Instagram-style "load more" is cursor pagination; a paginated admin table is usually offset.

---

## 6. The Cost of `total`

Clients often want a **total count** ("1,543 results, page 2 of 78"). But `SELECT COUNT(*)` over a big, filtered table can be **as expensive as the page query itself** — and on very large tables it's a real performance drain.

Options:
- **Offset + total** — fine for modest data; run a `COUNT(*)` alongside the page.
- **Skip the total** — cursor pagination usually omits it (there's no page number anyway).
- **Approximate total** — some systems show "about 10,000 results" from DB statistics.

> 💡 Don't reflexively return `total`. If it's expensive and the UI doesn't need exact counts, omit it or approximate it.

---

## 7. Consistent API Design

Whatever style you choose, be **consistent** across your API:

- Validate `limit` with sane bounds (e.g. `1 ≤ limit ≤ 100`) and a default — never let a client request `limit=1000000`.
- Always `ORDER BY` a **stable, unique** key (add `id` as a tiebreaker if sorting by a non-unique column like `created_at`).
- Use the **same response envelope** for every list endpoint so clients learn it once.
- Document which style each endpoint uses.

```python
limit: int = Query(20, ge=1, le=100)     # bounded, with a default
page: int = Query(1, ge=1)
```

> 🔑 Cap `limit`, always order by a unique key, and return a **uniform paginated shape**. Inconsistent pagination across endpoints is a common source of frontend bugs.

---

## 8. Real-World Use Case — Feed vs Admin Table

**Social feed** (`GET /feed`): infinite scroll, new posts constantly inserted at the top, potentially millions of rows. Offset would drift (users see duplicates as new posts arrive) and slow down deep in the feed. → **Cursor pagination** keyed on post id/timestamp: fast at any depth, no duplicates as new posts arrive.

**Admin orders table** (`GET /admin/orders`): a back-office UI with "Page 3 of 40" buttons, moderate row count, changes slowly. Users want to jump to a specific page. → **Offset pagination** with a `total` count.

Same app, two endpoints, two pagination styles chosen by their access pattern.

---

## 9. Mini Task

`main.py` seeds a SQLite table and exposes both pagination styles.

1. Run: `uvicorn main:app --reload` → open `/docs`.
2. **Offset:** `GET /items?page=1&limit=5`, then `page=2`, `page=3`. Note `total`, `total_pages`, `has_next`.
3. **Cursor:** `GET /items/cursor?limit=5` → note `next_cursor`. Call again with `?cursor=<that value>` → the next 5. Repeat until `has_more` is false.
4. **See the drift bug:** the verification (below) shows offset skipping/duplicating a row when data is inserted mid-pagination, while cursor stays correct.
5. **Experiment:**
   - Request `limit=99999` and confirm validation caps it.
   - Page deep into offset and reason about why it would slow down on a huge table.
   - Change the cursor to encode `created_at` instead of `id`.
6. **Bonus:** Add `has_prev` and a `prev_cursor` for bidirectional cursor paging.

---

## 10. Common Mistakes

| Mistake | Fix |
|---|---|
| No `ORDER BY` | Pagination is undefined without a stable order; always order by a unique key. |
| Unbounded `limit` | Cap it (`le=100`) with a sensible default. |
| Using offset for infinite scroll on churny data | Use cursor pagination to avoid drift. |
| Returning `total` when it's expensive and unused | Omit or approximate it. |
| Ordering by a non-unique column only | Add `id` as a tiebreaker for a stable order. |
| Exposing a raw DB id as the cursor | Base64-encode it as an opaque token. |
| Inconsistent response shapes across endpoints | Standardize one paginated envelope. |

---

## 11. Key Takeaways

- **Paginate every unbounded list.** Return a page + metadata, never the whole table.
- **Limit/offset**: `offset = (page-1)*limit`; simple, supports **random page access** and totals. Weak on **deep pages** (slow) and **inserts/deletes** (drift → duplicates/skips).
- **Cursor/keyset**: `WHERE key > cursor ORDER BY key LIMIT n`; **constant speed at any depth** and **stable** under churn, but only next/prev (no page jumps), usually no total.
- Cursors are typically **opaque (base64)** tokens over a stable, unique ordered key.
- **`total` counts can be expensive** — don't return them reflexively.
- Always **`ORDER BY` a unique key**, **cap `limit`**, and use a **consistent paginated shape**.
- **Offset for numbered admin UIs; cursor for feeds/infinite scroll and large, high-churn data.**

---

## ➡️ Next Lesson

**Lesson 37 — Filtering, Sorting, Searching**
- Query-parameter filtering and multi-field search
- Dynamic sorting with safe, whitelisted fields
- Combining filters, sort, and pagination cleanly
