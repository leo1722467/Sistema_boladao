from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import UserAuth, Contato


class UserAuthRepository:
    """Repository for `UserAuth` operations."""

    async def get_by_email(self, session: AsyncSession, email: str) -> Optional[UserAuth]:
        """Fetch UserAuth by associated Contato email.

            Args:
                session: Async database session.
                email: Email to search.

            Returns:
                Optional[UserAuth]: Found auth record or None.
        """

        stmt = select(UserAuth).join(Contato).where(Contato.email == email)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, contato: Contato, hashed_password: str) -> UserAuth:
        """Create a new `UserAuth` bound to a `Contato`.

        Args:
            session: Async database session.
            contato: Contato entity to bind.
            hashed_password: Hashed password.

        Returns:
            UserAuth: Persisted entity.
        """

        entity = UserAuth(contato_id=contato.id, hashed_senha=hashed_password, ativo=True)
        session.add(entity)
        await session.flush()
        return entity