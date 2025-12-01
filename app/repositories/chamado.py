from __future__ import annotations
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chamado


class ChamadoRepository:
    """Repository for Chamado (ticket) operations with empresa scoping."""

    async def list_by_empresa(self, session: AsyncSession, empresa_id: int) -> List[Chamado]:
        stmt = select(Chamado).where(Chamado.empresa_id == empresa_id).limit(200)
        res = await session.execute(stmt)
        return res.scalars().all()

    async def get_by_id(self, session: AsyncSession, empresa_id: int, chamado_id: int) -> Optional[Chamado]:
        stmt = select(Chamado).where(Chamado.id == chamado_id, Chamado.empresa_id == empresa_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id_global(self, session: AsyncSession, chamado_id: int) -> Optional[Chamado]:
        stmt = select(Chamado).where(Chamado.id == chamado_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        empresa_id: int,
        numero: str,
        titulo: str,
        ativo_id: Optional[int] = None,
        descricao: Optional[str] = None,
        categoria_id: Optional[int] = None,
        prioridade_id: Optional[int] = None,
        status_id: Optional[int] = None,
        requisitante_contato_id: Optional[int] = None,
        agente_contato_id: Optional[int] = None,
        proprietario_contato_id: Optional[int] = None,
    ) -> Chamado:
        entity = Chamado(
            empresa_id=empresa_id,
            numero=numero,
            ativo_id=ativo_id,
            titulo=titulo,
            descricao=descricao,
            categoria_id=categoria_id,
            prioridade_id=prioridade_id,
            status_id=status_id,
            requisitante_contato_id=requisitante_contato_id,
            agente_contato_id=agente_contato_id,
            proprietario_contato_id=proprietario_contato_id,
        )
        session.add(entity)
        await session.flush()
        return entity
