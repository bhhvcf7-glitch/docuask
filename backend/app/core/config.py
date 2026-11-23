from functools import lru_cache
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
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = Field(default=30, ge=1, le=1440)

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
