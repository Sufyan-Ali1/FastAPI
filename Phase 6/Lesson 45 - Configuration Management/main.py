"""
Lesson 45 - Configuration Management
------------------------------------
A FastAPI app whose configuration comes from environment variables / a .env
file via pydantic-settings - typed, validated, and centralized.

Setup:

    pip install fastapi uvicorn pydantic-settings
    cp .env.example .env       # then edit values (Windows: copy .env.example .env)
    uvicorn main:app --reload

Then GET /config to see the loaded (non-secret) settings.
"""

from typing import Annotated

from fastapi import Depends, FastAPI

from config import Settings, get_settings

# Read config ONCE at startup. If required fields (database_url, secret_key) are
# missing or invalid, the app FAILS HERE - loudly, at startup, not at runtime.
settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.get("/")
def root():
    return {"app": settings.app_name, "environment": settings.environment}


@app.get("/config")
def show_config(cfg: Annotated[Settings, Depends(get_settings)]):
    # Expose only NON-SECRET settings. Never return secret_key.
    return {
        "app_name": cfg.app_name,
        "environment": cfg.environment,
        "debug": cfg.debug,
        "port": cfg.port,
        "allowed_origins": cfg.allowed_origins,
        "database_url_scheme": cfg.database_url.split(":", 1)[0],  # scheme only
        "secret_key_configured": bool(cfg.secret_key),             # boolean, not the value
    }
