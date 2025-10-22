from __future__ import annotations
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ativo, Estoque


class AtivoRepository:
    """Repository for Ativo (asset) operations with empresa scoping."""

    async def list_by_empresa(self, session: AsyncSession, empresa_id: int) -> List[Ativo]:
        stmt = select(Ativo).where(Ativo.empresa_id == empresa_id).limit(200)
        res = await session.execute(stmt)
        return res.scalars().all()

    async def get_by_id(self, session: AsyncSession, empresa_id: int, ativo_id: int) -> Optional[Ativo]:
        stmt = select(Ativo).where(Ativo.id == ativo_id, Ativo.empresa_id == empresa_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_serial_text(self, session: AsyncSession, empresa_id: int, serial_text: str) -> Optional[Ativo]:
        stmt = select(Ativo).where(Ativo.empresa_id == empresa_id, Ativo.serial_text == serial_text)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        empresa_id: int,
        serial_text: str,
        descricao: Optional[str] = None,
        contrato_id: Optional[int] = None,
        status_ativo_id: Optional[int] = None,
        tipo_ativo_id: Optional[int] = None,
        acesso_ativo_id: Optional[int] = None,
        local_instalacao_id: Optional[int] = None,
        stock_unit_id: Optional[int] = None,
    ) -> Ativo:
        entity = Ativo(
            empresa_id=empresa_id,
            serial_text=serial_text,
            descricao=descricao,
            contrato_id=contrato_id,
            status_ativo_id=status_ativo_id,
            tipo_ativo_id=tipo_ativo_id,
            acesso_ativo_id=acesso_ativo_id,
            local_instalacao_id=local_instalacao_id,
            stock_unit_id=stock_unit_id,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def link_stock(self, session: AsyncSession, ativo: Ativo, estoque: Estoque) -> None:
        ativo.stock_unit_id = estoque.id
        estoque.vinculado_ativo_id = ativo.id
        await session.flush()