"""Application configuration management using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings resolved from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change-to-a-secure-random-secret-key-in-production"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/repopilot"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Repository ingestion safety limits (P1-02)
    REPO_MAX_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
    REPO_FETCH_TIMEOUT_SECONDS: int = 60
    REPO_TEMP_BASE_DIR: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
