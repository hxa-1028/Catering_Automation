"""Application settings loaded from the environment or an optional .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from catering_agent.constants import APP_PORT, DB_NAME


class Settings(BaseSettings):
    """Application settings, including paths to container-managed secret files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CATERING_",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_port: int = Field(default=APP_PORT, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str | None = None
    database_host: str = "db"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = DB_NAME
    database_user: str = "catering"
    db_password_secret_file: Path = Path("/run/secrets/db_password")
    llm_api_key_secret_file: Path = Path("/run/secrets/llm_api_key")
    gotenberg_url: str = "http://docconv:3000"

    @staticmethod
    def _read_secret_file(path: Path) -> str | None:
        """Read a non-empty file secret without exposing its value to callers."""

        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return value or None

    def resolved_database_url(self) -> str | None:
        """Return an explicit development URL or construct one from the DB secret."""

        if self.database_url:
            return self.database_url

        password = self._read_secret_file(self.db_password_secret_file)
        if password is None:
            return None
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        ).render_as_string(hide_password=False)

    def required_secrets_loaded(self) -> bool:
        """Check the Compose-managed secrets needed by app and worker services."""

        return (
            self._read_secret_file(self.db_password_secret_file) is not None
            and self._read_secret_file(self.llm_api_key_secret_file) is not None
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached process settings after Pydantic validation."""

    return Settings()
