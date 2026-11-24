from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "docuask"
    postgres_user: str = "docuask"
    postgres_password: SecretStr | None = None
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "docuask_e5_small_v1"
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = Field(default=30, ge=1, le=1440)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    auth_rate_limit: int = Field(default=60, ge=1, le=1000)
    api_rate_limit: int = Field(default=180, ge=1, le=10000)
    storage_dir: Path = Path("storage")
    stale_processing_minutes: int = Field(default=30, ge=1, le=1440)
    stale_queued_minutes: int = Field(default=30, ge=1, le=1440)
    recovery_interval_seconds: int = Field(default=60, ge=1, le=3600)
    preload_embeddings: bool = True
    pdfium_fallback: bool = True
    ocr_enabled: bool = False
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=100 * 1024 * 1024)

    llm_provider: Literal["ollama", "openai"] = "ollama"
    llm_model: str = "llama3.2:3b"
    ollama_url: str = "http://localhost:11434"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: SecretStr | None = None
    retrieval_mode: Literal["dense", "hybrid"] = "dense"
    rerank_enabled: bool = False
    rerank_candidates: int = Field(default=20, ge=2, le=50)
    qa_min_score: float = Field(default=0.45, ge=-1, le=1)
    qa_max_answer_chars: int = Field(default=10000, ge=100, le=100000)

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if self.jwt_secret is not None and len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        if self.app_env == "production" and self.jwt_secret is None:
            raise ValueError("JWT_SECRET is required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
