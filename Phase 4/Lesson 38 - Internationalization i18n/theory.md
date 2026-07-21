# Lesson 38 — Internationalization (i18n) *(optional)*

> **Goal of this lesson:** Serve an API that can speak more than one language. Learn what **i18n** means for a *backend*, the key architectural decision (**does the API or the frontend translate?**), how to negotiate a language from the **`Accept-Language`** header, and how to organize **translation catalogs** — plus the honest guidance on what an API should and shouldn't translate.
>
> This is an **optional** lesson. `main.py` is stdlib-only (a translation catalog + `Accept-Language` negotiation) so it runs with no extra installs; production tools (`gettext`, **Babel**) are covered in theory.

---

## 1. What i18n Means for an API

**Internationalization (i18n)** = designing software so it *can* be adapted to different languages/regions. **Localization (l10n)** = actually adapting it to a specific one (translating strings, formatting dates/currency).

> "i18n" and "l10n" are numeronyms: **i-18-letters-n** and **l-10-letters-n**.

For a **backend API**, i18n mostly touches:

- **User-facing messages** the API returns — error messages, notifications, status labels.
- **Locale-aware formatting** — dates, numbers, currency (`1,234.56` vs `1.234,56`).
- **Content** stored in multiple languages (a product description in English and French).

It does **not** mean translating your JSON field names, enum values, or IDs — those are a machine contract, not human text.

---

## 2. The Key Architectural Question — Who Translates?

Before any code, decide **where translation happens**. There are two valid models:

| Model | The API returns | The client does | Best when |
|---|---|---|---|
| **A. Frontend translates** | Machine-readable **codes** (`"error.insufficient_funds"`) | Looks up the code in its own translation files | You control the frontend; many locales; UI-heavy apps |
| **B. API translates** | **Localized text** (`"Insufficient funds"` / `"Fonds insuffisants"`) | Displays it as-is | Many/unknown clients (mobile, third parties); emails/SMS; server-rendered text |

```
Model A (codes):     API → {"error_code": "insufficient_funds"}  → frontend picks the language
Model B (text):      API → {"message": "Fonds insuffisants"}     → client shows it directly
```

> 🔑 **Prefer returning stable codes (Model A) when you own the frontend** — it keeps the API language-agnostic and puts translation where the UI already lives. Use **Model B (server-side translation)** for messages the server itself emits to humans (emails, SMS, notifications) or for many uncontrolled clients. Many real apps do **both**: a code *and* a default localized message.

This lesson focuses on **Model B** mechanics (the API translating), because that's the part FastAPI is involved in — but keep Model A in mind as often the better default.

---

## 3. The `Accept-Language` Header

Browsers and clients announce their language preferences with the **`Accept-Language`** request header, using **quality values (`q`)** to rank them:

```
Accept-Language: fr-FR,fr;q=0.9,en;q=0.8,de;q=0.5
```

Read as: "I prefer French (France), then French, then English, then German." The `q` (0–1, default 1) is the preference weight; the server picks the **highest-`q` language it supports.**

Clients can also let users override via a query param (`?lang=fr`) or a stored preference — those usually take priority over the header.

> 🔑 `Accept-Language` is a **ranked preference list**, not a single value. Parse it, sort by `q`, and match against the languages you actually support — falling back to a default if none match.

---

## 4. Locale Negotiation

The negotiation logic: parse the header → order candidates by `q` → return the first one your API supports → else the default.

```python
SUPPORTED = {"en", "fr", "es"}
DEFAULT = "en"

def negotiate_locale(accept_language: str | None, override: str | None = None) -> str:
    if override in SUPPORTED:                 # explicit ?lang wins
        return override
    if not accept_language:
        return DEFAULT
    # parse "fr-FR,fr;q=0.9,en;q=0.8" -> [("fr", 1.0), ("en", 0.8), ...]
    candidates = []
    for part in accept_language.split(","):
        piece, _, qval = part.strip().partition(";q=")
        lang = piece.split("-")[0].lower()    # "fr-FR" -> "fr"
        q = float(qval) if qval else 1.0
        candidates.append((lang, q))
    for lang, _ in sorted(candidates, key=lambda c: c[1], reverse=True):
        if lang in SUPPORTED:
            return lang
    return DEFAULT
```

In FastAPI, wrap this in a **dependency** so every endpoint can just ask for the resolved locale:

```python
def get_locale(accept_language: str | None = Header(None), lang: str | None = None) -> str:
    return negotiate_locale(accept_language, lang)

Locale = Annotated[str, Depends(get_locale)]
```

> 💡 Reading `Accept-Language` uses the `Header()` parameter from Lesson 18. Putting negotiation in a dependency (Lesson 14) means one place decides the language for the whole request.

---

## 5. Translation Catalogs

A **catalog** maps a **message key** to its translation in each locale. Never scatter raw strings through your code — key them:

```python
TRANSLATIONS = {
    "en": {"welcome": "Welcome", "not_found": "Item not found"},
    "fr": {"welcome": "Bienvenue", "not_found": "Article introuvable"},
    "es": {"welcome": "Bienvenido", "not_found": "Artículo no encontrado"},
}

def t(key: str, locale: str) -> str:
    return TRANSLATIONS.get(locale, {}).get(key) or TRANSLATIONS["en"][key]  # fallback
```

- Code references a **stable key** (`"not_found"`), not the English text.
- A missing translation **falls back** to the default locale, never crashes.

### Production tooling — `gettext` / Babel

Hand-written dicts are fine for a few strings. Real apps use the **`gettext`** standard with **`.po`/`.mo`** files, managed by **Babel**:

- Translators edit `.po` files (a standard format they have tools for).
- `pybabel extract` pulls translatable strings from your code (marked with `_( "...")`).
- Babel also does **locale-aware formatting** of dates, numbers, and currency, and **pluralization**.

> 🔑 Start with a keyed catalog + a fallback. Graduate to **Babel/gettext (`.po` files)** when you have real translators and many strings — it's the industry standard and handles plurals and formatting the dict approach can't.

---

## 6. Localizing Error Messages

The most common API i18n need: error responses in the user's language. Resolve the locale, then translate in a **custom exception handler** (Lesson 13):

```python
@app.exception_handler(LocalizedError)
async def localized_handler(request: Request, exc: LocalizedError):
    locale = negotiate_locale(request.headers.get("accept-language"))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.code, "message": t(exc.code, locale)},  # code + text
    )
```

Returning **both** an `error_code` and a localized `message` gives clients the best of both models: machines branch on the stable code, humans read the translated text.

---

## 7. Locale-Aware Formatting

Translation is only half of localization. **Formatting** differs by locale too:

| | `en-US` | `fr-FR` | `de-DE` |
|---|---|---|---|
| Number | `1,234.56` | `1 234,56` | `1.234,56` |
| Currency | `$1,234.56` | `1 234,56 €` | `1.234,56 €` |
| Date | `07/21/2026` | `21/07/2026` | `21.07.2026` |

Doing this by hand is error-prone; **Babel** formats numbers, currency, dates, and percentages per locale:

```python
from babel.numbers import format_currency   # if using Babel
format_currency(1234.56, "EUR", locale="fr_FR")   # -> "1 234,56 €"
```

> 💡 For an API, prefer returning **raw machine values** (`1234.56`, an ISO `2026-07-21` date) and let the **frontend format** for the locale — it's simpler and unambiguous. Server-side locale formatting matters mainly for text the server itself renders (emails, PDFs, SMS).

---

## 8. What to Translate — and What Not To

| Translate | Don't translate |
|---|---|
| User-facing **messages** (errors, notifications) | JSON **field names** (`price`, not `prix`) |
| **Labels** shown to end users | **Enum values** / status codes (`"pending"`, not `"en attente"`) |
| Emails/SMS/PDFs the server generates | **IDs, slugs, keys** (machine identifiers) |
| Multi-language **content** (stored per locale) | **Log messages** (keep logs in one language) |

> 🔑 Translate what a **human reads**; keep the **machine contract** (field names, enums, ids, codes) in one canonical language. Translating your API's structure breaks clients.

---

## 9. Related-But-Separate Concerns

i18n is often confused with things that are actually independent:

- **Timezones** — store and transmit UTC; convert for display. A user's language ≠ their timezone.
- **Pluralization** — "1 item" vs "2 items" varies by language (some have many plural forms). gettext/Babel handle plural rules; naive string concatenation doesn't.
- **RTL languages** (Arabic, Hebrew) — a rendering/UI concern, not an API one.
- **Multi-language content** — storing a product in several languages is a **data-modeling** problem (a translations table), separate from UI-string i18n.

---

## 10. Real-World Use Case — A Global SaaS API

Your SaaS serves users worldwide. Design:

- **Data responses** return machine values and stable enum codes — language-agnostic (`status: "active"`, `amount: 1234.56`). The web/mobile frontends translate labels themselves (Model A).
- **Server-generated messages** — password-reset emails, SMS codes, push notifications — are translated **server-side** to the user's stored locale (Model B), because there's no frontend involved.
- **Error responses** carry both `error_code` and a localized `message`, negotiated from `Accept-Language`, so both API integrators and humans are served.

Same system, each concern handled by the model that fits it — which is the real lesson of API i18n.

---

## 11. Mini Task

`main.py` is a stdlib-only i18n demo (English, French, Spanish).

1. Run: `uvicorn main:app --reload`
2. Negotiate language via the header:
   ```bash
   curl -H "Accept-Language: fr" http://127.0.0.1:8000/greeting
   curl -H "Accept-Language: es-ES,es;q=0.9,en;q=0.5" http://127.0.0.1:8000/greeting
   curl http://127.0.0.1:8000/greeting                 # no header -> default (en)
   ```
3. Override with a query param: `/greeting?lang=fr` (takes priority over the header).
4. Trigger a **localized error**: `/items/999` with different `Accept-Language` headers → the `message` changes but the `error_code` stays constant.
5. **Experiment:**
   - Add a fourth locale (e.g. `de`) to the catalog and confirm negotiation picks it up.
   - Request an unsupported language (`Accept-Language: ja`) and confirm it falls back to `en`.
   - Add a `q`-weighted header where a supported language isn't the first listed, and confirm the highest-`q` *supported* one wins.
6. **Bonus:** Return both `error_code` and localized `message` everywhere, so clients can choose which to use.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Translating field names / enum values | Keep the machine contract in one language; translate only human text. |
| Hardcoding English strings in code | Reference message **keys**; keep text in a catalog. |
| Treating `Accept-Language` as a single value | Parse the ranked list and match by `q` against supported locales. |
| No fallback for a missing translation | Fall back to the default locale, never crash. |
| Confusing language with timezone/currency | They're independent; handle each separately. |
| Naive pluralization by string concat | Use gettext/Babel plural rules. |
| Server-formatting numbers the frontend should format | Return raw values; let the UI format (except server-rendered text). |

---

## 13. Key Takeaways

- **i18n** for an API = translatable **user-facing messages** + locale-aware **formatting**, not translating the machine contract.
- Decide **who translates**: return stable **codes** (frontend translates, Model A) or **localized text** (API translates, Model B) — often both.
- Negotiate language from the **`Accept-Language`** ranked list (respect `q` weights), with an optional `?lang` override and a **default fallback**.
- Put negotiation in a **dependency**; keep strings in a **keyed catalog** with fallback.
- Use **`gettext`/Babel (`.po` files)** for real projects — they handle translators, **pluralization**, and locale **formatting**.
- Localize **error messages** via a custom exception handler; return `error_code` **and** `message`.
- **Translate what humans read; never translate field names, enums, or ids.**
- Keep **timezones, currency, pluralization, and RTL** as separate concerns.

---

## ➡️ Next Lesson

**Lesson 39 — GraphQL with FastAPI** *(optional, via Strawberry)*
- How GraphQL differs from REST
- Queries, mutations, and a single flexible endpoint
- When GraphQL fits (and when REST is still better)
