from __future__ import annotations
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OrdemServico


class OrdemServicoRepository:
    """Repository for OrdemServico operations with enhanced CRUD functionality."""

    async def create(
        self,
        session: AsyncSession,
        numero_os: Optional[str] = None,
        chamado_id: Optional[int] = None,
        tipo_os_id: Optional[int] = None,
        atividades_realizadas: Optional[str] = None,
        observacao: Optional[str] = None,
        numero_apr: Optional[str] = None,
    ) -> OrdemServico:
        """Create a new service order."""
        entity = OrdemServico(
            numero_os=numero_os,
            chamado_id=chamado_id,
            tipo_os_id=tipo_os_id,
            atividades_realizadas=atividades_realizadas,
            observacao=observacao,
            numero_apr=numero_apr,
        )
        session.add(entity)
        await session.flush()
        return entity

    async def get_by_id(self, session: AsyncSession, service_order_id: int) -> Optional[OrdemServico]:
        """Get a service order by ID."""
        stmt = select(OrdemServico).where(OrdemServico.id == service_order_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_numero_os(self, session: AsyncSession, numero_os: str) -> Optional[OrdemServico]:
        """Get a service order by its number."""
        stmt = select(OrdemServico).where(OrdemServico.numero_os == numero_os)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_ticket(self, session: AsyncSession, chamado_id: int) -> List[OrdemServico]:
        """List all service orders for a specific ticket."""
        stmt = select(OrdemServico).where(OrdemServico.chamado_id == chamado_id).order_by(OrdemServico.id.desc())
        result = await session.execute(stmt)
        return result.scalars().all()

    async def list_by_type(self, session: AsyncSession, tipo_os_id: int, limit: int = 100) -> List[OrdemServico]:
        """List service orders by type."""
        stmt = select(OrdemServico).where(OrdemServico.tipo_os_id == tipo_os_id).order_by(OrdemServico.id.desc()).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def update(
        self,
        session: AsyncSession,
        service_order: OrdemServico,
        **updates
    ) -> OrdemServico:
        """Update a service order with the provided fields."""
        for field, value in updates.items():
            if hasattr(service_order, field):
                setattr(service_order, field, value)
        
        await session.flush()
        return service_order

    async def link_ticket(self, session: AsyncSession, os: OrdemServico, chamado_id: int) -> None:
        """Link a service order to a ticket."""
        os.chamado_id = chamado_id
        await session.flush()

    async def count_by_ticket(self, session: AsyncSession, chamado_id: int) -> int:
        """Count service orders for a specific ticket."""
        stmt = select(OrdemServico).where(OrdemServico.chamado_id == chamado_id)
        result = await session.execute(stmt)
        return len(result.scalars().all())