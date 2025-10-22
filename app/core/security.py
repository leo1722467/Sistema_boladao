import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()


logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt.

    Args:
        password: Plain text password.

    Returns:
        Hashed password string.
    """

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: Plain text password.
        hashed_password: Previously hashed password.

    Returns:
        True if password matches; False otherwise.
    """

    return pwd_context.verify(plain_password, hashed_password)


def create_jwt_token(subject: str, expires_in: int, claims: Optional[Dict[str, Any]] = None) -> str:
    """Create a signed JWT token.

    Args:
        subject: Token subject (e.g., user id).
        expires_in: Expiration time in seconds.
        claims: Optional claims to include.

    Returns:
        Signed JWT token string.
    """

    now = datetime.utcnow()
    payload: Dict[str, Any] = {"sub": subject, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    if claims:
        payload.update(claims)
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return token


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a JWT token and return its payload if valid.

    Args:
        token: JWT token string.

    Returns:
        Decoded payload dict if valid; None otherwise.
    """

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError as exc:
        logger.warning("JWT verification failed: %s", exc)
        return None