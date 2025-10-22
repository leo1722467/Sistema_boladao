"""
Custom exceptions for the Sistema Boladão application.
Provides structured error handling with proper HTTP status codes and messages.
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class BusinessLogicError(Exception):
    """Base exception for business logic errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BusinessLogicError):
    """Raised when input validation fails."""
    pass


class NotFoundError(BusinessLogicError):
    """Raised when a requested resource is not found."""
    pass


class ConflictError(BusinessLogicError):
    """Raised when there's a conflict with existing data."""
    pass


class TenantScopeError(BusinessLogicError):
    """Raised when tenant scoping validation fails."""
    pass


class SerialGenerationError(BusinessLogicError):
    """Raised when serial generation fails after retries."""
    pass


class InventoryError(BusinessLogicError):
    """Raised for inventory-specific business logic errors."""
    pass


class AssetError(BusinessLogicError):
    """Raised for asset-specific business logic errors."""
    pass


class TicketError(BusinessLogicError):
    """Raised for ticket-specific business logic errors."""
    pass


class ServiceOrderError(BusinessLogicError):
    """Raised for service order-specific business logic errors."""
    pass


def business_exception_to_http(exc: BusinessLogicError) -> HTTPException:
    """Convert business logic exceptions to appropriate HTTP exceptions."""
    
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": exc.message, "type": "validation_error", **exc.details}
        )
    
    if isinstance(exc, NotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": exc.message, "type": "not_found", **exc.details}
        )
    
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": exc.message, "type": "conflict", **exc.details}
        )
    
    if isinstance(exc, TenantScopeError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": exc.message, "type": "tenant_scope_error", **exc.details}
        )
    
    # Default to 500 for other business logic errors
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"message": exc.message, "type": "business_logic_error", **exc.details}
    )


class ErrorHandler:
    """Centralized error handling utilities."""
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: list[str]) -> None:
        """Validate that all required fields are present and not None."""
        missing_fields = []
        for field in required_fields:
            if field not in data or data[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValidationError(
                f"Missing required fields: {', '.join(missing_fields)}",
                {"missing_fields": missing_fields}
            )
    
    @staticmethod
    def validate_positive_integer(value: Any, field_name: str) -> int:
        """Validate that a value is a positive integer."""
        if not isinstance(value, int) or value <= 0:
            raise ValidationError(
                f"{field_name} must be a positive integer",
                {"field": field_name, "value": value}
            )
        return value
    
    @staticmethod
    def validate_tenant_scope(resource_empresa_id: int, tenant_empresa_id: int, resource_type: str) -> None:
        """Validate that a resource belongs to the current tenant."""
        if resource_empresa_id != tenant_empresa_id:
            raise TenantScopeError(
                f"{resource_type} does not belong to the current company",
                {
                    "resource_empresa_id": resource_empresa_id,
                    "tenant_empresa_id": tenant_empresa_id,
                    "resource_type": resource_type
                }
            )