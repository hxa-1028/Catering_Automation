"""Application settings loaded from the environment or an optional .env file."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from catering_agent.constants import APP_PORT


class Settings(BaseSettings):
    """Non-secret settings required by the Phase 1 application scaffold."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CATERING_",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_port: int = Field(default=APP_PORT, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings after Pydantic validation."""

    return Settings()
