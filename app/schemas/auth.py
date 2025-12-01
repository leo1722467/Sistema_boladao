from typing import Optional
from pydantic import BaseModel, EmailStr, constr


class TokenResponse(BaseModel):
    """JWT token response payload.

    Attributes:
        access_token: Short-lived access token.
        refresh_token: Long-lived refresh token.
        token_type: OAuth2 token type, defaults to 'bearer'.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Login payload with email and password.

    Attributes:
        email: User email address.
        password: Plain password.
    """

    email: EmailStr
    password: constr(min_length=6)  # type: ignore[valid-type]


class RegisterRequest(BaseModel):
    """Registration payload with name, email and password.

    Attributes:
        nome: Full name.
        email: User email address.
        password: Plain password.
    """

    nome: constr(min_length=2)  # type: ignore[valid-type]
    email: EmailStr
    password: constr(min_length=6)  # type: ignore[valid-type]


class MeResponse(BaseModel):
    """Authenticated user profile payload.

    Attributes:
        id: Auth record id.
        nome: Contact name.
        email: Contact email.
        ativo: Whether user is active.
    """

    id: int
    nome: str
    email: Optional[EmailStr]
    ativo: bool
    contato_id: Optional[int]
