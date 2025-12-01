import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.services.auth import AuthService
from app.db.models import Empresa, Contato
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
            # Ensure admin contact has empresa association
            res = await session.execute(select(Contato).where(Contato.email == "admin@example.com"))
            admin_contato = res.scalar_one_or_none()
            if admin_contato and admin_contato.empresa_id is None:
                res_emp = await session.execute(select(Empresa).where(Empresa.nome == "Admin Company"))
                empresa = res_emp.scalar_one_or_none()
                if not empresa:
                    empresa = Empresa(nome="Admin Company")
                    session.add(empresa)
                    await session.flush()
                admin_contato.empresa_id = empresa.id
                await session.commit()
                logger.info("Updated admin contato to associate with Admin Company")

        # Seed dev user
        try:
            await svc.register(session, nome="Dev User", email="dev@example.com", password="secret123", empresa_nome="Dev Company")
            logger.info("Seeded dev user")
        except ValueError:
            logger.info("Dev user already exists; skipping seeding")
            # Ensure dev contact has empresa association
            res = await session.execute(select(Contato).where(Contato.email == "dev@example.com"))
            dev_contato = res.scalar_one_or_none()
            if dev_contato and dev_contato.empresa_id is None:
                res_emp = await session.execute(select(Empresa).where(Empresa.nome == "Dev Company"))
                empresa = res_emp.scalar_one_or_none()
                if not empresa:
                    empresa = Empresa(nome="Dev Company")
                    session.add(empresa)
                    await session.flush()
                dev_contato.empresa_id = empresa.id
                await session.commit()
                logger.info("Updated dev contato to associate with Dev Company")


if __name__ == "__main__":
    asyncio.run(seed())