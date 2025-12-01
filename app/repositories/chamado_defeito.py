from __future__ import annotations
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChamadoDefeito


class ChamadoDefeitoRepository:
    async def list_by_tipo_ativo(self, session: AsyncSession, tipo_ativo_id: int) -> List[ChamadoDefeito]:
        stmt = select(ChamadoDefeito).where(ChamadoDefeito.tipo_ativo_id == tipo_ativo_id).order_by(ChamadoDefeito.nome)
        res = await session.execute(stmt)
        return res.scalars().all()

    async def get_by_id(self, session: AsyncSession, defeito_id: int) -> Optional[ChamadoDefeito]:
        stmt = select(ChamadoDefeito).where(ChamadoDefeito.id == defeito_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def create(self, session: AsyncSession, nome: str, tipo_ativo_id: int) -> ChamadoDefeito:
        entity = ChamadoDefeito(nome=nome, tipo_ativo_id=tipo_ativo_id)
        session.add(entity)
        await session.flush()
        return entity

    async def delete(self, session: AsyncSession, defeito_id: int) -> bool:
        entity = await self.get_by_id(session, defeito_id)
        if not entity:
            return False
        await session.delete(entity)
        return True

