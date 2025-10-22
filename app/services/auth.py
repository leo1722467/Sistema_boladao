import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password, verify_password, create_jwt_token
from app.core.config import get_settings
from app.repositories.user_auth import UserAuthRepository
from app.repositories.contato import ContatoRepository
from app.db.models import AuditLog, UserAuth, Contato

logger = logging.getLogger(__name__)
settings = get_settings()


class AuthService:
    """Authentication service handling register and login flows."""

    def __init__(self) -> None:
        self.user_repo = UserAuthRepository()
        self.contato_repo = ContatoRepository()

    async def register(self, session: AsyncSession, nome: str, email: str, password: str) -> UserAuth:
        """Register a new user and create associated entities.

        Args:
            session: Async database session.
            nome: Contact name.
            email: Login email.
            password: Plain password.

        Returns:
            UserAuth: Created auth entity.
        """

        existing_contato = await self.contato_repo.get_by_email(session, email)
        if existing_contato is None:
            existing_contato = await self.contato_repo.create(session, nome=nome, email=email)

        existing_auth = await self.user_repo.get_by_email(session, email)
        if existing_auth:
            raise ValueError("Email already registered")

        hashed = hash_password(password)
        auth = await self.user_repo.create(session, contato=existing_contato, hashed_password=hashed)

        log = AuditLog(
            id_usuario=auth.id,
            acao="REGISTER",
            tabela_afetada="user_auth",
            registro_afetado=auth.id,
            dados_anteriores=None,
            dados_novos={"contato_id": auth.contato_id, "email": email},
            detalhes_adicionais="User registration",
        )
        session.add(log)

        await session.commit()
        await session.refresh(auth)
        return auth

    async def authenticate(self, session: AsyncSession, email: str, password: str) -> tuple[str, str, UserAuth]:
        """Authenticate credentials and issue tokens.

        Args:
            session: Async database session.
            email: Login email.
            password: Plain password.

        Returns:
            Tuple of access_token, refresh_token, and auth entity.
        """

        auth = await self.user_repo.get_by_email(session, email)
        if not auth:
            raise ValueError("Invalid credentials")
        if not verify_password(password, auth.hashed_senha):
            raise ValueError("Invalid credentials")
        if not auth.ativo:
            raise ValueError("User inactive")

        access_expires = settings.ACCESS_EXPIRES_MIN * 60
        refresh_expires = settings.REFRESH_EXPIRES_DAYS * 24 * 60 * 60
        access = create_jwt_token(subject=str(auth.id), expires_in=access_expires)
        refresh = create_jwt_token(subject=str(auth.id), expires_in=refresh_expires, claims={"type": "refresh"})

        log = AuditLog(
            id_usuario=auth.id,
            acao="LOGIN",
            tabela_afetada="user_auth",
            registro_afetado=auth.id,
            dados_anteriores=None,
            dados_novos=None,
            detalhes_adicionais="User login",
        )
        session.add(log)
        await session.commit()
        return access, refresh, auth

    async def refresh(self, session: AsyncSession, auth: UserAuth) -> tuple[str, str]:
        """Issue new token pair for an authenticated user.

        Args:
            session: Async database session.
            auth: Authenticated user entity.

        Returns:
            Tuple of new access and refresh tokens.
        """

        access_expires = settings.ACCESS_EXPIRES_MIN * 60
        refresh_expires = settings.REFRESH_EXPIRES_DAYS * 24 * 60 * 60
        access = create_jwt_token(subject=str(auth.id), expires_in=access_expires)
        refresh = create_jwt_token(subject=str(auth.id), expires_in=refresh_expires, claims={"type": "refresh"})
        return access, refresh