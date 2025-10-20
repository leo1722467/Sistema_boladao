from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.auth import AuthService
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, MeResponse
from app.core.security import verify_jwt_token
from app.db.models import UserAuth, Contato

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(session: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)) -> UserAuth:
    """Resolve current user from JWT token.

    Args:
        session: DB session dependency.
        token: Bearer token string.

    Returns:
        UserAuth entity.
    """

    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = int(payload.get("sub"))
    user = await session.get(UserAuth, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_user_any(request: Request, session: AsyncSession = Depends(get_db), authorization: Optional[str] = Header(None)) -> UserAuth:
    """Resolve current user from Authorization header or access_token cookie.

    Args:
        request: FastAPI request to read cookies.
        session: DB session dependency.
        authorization: Optional Authorization header.

    Returns:
        UserAuth entity.

    Raises:
        HTTPException: When token invalid or user not found.
    """

    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        logger.debug(f"No authentication token found for {request.url.path}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    payload = verify_jwt_token(token)
    if not payload:
        logger.debug(f"Invalid authentication token for {request.url.path}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = int(payload.get("sub"))
    user = await session.get(UserAuth, user_id)
    if not user:
        logger.warning(f"User not found for token subject: {user_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/register", response_model=MeResponse)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)) -> MeResponse:
    """Register a new user."""

    svc = AuthService()
    try:
        auth = await svc.register(session, nome=payload.nome, email=payload.email, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    contato: Optional[Contato] = await session.get(Contato, auth.contato_id)
    return MeResponse(id=auth.id, nome=contato.nome if contato else payload.nome, email=contato.email if contato else payload.email, ativo=auth.ativo)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate and issue JWT tokens."""

    svc = AuthService()
    try:
        access, refresh, _ = await svc.authenticate(session, email=payload.email, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/token", response_model=TokenResponse)
async def token(form_data: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_db)) -> TokenResponse:
    """OAuth2 password form endpoint to issue JWT tokens."""

    svc = AuthService()
    try:
        access, refresh, _ = await svc.authenticate(session, email=form_data.username, password=form_data.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(current_user: UserAuth = Depends(get_current_user_any), session: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Issue new tokens for the current user."""

    svc = AuthService()
    access, refresh = await svc.refresh(session, current_user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/me", response_model=MeResponse)
async def me(current_user: UserAuth = Depends(get_current_user_any), session: AsyncSession = Depends(get_db)) -> MeResponse:
    """Return current authenticated user info."""

    contato: Optional[Contato] = await session.get(Contato, current_user.contato_id)
    return MeResponse(id=current_user.id, nome=contato.nome if contato else "", email=contato.email if contato else None, ativo=current_user.ativo)