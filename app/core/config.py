from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvName = Literal["development", "staging", "production", "test"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """
    Centralized application configuration (Pydantic v2 + pydantic-settings).

    Loads values from:
      1) Environment variables
      2) `.env` file in project root
    """

    # ---- App basics ----
    ENV: EnvName = Field(default="development", description="Runtime environment")
    DEBUG: bool = Field(default=False, description="Enable debug features")
    LOG_LEVEL: LogLevel = Field(default="INFO", description="Root logger level")
    APP_NAME: str = Field(default="Roll4Treasure", description="Application name")
    TEMPLATE_DIR: str = Field(default="app/templates", description="Jinja templates directory")
    STATIC_DIR: str = Field(default="app/static", description="Static files directory")

    # ---- Web server ----
    HOST: str = Field(default="127.0.0.1", description="Uvicorn bind address")
    PORT: int = Field(default=8000, description="Uvicorn bind port")

    # ---- Database ----
    DATABASE_URL: str = Field(default="", description="Postgres DSN")
    DB_MIN_SIZE: int = Field(default=1, ge=1, description="Pool minimum size")
    DB_MAX_SIZE: int = Field(default=5, ge=1, description="Pool maximum size")
    DB_CONNECT_TIMEOUT: float = Field(default=5.0, ge=0.1, description="Connect timeout seconds")

    # ---- Caching / files ----
    IMAGE_CACHE_DIR: str = Field(default="img-cache", description="Local cache folder")

    # ---- Pydantic settings meta ----
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


# Eager singleton used throughout the app
settings = Settings()


def configure_root_logger() -> None:
    """Apply LOG_LEVEL from settings to the root logger (idempotent)."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.getLogger().setLevel(level)
