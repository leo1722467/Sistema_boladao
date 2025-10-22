from __future__ import annotations
import time
import random
import logging
import asyncio
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, text

from app.repositories.ativo import AtivoRepository
from app.repositories.estoque import EstoqueRepository
from app.db.models import Ativo, Estoque
from app.core.exceptions import SerialGenerationError, ErrorHandler

logger = logging.getLogger(__name__)


class SerialService:
    """Generate company-scoped serials with robust collision handling and retry logic."""

    def __init__(self) -> None:
        self.ativo_repo = AtivoRepository()
        self.estoque_repo = EstoqueRepository()
        self.max_retries = 10
        self.base_delay = 0.1  # 100ms base delay for retries

    def _format(self, empresa_id: int, kind: Literal["ATIVO", "ESTOQUE"], attempt: int = 0) -> str:
        """
        Generate a serial number with improved uniqueness.
        
        Args:
            empresa_id: Company ID for scoping
            kind: Type of serial (ATIVO or ESTOQUE)
            attempt: Retry attempt number for additional randomness
            
        Returns:
            Formatted serial number
        """
        timestamp = int(time.time() * 1000)  # Use milliseconds for better uniqueness
        random_part = random.randint(1000, 9999)
        
        # Add attempt number for collision resolution
        if attempt > 0:
            random_part += attempt * 10000
            
        return f"EMP-{empresa_id}-{timestamp}-{random_part}-{kind}"

    async def _check_ativo_serial_exists(self, session: AsyncSession, empresa_id: int, serial: str) -> bool:
        """Check if an ativo serial already exists for the company."""
        try:
            stmt = select(Ativo).where(
                Ativo.empresa_id == empresa_id,
                Ativo.serial_text == serial
            ).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.warning(f"Error checking ativo serial existence: {e}")
            return False

    async def _check_estoque_serial_exists(self, session: AsyncSession, empresa_id: int, serial: str) -> bool:
        """Check if an estoque serial already exists for the company."""
        try:
            stmt = select(Estoque).where(
                Estoque.empresa_id == empresa_id,
                Estoque.serial == serial
            ).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.warning(f"Error checking estoque serial existence: {e}")
            return False

    async def generate_ativo_serial(self, session: AsyncSession, empresa_id: int) -> str:
        """
        Generate a unique serial for an Ativo with robust collision handling.
        
        Args:
            session: Database session
            empresa_id: Company ID for scoping
            
        Returns:
            Unique serial number
            
        Raises:
            SerialGenerationError: If unable to generate unique serial after retries
        """
        ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
        
        for attempt in range(self.max_retries):
            try:
                candidate = self._format(empresa_id, "ATIVO", attempt)
                
                # Check if serial already exists
                exists = await self._check_ativo_serial_exists(session, empresa_id, candidate)
                
                if not exists:
                    logger.debug(f"Generated ativo serial {candidate} for empresa {empresa_id} on attempt {attempt + 1}")
                    return candidate
                
                # If collision detected, add exponential backoff delay
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    await asyncio.sleep(delay)
                    logger.debug(f"Serial collision detected, retrying in {delay:.3f}s (attempt {attempt + 1})")
                    
            except Exception as e:
                logger.error(f"Error during ativo serial generation attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    raise SerialGenerationError(
                        f"Failed to generate ativo serial after {self.max_retries} attempts",
                        {"empresa_id": empresa_id, "last_error": str(e)}
                    )
        
        raise SerialGenerationError(
            f"Unable to generate unique ativo serial after {self.max_retries} attempts",
            {"empresa_id": empresa_id}
        )

    async def generate_estoque_serial(self, session: AsyncSession, empresa_id: int) -> str:
        """
        Generate a unique serial for an Estoque with robust collision handling.
        
        Args:
            session: Database session
            empresa_id: Company ID for scoping
            
        Returns:
            Unique serial number
            
        Raises:
            SerialGenerationError: If unable to generate unique serial after retries
        """
        ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
        
        for attempt in range(self.max_retries):
            try:
                candidate = self._format(empresa_id, "ESTOQUE", attempt)
                
                # Check if serial already exists
                exists = await self._check_estoque_serial_exists(session, empresa_id, candidate)
                
                if not exists:
                    logger.debug(f"Generated estoque serial {candidate} for empresa {empresa_id} on attempt {attempt + 1}")
                    return candidate
                
                # If collision detected, add exponential backoff delay
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    await asyncio.sleep(delay)
                    logger.debug(f"Serial collision detected, retrying in {delay:.3f}s (attempt {attempt + 1})")
                    
            except Exception as e:
                logger.error(f"Error during estoque serial generation attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    raise SerialGenerationError(
                        f"Failed to generate estoque serial after {self.max_retries} attempts",
                        {"empresa_id": empresa_id, "last_error": str(e)}
                    )
        
        raise SerialGenerationError(
            f"Unable to generate unique estoque serial after {self.max_retries} attempts",
            {"empresa_id": empresa_id}
        )

    async def validate_serial_format(self, serial: str, kind: Literal["ATIVO", "ESTOQUE"]) -> bool:
        """
        Validate that a serial number follows the expected format.
        
        Args:
            serial: Serial number to validate
            kind: Expected type (ATIVO or ESTOQUE)
            
        Returns:
            True if format is valid
        """
        if not serial or not isinstance(serial, str):
            return False
            
        parts = serial.split("-")
        if len(parts) != 5:
            return False
            
        try:
            # Check format: EMP-{empresa_id}-{timestamp}-{random}-{kind}
            if parts[0] != "EMP":
                return False
            if not parts[1].isdigit():  # empresa_id
                return False
            if not parts[2].isdigit():  # timestamp
                return False
            if not parts[3].isdigit():  # random part
                return False
            if parts[4] != kind:  # kind
                return False
                
            return True
            
        except (ValueError, IndexError):
            return False

    async def get_next_sequence_number(self, session: AsyncSession, empresa_id: int, prefix: str) -> int:
        """
        Get the next sequence number for a given prefix (future enhancement).
        This can be used for more predictable serial generation.
        
        Args:
            session: Database session
            empresa_id: Company ID
            prefix: Serial prefix
            
        Returns:
            Next sequence number
        """
        # This is a placeholder for future sequence-based serial generation
        # Could be implemented with a dedicated sequence table
        try:
            # For now, return a simple timestamp-based sequence
            return int(time.time() * 1000) % 1000000
        except Exception as e:
            logger.error(f"Error getting sequence number: {e}")
            return random.randint(100000, 999999)