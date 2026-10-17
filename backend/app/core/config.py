from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Knowledge Atlas API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://knowledge_atlas:knowledge_atlas@localhost:5432/knowledge_atlas"
    )
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    max_upload_bytes: int = 10 * 1024 * 1024
    task_lease_seconds: int = Field(default=300, ge=1, le=86400)
    task_max_attempts: int = Field(default=3, ge=1, le=100)
    worker_poll_interval_seconds: float = Field(default=2, gt=0, le=60)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

