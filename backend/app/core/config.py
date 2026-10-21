from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
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
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = Field(default=120, ge=5, le=180)
    extraction_max_input_chars: int = Field(default=60000, ge=1000, le=200000)
    embedding_api_key: SecretStr | None = None
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = Field(default=1024, ge=1, le=2000)
    embedding_timeout_seconds: float = Field(default=60, ge=5, le=180)
    embedding_batch_size: int = Field(default=32, ge=1, le=100)
    github_token: SecretStr | None = None
    github_api_base_url: str = "https://api.github.com"
    github_graphql_url: str = "https://api.github.com/graphql"
    github_api_version: str = "2026-03-10"
    github_timeout_seconds: float = Field(default=30, ge=5, le=120)

    @field_validator("github_token", mode="before")
    @classmethod
    def normalize_github_token(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

