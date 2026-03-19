"""Application configuration via pydantic-settings.

Loads settings from environment variables and an optional .env file.
All configuration is centralized here and accessed via ``get_settings()``.
"""

from __future__ import annotations

import functools
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root application settings loaded from the environment.

    Attributes mirror the keys in ``.env.example``.  Defaults are chosen so
    that the application can start locally with minimal configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://arxiv:arxiv@localhost:5432/arxiv_digest"

    # ── Authentication ──────────────────────────────────────────────────
    API_KEY: SecretStr = SecretStr("change-me-to-a-secure-random-string")

    # ── Cache ───────────────────────────────────────────────────────────
    CACHE_DIR: Path = Path(".cache")

    # ── Webhooks ────────────────────────────────────────────────────────
    WEBHOOK_URLS: list[str] = []

    # ── Logging ─────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── CORS ────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]

    # ── Topics ──────────────────────────────────────────────────────────
    TOPICS_FILE: Path = Path("config/topics.yaml")

    # ── Application metadata ────────────────────────────────────────────
    APP_NAME: str = "arxiv-research-digest"
    APP_VERSION: str = "2.0.0"


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings.

    The result is cached so that repeated calls (e.g. FastAPI dependency
    injection) always return the same instance without re-reading the
    environment.
    """
    return Settings()
