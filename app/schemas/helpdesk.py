"""
Pydantic schemas for helpdesk API endpoints.
Provides request/response models with comprehensive validation and documentation.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, conint, constr, validator
from enum import Enum


class InventoryIntakeRequest(BaseModel):
    """Request model for inventory intake operation."""
    
    catalogo_peca_id: int = Field(
        ..., 
        gt=0, 
        description="ID of the catalog item to add to inventory",
        example=1
    )
    serial: Optional[constr(min_length=1, max_length=100)] = Field(  # type: ignore[valid-type]
        None,
        description="Optional serial number. If not provided, one will be generated automatically",
        example="SN123456789"
    )
    status_estoque_id: Optional[int] = Field(
        None,
        gt=0,
        description="Optional inventory status ID. Uses default if not provided",
        example=1
    )
    qtd: Optional[conint(ge=1, le=10000)] = Field(  # type: ignore[valid-type]
        1,
        description="Quantity to add to inventory (default: 1)",
        example=5
    )
    auto_create_asset: bool = Field(
        True,
        description="Whether to automatically create an asset from this inventory item",
        example=True
    )

    class Config:
        schema_extra = {
            "example": {
                "catalogo_peca_id": 1,
                "serial": "SN123456789",
                "status_estoque_id": 1,
                "qtd": 1,
                "auto_create_asset": True
            }
        }


class InventoryIntakeResponse(BaseModel):
    """Response model for inventory intake operation."""
    
    estoque_id: int = Field(
        ...,
        description="ID of the created inventory item",
        example=123
    )
    asset_id: Optional[int] = Field(
        None,
        description="ID of the automatically created asset (if auto_create_asset was true)",
        example=456
    )
    serial: Optional[str] = Field(
        None,
        description="Serial number of the inventory item",
        example="EMP-1-1698765432000-1234-ESTOQUE"
    )

    class Config:
        schema_extra = {
            "example": {
                "estoque_id": 123,
                "asset_id": 456,
                "serial": "EMP-1-1698765432000-1234-ESTOQUE"
            }
        }


class AssetSummary(BaseModel):
    """Summary model for asset information."""
    
    id: int = Field(..., description="Asset ID", example=123)
    serial_text: str = Field(..., description="Asset serial number", example="EMP-1-1698765432000-1234-ATIVO")
    descricao: Optional[str] = Field(None, description="Asset description", example="Laptop Dell Inspiron")
    tag: Optional[str] = Field(None, description="Asset tag", example="TAG-001")
    criado_em: Optional[str] = Field(None, description="Creation timestamp (ISO format)", example="2023-10-31T10:30:00")


class CreateTicketRequest(BaseModel):
    """Request model for creating a new ticket."""
    
    titulo: constr(min_length=1, max_length=200) = Field(  # type: ignore[valid-type]
        ...,
        description="Ticket title (required)",
        example="Laptop not turning on"
    )
    descricao: Optional[constr(max_length=2000)] = Field(  # type: ignore[valid-type]
        None,
        description="Detailed description of the issue",
        example="The laptop won't turn on when pressing the power button. No lights or sounds."
    )
    prioridade_id: Optional[int] = Field(
        None,
        gt=0,
        description="Priority ID (uses default if not provided)",
        example=2
    )
    status_id: Optional[int] = Field(
        None,
        gt=0,
        description="Status ID (uses default if not provided)",
        example=1
    )
    categoria_id: Optional[int] = Field(
        None,
        gt=0,
        description="Category ID",
        example=3
    )
    solicitante_id: Optional[int] = Field(
        None,
        gt=0,
        description="Requester contact ID (uses current user if not provided)",
        example=10
    )
    ativo_id: Optional[int] = Field(
        None,
        gt=0,
        description="Asset ID to link to this ticket",
        example=456
    )
    serial_text: Optional[constr(min_length=1, max_length=100)] = Field(  # type: ignore[valid-type]
        None,
        description="Asset serial number (alternative to ativo_id)",
        example="EMP-1-1698765432000-1234-ATIVO"
    )

    @validator('titulo')
    def titulo_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty or whitespace')
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "titulo": "Laptop not turning on",
                "descricao": "The laptop won't turn on when pressing the power button. No lights or sounds.",
                "prioridade_id": 2,
                "categoria_id": 3,
                "ativo_id": 456
            }
        }


class CreateTicketResponse(BaseModel):
    """Response model for ticket creation."""
    
    id: int = Field(..., description="Ticket ID", example=789)
    numero: str = Field(..., description="Ticket number", example="TKT-2023-001234")
    ativo_id: Optional[int] = Field(None, description="Linked asset ID", example=456)

    class Config:
        schema_extra = {
            "example": {
                "id": 789,
                "numero": "TKT-2023-001234",
                "ativo_id": 456
            }
        }


class CreateServiceOrderRequest(BaseModel):
    """Request model for creating a service order."""
    
    chamado_id: Optional[int] = Field(
        None,
        gt=0,
        description="Ticket ID to link to this service order",
        example=789
    )
    tipo_os_id: Optional[int] = Field(
        None,
        gt=0,
        description="Service order type ID",
        example=1
    )
    atividades_realizadas: Optional[constr(max_length=2000)] = Field(  # type: ignore[valid-type]
        None,
        description="Description of activities performed",
        example="Diagnosed hardware failure, replaced motherboard, tested functionality"
    )
    observacao: Optional[constr(max_length=1000)] = Field(  # type: ignore[valid-type]
        None,
        description="Additional observations or notes",
        example="Customer satisfied with repair. Warranty extended by 6 months."
    )
    numero_apr: Optional[constr(max_length=50)] = Field(  # type: ignore[valid-type]
        None,
        description="APR (Risk Analysis) number if applicable",
        example="APR-2023-001"
    )

    class Config:
        schema_extra = {
            "example": {
                "chamado_id": 789,
                "tipo_os_id": 1,
                "atividades_realizadas": "Diagnosed hardware failure, replaced motherboard, tested functionality",
                "observacao": "Customer satisfied with repair. Warranty extended by 6 months.",
                "numero_apr": "APR-2023-001"
            }
        }


class CreateServiceOrderResponse(BaseModel):
    """Response model for service order creation."""
    
    id: int = Field(..., description="Service order ID", example=321)
    chamado_id: Optional[int] = Field(None, description="Linked ticket ID", example=789)
    numero_os: Optional[str] = Field(None, description="Service order number", example="OS-2023-001234")

    class Config:
        schema_extra = {
            "example": {
                "id": 321,
                "chamado_id": 789,
                "numero_os": "OS-2023-001234"
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    message: str = Field(..., description="Error message", example="Validation failed")
    type: str = Field(..., description="Error type", example="validation_error")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    class Config:
        schema_extra = {
            "example": {
                "message": "Catalog item with ID 999 not found",
                "type": "not_found",
                "details": {"catalogo_peca_id": 999}
            }
        }


class SuccessResponse(BaseModel):
    """Standard success response model."""
    
    message: str = Field(..., description="Success message", example="Operation completed successfully")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")

    class Config:
        schema_extra = {
            "example": {
                "message": "Operation completed successfully",
                "data": {"processed_items": 5}
            }
        }


class TicketDetailResponse(BaseModel):
    """Detailed ticket response model."""
    
    id: int = Field(..., description="Ticket ID", example=789)
    numero: str = Field(..., description="Ticket number", example="TKT-2023-001234")
    titulo: str = Field(..., description="Ticket title", example="Laptop not turning on")
    descricao: Optional[str] = Field(None, description="Ticket description")
    status: Optional[str] = Field(None, description="Current status", example="open")
    prioridade: Optional[str] = Field(None, description="Priority level", example="high")
    categoria: Optional[str] = Field(None, description="Ticket category", example="hardware")
    ativo_id: Optional[int] = Field(None, description="Linked asset ID", example=456)
    requisitante: Optional[str] = Field(None, description="Requester name", example="João Silva")
    agente: Optional[str] = Field(None, description="Assigned agent name", example="Maria Santos")
    criado_em: str = Field(..., description="Creation timestamp", example="2023-10-31T10:30:00")
    atualizado_em: str = Field(..., description="Last update timestamp", example="2023-10-31T15:45:00")
    fechado_em: Optional[str] = Field(None, description="Closure timestamp")
    sla_status: Optional[Dict[str, Any]] = Field(None, description="SLA breach information")
    next_actions: Optional[List[Dict[str, str]]] = Field(None, description="Suggested next actions")

    class Config:
        schema_extra = {
            "example": {
                "id": 789,
                "numero": "TKT-2023-001234",
                "titulo": "Laptop not turning on",
                "descricao": "The laptop won't turn on when pressing the power button",
                "status": "open",
                "prioridade": "high",
                "categoria": "hardware",
                "ativo_id": 456,
                "requisitante": "João Silva",
                "agente": "Maria Santos",
                "criado_em": "2023-10-31T10:30:00",
                "atualizado_em": "2023-10-31T15:45:00",
                "fechado_em": None,
                "sla_status": {"response_breach": False, "resolution_breach": True},
                "next_actions": [{"action": "transition_to_in_progress", "description": "Start working on ticket"}]
            }
        }


class UpdateTicketRequest(BaseModel):
    """Request model for updating a ticket."""
    
    titulo: Optional[constr(min_length=1, max_length=200)] = Field(  # type: ignore[valid-type]
        None,
        description="Updated ticket title",
        example="Laptop hardware failure - motherboard replacement needed"
    )
    descricao: Optional[constr(max_length=2000)] = Field(  # type: ignore[valid-type]
        None,
        description="Updated ticket description",
        example="After diagnosis, determined that motherboard needs replacement"
    )
    status_id: Optional[int] = Field(
        None,
        gt=0,
        description="New status ID",
        example=3
    )
    prioridade_id: Optional[int] = Field(
        None,
        gt=0,
        description="New priority ID",
        example=2
    )
    categoria_id: Optional[int] = Field(
        None,
        gt=0,
        description="New category ID",
        example=1
    )
    agente_contato_id: Optional[int] = Field(
        None,
        gt=0,
        description="Assign to agent (contact ID)",
        example=15
    )
    comment: Optional[constr(max_length=1000)] = Field(  # type: ignore[valid-type]
        None,
        description="Comment explaining the update",
        example="Escalating to senior technician due to complexity"
    )

    class Config:
        schema_extra = {
            "example": {
                "status_id": 3,
                "agente_contato_id": 15,
                "comment": "Escalating to senior technician due to complexity"
            }
        }


class TicketFilters(BaseModel):
    """Filters for ticket listing."""
    
    status_id: Optional[int] = Field(None, gt=0, description="Filter by status ID")
    prioridade_id: Optional[int] = Field(None, gt=0, description="Filter by priority ID")
    categoria_id: Optional[int] = Field(None, gt=0, description="Filter by category ID")
    agente_contato_id: Optional[int] = Field(None, gt=0, description="Filter by assigned agent")
    requisitante_contato_id: Optional[int] = Field(None, gt=0, description="Filter by requester")
    ativo_id: Optional[int] = Field(None, gt=0, description="Filter by linked asset")
    search: Optional[constr(max_length=100)] = Field(  # type: ignore[valid-type]
        None,
        description="Search in title, description, or ticket number",
        example="laptop"
    )
    limit: Optional[int] = Field(100, ge=1, le=500, description="Maximum number of results")
    offset: Optional[int] = Field(0, ge=0, description="Number of results to skip")

    class Config:
        schema_extra = {
            "example": {
                "status_id": 1,
                "search": "laptop",
                "limit": 50,
                "offset": 0
            }
        }


class TicketListResponse(BaseModel):
    """Response model for ticket listing."""
    
    tickets: List[TicketDetailResponse] = Field(..., description="List of tickets")
    total: int = Field(..., description="Total number of tickets matching filters")
    limit: int = Field(..., description="Applied limit")
    offset: int = Field(..., description="Applied offset")

    class Config:
        schema_extra = {
            "example": {
                "tickets": [
                    {
                        "id": 789,
                        "numero": "TKT-2023-001234",
                        "titulo": "Laptop not turning on",
                        "status": "open",
                        "prioridade": "high",
                        "criado_em": "2023-10-31T10:30:00"
                    }
                ],
                "total": 1,
                "limit": 100,
                "offset": 0
            }
        }


class TicketAnalyticsResponse(BaseModel):
    """Response model for ticket analytics."""
    
    total_tickets: int = Field(..., description="Total number of tickets")
    by_status: Dict[str, int] = Field(..., description="Ticket count by status")
    by_priority: Dict[str, int] = Field(..., description="Ticket count by priority")
    sla_breaches: Dict[str, int] = Field(..., description="SLA breach counts")
    escalation_recommendations: List[Dict[str, Any]] = Field(..., description="Tickets needing escalation")

    class Config:
        schema_extra = {
            "example": {
                "total_tickets": 150,
                "by_status": {"open": 45, "in_progress": 30, "resolved": 75},
                "by_priority": {"low": 50, "normal": 70, "high": 25, "urgent": 5},
                "sla_breaches": {"response_breaches": 3, "resolution_breaches": 8, "escalation_needed": 2},
                "escalation_recommendations": [
                    {
                        "ticket_id": 123,
                        "ticket_number": "TKT-2023-001123",
                        "recommendation": "Escalate to manager - ticket requires immediate attention"
                    }
                ]
            }
        }


class ServiceOrderDetailResponse(BaseModel):
    """Detailed service order response model."""
    
    id: int = Field(..., description="Service order ID", example=321)
    numero_os: Optional[str] = Field(None, description="Service order number", example="OS-1-2023-12345")
    chamado_id: Optional[int] = Field(None, description="Linked ticket ID", example=789)
    tipo_os: Optional[str] = Field(None, description="Service order type", example="Maintenance")
    atividades_realizadas: Optional[str] = Field(None, description="Activities performed")
    observacao: Optional[str] = Field(None, description="Observations and notes")
    numero_apr: Optional[str] = Field(None, description="APR number", example="APR-2023-001")
    data_hora_inicio: Optional[str] = Field(None, description="Start timestamp")
    data_hora_fim: Optional[str] = Field(None, description="End timestamp")
    duracao: Optional[str] = Field(None, description="Duration", example="2h 30m")
    status: Optional[str] = Field(None, description="Current status", example="in_progress")
    activities: Optional[List[Dict[str, Any]]] = Field(None, description="Activity log entries")
    time_tracking: Optional[Dict[str, Any]] = Field(None, description="Time tracking information")

    class Config:
        schema_extra = {
            "example": {
                "id": 321,
                "numero_os": "OS-1-2023-12345",
                "chamado_id": 789,
                "tipo_os": "Maintenance",
                "atividades_realizadas": "Diagnosed and replaced faulty component",
                "observacao": "Customer satisfied with repair",
                "numero_apr": "APR-2023-001",
                "data_hora_inicio": "2023-10-31T09:00:00",
                "data_hora_fim": "2023-10-31T11:30:00",
                "duracao": "2h 30m",
                "status": "completed",
                "activities": [
                    {
                        "timestamp": "2023-10-31T09:00:00",
                        "activity_type": "DIAGNOSTIC",
                        "description": "Initial diagnosis",
                        "duration_minutes": 30,
                        "billable": True
                    }
                ],
                "time_tracking": {
                    "total_hours": 2.5,
                    "billable_hours": 2.0
                }
            }
        }


class UpdateServiceOrderRequest(BaseModel):
    """Request model for updating a service order."""
    
    atividades_realizadas: Optional[constr(max_length=2000)] = Field(  # type: ignore[valid-type]
        None,
        description="Updated activities performed",
        example="Completed hardware replacement and system testing"
    )
    observacao: Optional[constr(max_length=1000)] = Field(  # type: ignore[valid-type]
        None,
        description="Updated observations and notes",
        example="All systems functioning normally after repair"
    )
    numero_apr: Optional[constr(max_length=50)] = Field(  # type: ignore[valid-type]
        None,
        description="Updated APR number",
        example="APR-2023-002"
    )
    data_hora_inicio: Optional[str] = Field(
        None,
        description="Start timestamp (ISO format)",
        example="2023-10-31T09:00:00"
    )
    data_hora_fim: Optional[str] = Field(
        None,
        description="End timestamp (ISO format)",
        example="2023-10-31T11:30:00"
    )
    comment: Optional[constr(max_length=500)] = Field(  # type: ignore[valid-type]
        None,
        description="Comment explaining the update",
        example="Updated completion time and final observations"
    )

    class Config:
        schema_extra = {
            "example": {
                "atividades_realizadas": "Completed hardware replacement and system testing",
                "observacao": "All systems functioning normally after repair",
                "data_hora_fim": "2023-10-31T11:30:00",
                "comment": "Service order completed successfully"
            }
        }


class AddActivityRequest(BaseModel):
    """Request model for adding an activity to a service order."""
    
    activity_type: str = Field(
        ...,
        description="Type of activity performed",
        example="REPAIR"
    )
    description: constr(min_length=1, max_length=500) = Field(  # type: ignore[valid-type]
        ...,
        description="Description of the activity",
        example="Replaced faulty motherboard and tested functionality"
    )
    duration_minutes: Optional[int] = Field(
        None,
        ge=0,
        le=1440,
        description="Duration in minutes (0-1440)",
        example=120
    )
    billable: bool = Field(
        True,
        description="Whether this activity is billable",
        example=True
    )

    class Config:
        schema_extra = {
            "example": {
                "activity_type": "REPAIR",
                "description": "Replaced faulty motherboard and tested functionality",
                "duration_minutes": 120,
                "billable": True
            }
        }


class ServiceOrderFilters(BaseModel):
    """Filters for service order listing."""
    
    tipo_os_id: Optional[int] = Field(None, gt=0, description="Filter by service order type ID")
    chamado_id: Optional[int] = Field(None, gt=0, description="Filter by linked ticket ID")
    numero_apr: Optional[constr(max_length=50)] = Field(  # type: ignore[valid-type]
        None,
        description="Filter by APR number",
        example="APR-2023"
    )
    search: Optional[constr(max_length=100)] = Field(  # type: ignore[valid-type]
        None,
        description="Search in service order number, activities, or observations",
        example="motherboard"
    )
    limit: Optional[int] = Field(100, ge=1, le=500, description="Maximum number of results")
    offset: Optional[int] = Field(0, ge=0, description="Number of results to skip")

    class Config:
        schema_extra = {
            "example": {
                "tipo_os_id": 1,
                "search": "motherboard",
                "limit": 50,
                "offset": 0
            }
        }


class ServiceOrderListResponse(BaseModel):
    """Response model for service order listing."""
    
    service_orders: List[ServiceOrderDetailResponse] = Field(..., description="List of service orders")
    total: int = Field(..., description="Total number of service orders matching filters")
    limit: int = Field(..., description="Applied limit")
    offset: int = Field(..., description="Applied offset")

    class Config:
        schema_extra = {
            "example": {
                "service_orders": [
                    {
                        "id": 321,
                        "numero_os": "OS-1-2023-12345",
                        "chamado_id": 789,
                        "tipo_os": "Maintenance",
                        "status": "completed"
                    }
                ],
                "total": 1,
                "limit": 100,
                "offset": 0
            }
        }


class ServiceOrderAnalyticsResponse(BaseModel):
    """Response model for service order analytics."""
    
    total_service_orders: int = Field(..., description="Total number of service orders")
    by_type: Dict[str, int] = Field(..., description="Service order count by type")
    completion_stats: Dict[str, int] = Field(..., description="Completion statistics")
    time_tracking: Dict[str, float] = Field(..., description="Time tracking statistics")

    class Config:
        schema_extra = {
            "example": {
                "total_service_orders": 75,
                "by_type": {"maintenance": 30, "installation": 25, "repair": 20},
                "completion_stats": {"completed": 50, "in_progress": 15, "pending": 10},
                "time_tracking": {
                    "total_hours": 320.5,
                    "billable_hours": 280.0,
                    "average_duration": 4.27
                }
            }
        }