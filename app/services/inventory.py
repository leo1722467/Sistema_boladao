from __future__ import annotations
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.repositories.estoque import EstoqueRepository
from app.services.asset import AssetService
from app.services.serial import SerialService
from app.db.models import Estoque, Ativo, CatalogoPeca
from app.core.exceptions import (
    InventoryError, ValidationError, ConflictError, 
    ErrorHandler, NotFoundError
)

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self) -> None:
        self.estoque_repo = EstoqueRepository()
        self.asset_svc = AssetService()
        self.serial_svc = SerialService()

    async def intake(
        self,
        session: AsyncSession,
        empresa_id: int,
        catalogo_peca_id: int,
        serial: Optional[str] = None,
        status_estoque_id: Optional[int] = None,
        qtd: Optional[int] = 1,
        auto_create_asset: bool = True,
    ) -> tuple[Estoque, Optional[Ativo]]:
        """
        Process inventory intake with comprehensive validation and error handling.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            catalogo_peca_id: Catalog item ID
            serial: Optional serial number (generated if not provided)
            status_estoque_id: Optional inventory status ID
            qtd: Quantity (default 1)
            auto_create_asset: Whether to automatically create an asset
            
        Returns:
            Tuple of (Estoque, Optional[Ativo])
            
        Raises:
            ValidationError: For invalid input parameters
            NotFoundError: If catalog item doesn't exist
            ConflictError: If serial number conflicts
            InventoryError: For other inventory-specific errors
        """
        try:
            # Validate input parameters
            ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
            ErrorHandler.validate_positive_integer(catalogo_peca_id, "catalogo_peca_id")
            
            if qtd is not None:
                ErrorHandler.validate_positive_integer(qtd, "qtd")
            else:
                qtd = 1
                
            if status_estoque_id is not None:
                ErrorHandler.validate_positive_integer(status_estoque_id, "status_estoque_id")
            
            # Validate catalog item exists
            catalogo_item = await session.get(CatalogoPeca, catalogo_peca_id)
            if not catalogo_item:
                raise NotFoundError(
                    f"Catalog item with ID {catalogo_peca_id} not found",
                    {"catalogo_peca_id": catalogo_peca_id}
                )
            
            # Generate serial if missing
            if not serial:
                try:
                    serial = await self.serial_svc.generate_estoque_serial(session, empresa_id)
                except Exception as e:
                    logger.error(f"Failed to generate serial for empresa {empresa_id}: {e}")
                    raise InventoryError(
                        "Failed to generate serial number for inventory item",
                        {"empresa_id": empresa_id, "error": str(e)}
                    )
            
            # Validate serial format if provided
            if serial and len(serial.strip()) == 0:
                raise ValidationError("Serial number cannot be empty or whitespace")
            
            # Create inventory item
            try:
                estoque = await self.estoque_repo.intake(
                    session=session,
                    empresa_id=empresa_id,
                    catalogo_peca_id=catalogo_peca_id,
                    serial=serial,
                    status_estoque_id=status_estoque_id,
                    qtd=qtd,
                )
                logger.info(f"Created inventory item {estoque.id} for empresa {empresa_id}")
                
            except IntegrityError as e:
                logger.warning(f"Integrity error creating inventory item: {e}")
                if "serial" in str(e).lower():
                    raise ConflictError(
                        f"Serial number '{serial}' already exists for this company",
                        {"serial": serial, "empresa_id": empresa_id}
                    )
                raise InventoryError(
                    "Failed to create inventory item due to data constraint violation",
                    {"error": str(e)}
                )

            # Create asset if requested
            ativo: Optional[Ativo] = None
            if auto_create_asset:
                try:
                    ativo = await self.asset_svc.create_from_stock(
                        session=session,
                        empresa_id=empresa_id,
                        estoque=estoque,
                    )
                    logger.info(f"Created asset {ativo.id} from inventory item {estoque.id}")
                    
                except Exception as e:
                    logger.error(f"Failed to create asset from inventory item {estoque.id}: {e}")
                    # Don't fail the entire operation if asset creation fails
                    # Log the error and continue without the asset
                    logger.warning(f"Continuing without asset creation due to error: {e}")
            
            return estoque, ativo
            
        except (ValidationError, NotFoundError, ConflictError, InventoryError):
            # Re-raise business logic exceptions as-is
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during inventory intake: {e}")
            raise InventoryError(
                "An unexpected error occurred during inventory intake",
                {"error": str(e), "empresa_id": empresa_id}
            )

    async def validate_stock_availability(
        self,
        session: AsyncSession,
        empresa_id: int,
        catalogo_peca_id: int,
        required_qty: int = 1
    ) -> bool:
        """
        Validate if sufficient stock is available for a catalog item.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            catalogo_peca_id: Catalog item ID
            required_qty: Required quantity
            
        Returns:
            True if sufficient stock is available
        """
        try:
            ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
            ErrorHandler.validate_positive_integer(catalogo_peca_id, "catalogo_peca_id")
            ErrorHandler.validate_positive_integer(required_qty, "required_qty")
            
            available_qty = await self.estoque_repo.get_available_quantity(
                session, empresa_id, catalogo_peca_id
            )
            
            return available_qty >= required_qty
            
        except Exception as e:
            logger.error(f"Error checking stock availability: {e}")
            return False