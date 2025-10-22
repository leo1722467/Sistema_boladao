from __future__ import annotations
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ativo import AtivoRepository
from app.repositories.estoque import EstoqueRepository
from app.services.serial import SerialService
from app.db.models import Ativo, Estoque


class AssetService:
    def __init__(self) -> None:
        self.ativo_repo = AtivoRepository()
        self.estoque_repo = EstoqueRepository()
        self.serial_svc = SerialService()

    async def create_from_stock(
        self,
        session: AsyncSession,
        empresa_id: int,
        estoque: Estoque,
        descricao: Optional[str] = None,
        contrato_id: Optional[int] = None,
        status_ativo_id: Optional[int] = None,
        tipo_ativo_id: Optional[int] = None,
        acesso_ativo_id: Optional[int] = None,
        local_instalacao_id: Optional[int] = None,
    ) -> Ativo:
        # Generate unique serial_text for asset
        serial_text = await self.serial_svc.generate_ativo_serial(session, empresa_id)
        ativo = await self.ativo_repo.create(
            session=session,
            empresa_id=empresa_id,
            serial_text=serial_text,
            descricao=descricao,
            contrato_id=contrato_id,
            status_ativo_id=status_ativo_id,
            tipo_ativo_id=tipo_ativo_id,
            acesso_ativo_id=acesso_ativo_id,
            local_instalacao_id=local_instalacao_id,
            stock_unit_id=estoque.id,
        )
        await self.ativo_repo.link_stock(session, ativo, estoque)
        return ativo