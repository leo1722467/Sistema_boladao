import logging
from typing import Optional
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        db_url: Database URL in SQLAlchemy format.
        jwt_secret: Secret used to sign JWT tokens.
        jwt_alg: Algorithm used for JWT.
        access_expires: Access token expiry in seconds.
        refresh_expires: Refresh token expiry in seconds.
        app_port: Default application port for local runs.
    """

    db_url: str = "sqlite+aiosqlite:///./app.db"
    jwt_secret: str = "change-me-in-env"
    jwt_alg: str = "HS256"
    access_expires: int = 900
    refresh_expires: int = 86400
    app_port: int = 8081

    class Config:
        env_prefix = "APP_"
        case_sensitive = False


settings = Settings()


def configure_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging.

    Args:
        level: Logging level to set.

    Returns:
        None
    """

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )