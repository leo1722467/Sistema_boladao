from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.auth import get_current_user_any
from app.db.models import UserAuth, Contato


@dataclass
class TenantContext:
    empresa_id: int
    user_id: int
    contato_id: int


async def get_tenant_context(
    session: AsyncSession = Depends(get_db),
    current_user: UserAuth = Depends(get_current_user_any),
) -> TenantContext:
    """Resolve tenant context (empresa_id) from the authenticated user.

    Currently derives empresa_id via the user's Contato. In the future, this can
    support admin overrides (e.g., X-Company-ID) and role-based scoping.
    """

    contato: Optional[Contato] = await session.get(Contato, current_user.contato_id)
    if not contato or contato.empresa_id is None:
        # Return a clear HTTP error instead of crashing with 500
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user has no associated empresa (company)"
        )

    return TenantContext(
        empresa_id=int(contato.empresa_id),
        user_id=int(current_user.id),
        contato_id=int(current_user.contato_id),
    )