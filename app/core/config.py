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

    # SMTP notifications
    SMTP_HOST: str | None = None
    SMTP_PORT: int | None = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_FROM_NAME: str | None = "Sistema Boladão"
    NOTIFY_ENABLED: bool = False
    NOTIFY_ON_CREATE: bool = True
    NOTIFY_ON_STATUS: bool = True
    NOTIFY_ON_ASSIGN: bool = True
    NOTIFY_ON_PENDING_CUSTOMER: bool = True
    NOTIFY_ON_CONCLUDED: bool = True
    NOTIFY_SLA_ENABLED: bool = True
    NOTIFY_SLA_ON_RESPONSE_BREACH: bool = True
    NOTIFY_SLA_ON_RESOLUTION_BREACH: bool = True
    NOTIFY_SLA_ON_ESCALATION: bool = True
    NOTIFY_SLA_ON_OVERRIDES_UPDATED: bool = True
    NOTIFY_SLA_TEAM_EMAILS: list[str] = []

@lru_cache
def get_settings() -> Settings:
    return Settings()
