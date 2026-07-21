"""
Lesson 38 - Internationalization (i18n)   [optional]
----------------------------------------------------
A stdlib-only i18n demo (no Babel/gettext needed) showing:

    - negotiating a language from the Accept-Language header (respecting q-weights)
    - an optional ?lang override that takes priority
    - a keyed translation catalog with fallback to the default locale
    - localized ERROR messages that still return a stable machine `error_code`

Production apps use gettext / Babel with .po files (see theory.md); this file
keeps it dependency-free so it runs anywhere.

    pip install fastapi uvicorn

How to run (from inside this folder):

    uvicorn main:app --reload

Try:
    curl -H "Accept-Language: fr" http://127.0.0.1:8000/greeting
    curl "http://127.0.0.1:8000/greeting?lang=es"
    curl -H "Accept-Language: ja" http://127.0.0.1:8000/greeting   # falls back to en
"""

from typing import Annotated

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Lesson 38 - i18n")

SUPPORTED = {"en", "fr", "es"}
DEFAULT = "en"

# Keyed translation catalog: message key -> per-locale text.
TRANSLATIONS = {
    "en": {"welcome": "Welcome!", "not_found": "Item {id} was not found."},
    "fr": {"welcome": "Bienvenue !", "not_found": "L'article {id} est introuvable."},
    "es": {"welcome": "¡Bienvenido!", "not_found": "No se encontró el artículo {id}."},
}


def negotiate_locale(accept_language: str | None, override: str | None = None) -> str:
    """Pick the best supported locale: ?lang override > Accept-Language q-order > default."""
    if override and override.lower() in SUPPORTED:
        return override.lower()
    if not accept_language:
        return DEFAULT
    candidates: list[tuple[str, float]] = []
    for part in accept_language.split(","):
        piece, _, qval = part.strip().partition(";q=")
        lang = piece.split("-")[0].lower()      # "fr-FR" -> "fr"
        try:
            q = float(qval) if qval else 1.0
        except ValueError:
            q = 1.0
        candidates.append((lang, q))
    # Highest q-weight supported language wins.
    for lang, _ in sorted(candidates, key=lambda c: c[1], reverse=True):
        if lang in SUPPORTED:
            return lang
    return DEFAULT


def t(key: str, locale: str, **kwargs) -> str:
    """Translate a key, falling back to the default locale if missing."""
    text = TRANSLATIONS.get(locale, {}).get(key) or TRANSLATIONS[DEFAULT][key]
    return text.format(**kwargs)


# Dependency: resolve the request's locale once, inject it everywhere.
def get_locale(
    accept_language: Annotated[str | None, Header()] = None,
    lang: str | None = None,
) -> str:
    return negotiate_locale(accept_language, lang)


Locale = Annotated[str, Depends(get_locale)]


# A domain error that carries a stable code; the handler localizes the message.
class LocalizedError(Exception):
    def __init__(self, status_code: int, code: str, **params):
        self.status_code = status_code
        self.code = code
        self.params = params


@app.exception_handler(LocalizedError)
async def localized_error_handler(request: Request, exc: LocalizedError):
    locale = negotiate_locale(
        request.headers.get("accept-language"),
        request.query_params.get("lang"),
    )
    return JSONResponse(
        status_code=exc.status_code,
        # Return BOTH: a stable code for machines + localized text for humans.
        content={"error_code": exc.code, "message": t(exc.code, locale, **exc.params)},
    )


@app.get("/")
def root():
    return {"message": "i18n demo. Send Accept-Language or ?lang=.",
            "supported": sorted(SUPPORTED), "default": DEFAULT}


@app.get("/greeting")
def greeting(locale: Locale):
    return {"locale": locale, "message": t("welcome", locale)}


@app.get("/items/{item_id}")
def get_item(item_id: int, locale: Locale):
    # Pretend every item is missing, to demonstrate a localized error.
    raise LocalizedError(404, "not_found", id=item_id)
