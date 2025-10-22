from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENV: str = Field(default="dev", description="dev|staging|prod")
    APP_NAME: str = "Sistemao Bolado API"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8081

    # Segurança
    JWT_SECRET: str = "change-me"
    ACCESS_EXPIRES_MIN: int = 30
    REFRESH_EXPIRES_DAYS: int = 7

    # DB
    DB_URL: AnyUrl | str = "sqlite+aiosqlite:///./app.db"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

@lru_cache
def get_settings() -> Settings:
    return Settings()
