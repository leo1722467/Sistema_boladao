from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Contato


class ContatoRepository:
    """Repository for `Contato` operations."""

    async def get_by_email(self, session: AsyncSession, email: str) -> Optional[Contato]:
        """Fetch `Contato` by email.

        Args:
            session: Async database session.
            email: Email to search.

        Returns:
            Optional[Contato]: Found record or None.
        """

        stmt = select(Contato).where(Contato.email == email)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, nome: str, email: Optional[str], empresa_id: Optional[int] = None) -> Contato:
        """Create a new `Contato`.

        Args:
            session: Async database session.
            nome: Contact name.
            email: Contact email.
            empresa_id: Optional Empresa ID to associate the contact with.

        Returns:
            Contato: Persisted entity.
        """

        entity = Contato(nome=nome, email=email, ativo=True, empresa_id=empresa_id)
        session.add(entity)
        await session.flush()
        return entity