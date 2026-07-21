"""core/config.py - application configuration.

A simple settings object for now. Lesson 45 upgrades this to `pydantic-settings`
(typed, validated, loaded from environment / .env files). Centralizing config
here means the rest of the app never hardcodes values.
"""

import os


class Settings:
    APP_NAME: str = "Lesson 44 - Layered API"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./app_data.db"
    )
    ITEM_MAX_PRICE: float = 1_000_000.0


settings = Settings()
