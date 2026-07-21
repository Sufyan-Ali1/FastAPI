"""
config.py - typed, validated application settings via pydantic-settings.

This is the production version of Lesson 44's core/config.py stub. Values come
from environment variables and/or a .env file, are TYPE-CONVERTED and VALIDATED,
and required fields (no default) must be provided or the app won't start.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",          # load a local .env automatically (if present)
        env_file_encoding="utf-8",
        extra="ignore",           # ignore unrelated env vars
        case_sensitive=False,     # DATABASE_URL env -> database_url field
    )

    # --- Optional (have defaults) ---
    app_name: str = "Lesson 45 - Config API"
    environment: str = "dev"                    # "dev" | "staging" | "prod"
    debug: bool = False                         # "true"/"1"/"yes" -> True
    port: int = 8000                            # "8000" -> int 8000
    allowed_origins: list[str] = []             # JSON/CSV in env -> list

    # --- Required (NO default) -> must be provided via env or .env ---
    database_url: str
    secret_key: str

    @field_validator("environment")
    @classmethod
    def valid_environment(cls, v: str) -> str:
        allowed = {"dev", "staging", "prod"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v

    @field_validator("secret_key")
    @classmethod
    def secret_long_enough(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    # Cached: built once, reads env/.env a single time. Tests can override this.
    return Settings()
