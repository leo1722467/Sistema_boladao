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
        # Seed admin user
        try:
            await svc.register(session, nome="Admin", email="admin@example.com", password="admin123", empresa_nome="Admin Company")
            logger.info("Seeded admin user")
        except ValueError:
            logger.info("Admin user already exists; skipping seeding")

        # Seed dev user
        try:
            await svc.register(session, nome="Dev User", email="dev@example.com", password="secret123", empresa_nome="Dev Company")
            logger.info("Seeded dev user")
        except ValueError:
            logger.info("Dev user already exists; skipping seeding")


if __name__ == "__main__":
    asyncio.run(seed())