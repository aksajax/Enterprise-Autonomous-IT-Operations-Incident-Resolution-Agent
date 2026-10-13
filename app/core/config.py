
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(
        default="Enterprise Autonomous IT Operations Agent",
        min_length=3,
        max_length=120,
    )
    app_env: Literal[
        "development",
        "test",
        "staging",
        "production",
    ] = "development"

    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/incident_ops.db"

    # JWT authentication settings
    jwt_secret_key: str = Field(
        default="development-only-change-this-secret-key",
        min_length=32,
    )
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

        if normalized not in allowed:
            raise ValueError(
                f"log_level must be one of {sorted(allowed)}"
            )

        return normalized

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized.startswith("/"):
            raise ValueError("api_v1_prefix must start with '/'")

        if "//" in normalized:
            raise ValueError("api_v1_prefix cannot contain '//'")

        if normalized != "/":
            normalized = normalized.rstrip("/")

        return normalized

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.app_env == "production":
            if not self.database_url.startswith(
                "postgresql+psycopg://"
            ):
                raise ValueError(
                    "Production requires a PostgreSQL URL "
                    "using the psycopg driver."
                )

            if (
                self.jwt_secret_key
                == "development-only-change-this-secret-key"
            ):
                raise ValueError(
                    "Set a unique JWT_SECRET_KEY in production."
                )

        return self

    @property
    def is_development(self) -> bool:
        return self.app_env in {"development", "test"}

    @property
    def docs_enabled(self) -> bool:
        return self.is_development


settings = Settings()
