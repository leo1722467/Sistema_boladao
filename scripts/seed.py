import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.services.auth import AuthService
logger = logging.getLogger(__name__)


async def seed() -> None:
    """Seed minimal data for development.

    Returns:
        None
    """

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:  # type: ignore[call-arg]
        svc = AuthService()
        try:
            await svc.register(session, nome="Admin", email="admin@example.com", password="admin123")
            logger.info("Seeded admin user")
        except ValueError:
            logger.info("Admin user already exists; skipping seeding")


if __name__ == "__main__":
    asyncio.run(seed())