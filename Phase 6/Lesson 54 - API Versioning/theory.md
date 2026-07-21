# Lesson 54 — API Versioning

> **Goal of this lesson:** Evolve your API **without breaking existing clients**. Learn what a **breaking change** is, the versioning strategies (URL path, header, media type), how to run **`/api/v1`** and **`/api/v2`** side by side with `APIRouter`, and how to **deprecate** an old version gracefully.
>
> `main.py` serves **v1 and v2 simultaneously** — a real breaking change (splitting `name` into `first_name`/`last_name`) handled across versions, with a deprecation header on v1.

---

## 1. The Problem — Your API Is a Contract

Once clients (a mobile app, a partner integration, another team's service) depend on your API, its shape is a **contract**. If you change the response format or remove a field, **every client that relied on it breaks** — and you often can't force them all to upgrade at once (a mobile app in the App Store, a partner on their own schedule).

```
v1 response the mobile app parses:   {"name": "Ada Lovelace", "email": "..."}
You "improve" it to:                 {"first_name": "Ada", "last_name": "Lovelace", ...}
Result:  every deployed app that reads `name` -> CRASHES
```

**Versioning** lets you introduce breaking changes in a **new** version while keeping the old one running, so clients migrate on *their* timeline.

> 🔑 A public API is a **contract**. You can't break it out from under clients who can't upgrade instantly. Versioning is how you evolve the contract without breaking the people relying on it.

---

## 2. Breaking vs Non-Breaking Changes

The whole decision hinges on this: does the change break existing clients? **Only breaking changes need a new version.**

| ✅ Non-breaking (add to the current version) | ❌ Breaking (needs a new version) |
|---|---|
| **Adding** a new optional field to a response | **Removing** or **renaming** a field |
| **Adding** a new endpoint | **Changing** a field's type or meaning |
| **Adding** an optional query parameter | **Making** an optional param required |
| **Adding** a new enum value (usually) | **Removing** an enum value / endpoint |
| Relaxing a validation rule | **Tightening** validation (rejects what was accepted) |
| Bug fixes that don't change the contract | **Changing** status codes / error shapes |

The rule of thumb: **adding is safe; removing, renaming, or changing meaning is breaking.** A client should tolerate new fields it doesn't recognize (and good clients ignore unknown fields).

> 🔑 **Additive changes are safe** — ship them to the current version. **Removing, renaming, or changing** existing behavior is breaking and needs a new version. Don't version for changes that don't break anyone.

---

## 3. Versioning Strategies

There are several ways to express the version. The main ones:

| Strategy | Looks like | Notes |
|---|---|---|
| **URL path** ⭐ | `/api/v1/users`, `/api/v2/users` | Most common; explicit, easy to route, cache, and browse |
| **Query parameter** | `/api/users?version=2` | Simple but easy to forget; clutters URLs |
| **Custom header** | `X-API-Version: 2` | Clean URLs; less visible/discoverable |
| **Media type (content negotiation)** | `Accept: application/vnd.myapi.v2+json` | "Purest" REST; complex, less common |

**URL path versioning** (`/api/v1/...`) is by far the most common in practice: it's explicit, trivially routable, visible in logs and browsers, and easy to cache separately. This course uses it.

> 🔑 **URL path versioning (`/api/v1`, `/api/v2`)** is the pragmatic default — explicit, easy to route and cache, obvious in logs. Header/media-type versioning is "cleaner" in theory but harder in practice.

---

## 4. Implementing Versions with `APIRouter`

FastAPI makes path versioning natural with **`APIRouter`** (Lesson 16): one router per version, each mounted under its version prefix. Both versions run in the **same app**, side by side:

```python
# v1 router
v1 = APIRouter(prefix="/api/v1", tags=["v1"])

@v1.get("/users/{user_id}")
def get_user_v1(user_id: int):
    return {"id": user_id, "name": "Ada Lovelace", "email": "..."}   # old shape

# v2 router - the breaking change lives here
v2 = APIRouter(prefix="/api/v2", tags=["v2"])

@v2.get("/users/{user_id}")
def get_user_v2(user_id: int):
    return {"id": user_id, "first_name": "Ada", "last_name": "Lovelace", ...}  # new shape

app.include_router(v1)
app.include_router(v2)
```

Now `/api/v1/users/1` returns the old format and `/api/v2/users/1` returns the new one — **simultaneously**. Old clients keep working; new clients use v2. Swagger (`/docs`) shows both, grouped by tag.

> 🔑 Run versions **side by side** with an `APIRouter` per version under a version prefix. Both live in one app; each client hits the version it was built against.

---

## 5. Don't Duplicate Logic Across Versions

Two versions of an endpoint shouldn't mean two copies of the business logic. Keep the logic in a **service** (Lesson 44); each version's route just **shapes the response** differently:

```python
# services/user_service.py - ONE source of truth
def get_user(user_id: int) -> User: ...

# v1 route: shape the old way
@v1.get("/users/{id}")
def get_user_v1(id: int):
    u = user_service.get_user(id)
    return {"id": u.id, "name": f"{u.first} {u.last}", "email": u.email}

# v2 route: shape the new way
@v2.get("/users/{id}")
def get_user_v2(id: int):
    u = user_service.get_user(id)
    return {"id": u.id, "first_name": u.first, "last_name": u.last, "email": u.email}
```

The versions differ only in the **response schema** (often just different Pydantic response models), not the underlying logic. This keeps versions cheap to maintain.

> 🔑 Versions differ in the **API surface** (response shape), not the **logic**. Share the service layer; give each version its own response schema. Duplicating logic per version is how versioning becomes unmaintainable.

---

## 6. Deprecation & Sunset

Running old versions forever is a maintenance burden. The lifecycle: **release v2 → deprecate v1 → give clients time to migrate → remove v1.** Communicate clearly:

- **Announce** the deprecation and a **sunset date** (documentation, changelog, email to API consumers).
- **Signal it in responses** with standard headers so clients notice programmatically:
  ```
  Deprecation: true
  Sunset: Sat, 31 Dec 2026 23:59:59 GMT
  Link: <https://docs.example.com/migrate-v2>; rel="deprecation"
  ```
- **Give a generous window** (months, not days) — clients need time, especially mobile apps and partners.
- **Monitor usage** of the old version; only remove it when traffic is near zero.

> 🔑 Deprecate with **communication + `Deprecation`/`Sunset` headers + a generous migration window**, and monitor usage before removing. Never silently break or abruptly kill a version clients still use.

---

## 7. Versioning and Semantic Versioning

Don't confuse **API versioning** (`/v1`, `/v2` in the URL) with **package versioning** (SemVer: `MAJOR.MINOR.PATCH`). They're related:

- **PATCH** (bug fix) and **MINOR** (additive, backward-compatible) → **no new API version** needed; ship to the current one.
- **MAJOR** (breaking change) → a **new API version** (`/v2`).

Most teams keep API versions **coarse** — a small number of major versions (`v1`, `v2`), not `v1.3.7` in the URL. Minor/patch changes flow into the current version; only breaking changes bump the URL version.

> 🔑 URL versions are **coarse (major only)** — `v1`, `v2`. Additive/bug-fix changes go into the current version; a new URL version is reserved for **breaking** changes.

---

## 8. When *Not* to Version

Versioning has real cost (maintaining multiple code paths). Avoid it when you can:

- **Additive changes** don't need a version — just add the field/endpoint.
- **Internal APIs** you control on both ends can often skip formal versioning (coordinate the change).
- **Early-stage / pre-launch** APIs with no external clients can change freely.
- Prefer **evolving compatibly** (add, don't remove) over minting a new version whenever possible.

> 💡 The best versioning is **not needing to version** — design responses to be extensible (clients ignore unknown fields), add rather than remove, and reserve a new version for genuinely breaking changes.

---

## 9. Real-World Use Case — Splitting a Name Field

Your `/api/v1/users` returns `{"name": "Ada Lovelace", ...}`. Product now needs first/last names separately for personalization. That's a **breaking change** (renaming/removing `name`), and a mobile app in the wild parses `name`. So:

- Introduce **`/api/v2/users`** returning `{"first_name": "Ada", "last_name": "Lovelace", ...}`.
- Keep **`/api/v1`** running unchanged; add `Deprecation`/`Sunset` headers pointing to a migration guide.
- Both are served by the **same** user service; only the response schema differs.
- The mobile app keeps using v1 until its next release ships v2 support; new integrations use v2 immediately.
- Months later, when v1 traffic is negligible, you remove it.

No client ever breaks, and the API evolved. That's versioning done right — exactly what `main.py` demonstrates.

---

## 10. Mini Task

`main.py` serves v1 and v2 side by side.

1. Run: `uvicorn main:app --reload` → open `/docs` and note both v1 and v2 endpoints (grouped by tag).
2. Call both and compare the **response shapes**:
   - `GET /api/v1/users/1` → `{"id", "name", "email"}` (old contract).
   - `GET /api/v2/users/1` → `{"id", "first_name", "last_name", "email"}` (new contract).
3. Inspect the **v1 response headers** → note `Deprecation: true` and a `Sunset` date.
4. Confirm a change that's *additive* (a new field on v2) wouldn't have needed a new version.
5. **Experiment:**
   - Add a `/api/v2/users` list endpoint that doesn't exist in v1 (additive, version-specific).
   - Move the shared logic into a service function both versions call.
   - Add a `Link` header on v1 pointing to a migration guide.
6. **Bonus:** Add header-based versioning (`X-API-Version`) as an alternative and compare the ergonomics with URL versioning.

---

## 11. Common Mistakes

| Mistake | Fix |
|---|---|
| Versioning for additive changes | Just add the field/endpoint to the current version. |
| Breaking v1 in place | Introduce v2; keep v1 running until clients migrate. |
| Duplicating business logic per version | Share a service; version only the response shape. |
| Removing an old version with no notice | Deprecate with headers + a generous sunset window. |
| Fine-grained URL versions (`/v1.2.3`) | Keep URL versions coarse (major only). |
| No way for clients to detect deprecation | Send `Deprecation`/`Sunset` headers. |
| Never removing old versions | Monitor usage and retire versions once traffic is negligible. |

---

## 12. Key Takeaways

- A public API is a **contract**; breaking it breaks clients who can't upgrade instantly. **Versioning** lets old and new coexist.
- **Only breaking changes need a version** — additive changes (new fields/endpoints/optional params) are safe in the current version.
- **URL path versioning (`/api/v1`, `/api/v2`)** is the pragmatic default; header/media-type versioning is cleaner in theory, harder in practice.
- Run versions **side by side** with an **`APIRouter`** per version; both live in one app.
- **Share the logic** (service layer); version only the **response shape** (per-version schemas) — don't duplicate logic.
- **Deprecate gracefully**: announce, send `Deprecation`/`Sunset` headers, give a generous window, monitor usage, then remove.
- Keep URL versions **coarse** (major only); the best versioning is designing so you rarely need it (add, don't remove).

---

## ➡️ Next Lesson

**Lesson 55 — API Documentation Customization**
- Customizing the OpenAPI schema
- Hiding internal endpoints from the docs
- Adding examples, descriptions, and metadata
