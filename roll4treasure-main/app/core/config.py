# /opt/r4t/app/core/config.py
from typing import Optional

try:
    # Pydantic v2+
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field
except Exception:
    # Fallback for Pydantic v1 (not expected here but safe)
    from pydantic import BaseSettings  # type: ignore
    SettingsConfigDict = dict  # type: ignore

    def Field(**kwargs):  # type: ignore
        return None


class Settings(BaseSettings):
    # Core app defaults
    DEBUG: bool = True
    APP_NAME: str = "Roll4Treasure"
    TEMPLATE_DIR: str = "app/templates"
    STATIC_DIR: str = "app/static"

    # Env-provided knobs (these match keys in .env)
    MOXFIELD_COOKIE: Optional[str] = Field(default=None, alias="moxfield_cookie")
    DATABASE_URL: Optional[str] = Field(default=None, alias="database_url")
    IMAGE_CACHE_DIR: str = Field(default="/opt/r4t/img-cache", alias="image_cache_dir")

    # Config for Pydantic v2
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",          # ignore unexpected keys in .env
        case_sensitive=False,    # lowercase keys can populate uppercase fields
        populate_by_name=True,   # allow field names as well as aliases
    )


settings = Settings()
