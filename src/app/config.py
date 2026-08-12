from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, overridable via environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Twatter API"
    api_prefix: str = "/api"
    environment: str = "development"
    debug: bool = False

    # Dev convenience default for this repo's machine. Real credentials belong in
    # .env (see .env.example) — env vars always override this value.
    database_url: str = "postgresql+psycopg://ashiq:1212@localhost:5432/twatter"

    jwt_secret_key: str = "change-me-in-production-with-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Comma-separated list of allowed origins, e.g. "http://localhost:3000,http://localhost:5173"
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
