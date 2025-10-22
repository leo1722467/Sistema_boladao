from __future__ import annotations
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Estoque


class EstoqueRepository:
    """Repository for Estoque (inventory) operations with empresa scoping."""

    async def intake(
        self,
        session: AsyncSession,
        empresa_id: int,
        catalogo_peca_id: int,
        serial: Optional[str] = None,
        status_estoque_id: Optional[int] = None,
        qtd: Optional[int] = 1,
    ) -> Estoque:
        entity = Estoque(
            empresa_id=empresa_id,
            catalogo_peca_id=catalogo_peca_id,
            serial=serial,
            status_estoque_id=status_estoque_id,
            qtd=qtd,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def get_by_serial(self, session: AsyncSession, empresa_id: int, serial: str) -> Optional[Estoque]:
        stmt = select(Estoque).where(Estoque.empresa_id == empresa_id, Estoque.serial == serial)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def update_link_ativo(self, session: AsyncSession, estoque: Estoque, ativo_id: int) -> None:
        estoque.vinculado_ativo_id = ativo_id
        await session.flush()