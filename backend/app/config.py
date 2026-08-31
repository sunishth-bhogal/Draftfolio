"""Application settings, loaded from environment / .env."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://draftfolio:draftfolio@localhost:5432/draftfolio"
    redis_url: str = "redis://localhost:6379/0"
    env: str = "development"
    # Comma-separated list of allowed browser origins for CORS.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Auth — override in production via env.
    secret_key: str = "dev-secret-change-me-in-production-0123456789"
    token_ttl_hours: int = 720

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Managed hosts (Render/Heroku) hand out 'postgres://...'; SQLAlchemy
        needs the driver-qualified scheme."""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
