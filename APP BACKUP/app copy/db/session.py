from typing import AsyncGenerator
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_engine() -> object:
    """Create and return the async SQLAlchemy engine.

    Returns:
        Async engine instance.
    """

    engine = create_async_engine(str(settings.db_url), echo=False, poolclass=NullPool, future=True)
    return engine


engine = get_engine()
SessionLocal = async_sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an `AsyncSession` and ensures cleanup.

    Yields:
        AsyncSession: Database session for request scope.
    """

    async with SessionLocal() as session:  # type: ignore[call-arg]
        try:
            yield session
        except Exception as exc:
            # Don't log expected HTTP exceptions (like auth failures) as errors
            from fastapi import HTTPException
            if isinstance(exc, HTTPException) and exc.status_code in [401, 403]:
                logger.debug("Authentication/authorization failure: %s", exc.detail)
            else:
                logger.exception("DB session error: %s", exc)
            raise
        finally:
            await session.close()