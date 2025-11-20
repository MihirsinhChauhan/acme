"""Application configuration loaded from environment variables."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central place for strongly typed application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Acme Import Service")
    environment: Literal["development", "staging", "production"] = Field(default="development")
    api_prefix: str = Field(default="/api")

    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    celery_broker_url: str = Field(validation_alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(validation_alias="CELERY_RESULT_BACKEND")

    upload_tmp_dir: str = Field(default="/tmp/imports")
    max_upload_size_mb: int = Field(default=512)

    @model_validator(mode="after")
    def convert_database_url(self) -> "Settings":
        """Convert postgresql+psycopg:// (psycopg3) to postgresql:// (psycopg2)."""
        if self.database_url.startswith("postgresql+psycopg://"):
            self.database_url = self.database_url.replace("postgresql+psycopg://", "postgresql://")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance so downstream code can import directly."""

    return Settings()
