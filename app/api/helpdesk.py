from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.tenant import get_tenant_context, TenantContext
from app.core.authorization import (
    get_authorization_context, AuthorizationContext,
    Permission, require_agent_or_admin_role, require_any_authenticated_role,
    ResourceOwnershipValidator
)
from app.core.exceptions import business_exception_to_http, BusinessLogicError
from app.repositories.ativo import AtivoRepository
from app.services.inventory import InventoryService
from app.services.ticket import TicketService
from app.services.ordem_servico import OrdemServicoService
from app.schemas.helpdesk import (
    InventoryIntakeRequest,
    InventoryIntakeResponse,
    CreateTicketRequest,
    CreateTicketResponse,
    CreateServiceOrderRequest,
    CreateServiceOrderResponse,
    AssetSummary,
    ErrorResponse,
    TicketDetailResponse,
    UpdateTicketRequest,
    TicketFilters,
    TicketListResponse,
    TicketAnalyticsResponse,
    ServiceOrderDetailResponse,
    UpdateServiceOrderRequest,
    AddActivityRequest,
    ServiceOrderFilters,
    ServiceOrderListResponse,
    ServiceOrderAnalyticsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/helpdesk", tags=["helpdesk"])


@router.post(
    "/inventory/intake",
    response_model=InventoryIntakeResponse,
    responses={
        200: {"description": "Inventory item created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input data"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Catalog item not found"},
        409: {"model": ErrorResponse, "description": "Serial number conflict"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Process inventory intake",
    description="Add a new item to inventory with optional automatic asset creation. Requires agent or admin role and manage inventory permission."
)
async def inventory_intake(
    payload: InventoryIntakeRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_agent_or_admin_role),
) -> InventoryIntakeResponse:
    """
    Process inventory intake with automatic asset creation.
    Requires agent or admin role.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_INVENTORY):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to manage inventory"
            )
        
        svc = InventoryService()
        estoque, ativo = await svc.intake(
            session=session,
            empresa_id=auth_context.tenant.empresa_id,
            catalogo_peca_id=payload.catalogo_peca_id,
            serial=payload.serial,
            status_estoque_id=payload.status_estoque_id,
            qtd=int(payload.qtd or 1),
            auto_create_asset=payload.auto_create_asset,
        )
        await session.commit()
        
        logger.info(
            f"User {auth_context.user.id} created inventory item {estoque.id} "
            f"for empresa {auth_context.tenant.empresa_id}"
        )
        
        return InventoryIntakeResponse(
            estoque_id=estoque.id, 
            asset_id=(ativo.id if ativo else None), 
            serial=estoque.serial
        )
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error in inventory intake: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error in inventory intake: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during inventory intake"
        )


@router.get(
    "/assets",
    response_model=List[AssetSummary],
    responses={
        200: {"description": "List of assets for the current company"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="List company assets",
    description="Retrieve a list of all assets belonging to the authenticated user's company. Requires view assets permission."
)
async def list_assets(
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
) -> List[AssetSummary]:
    """
    List assets for the current company.
    Requires view assets permission.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.VIEW_ASSETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view assets"
            )
        
        repo = AtivoRepository()
        items = await repo.list_by_empresa(session, auth_context.tenant.empresa_id)
        
        logger.debug(f"User {auth_context.user.id} listed {len(items)} assets")
        
        return [
            AssetSummary(
                id=a.id,
                serial_text=a.serial_text,
                descricao=a.descricao,
                tag=a.tag,
                criado_em=a.criado_em.isoformat() if a.criado_em else None
            )
            for a in items
        ]
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error listing assets: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error listing assets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing assets"
        )


@router.post("/tickets", response_model=CreateTicketResponse)
async def create_ticket(
    payload: CreateTicketRequest,
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> CreateTicketResponse:
    ativo_id: Optional[int] = payload.ativo_id
    if not ativo_id and payload.serial_text:
        # Resolve by serial_text within empresa
        repo = AtivoRepository()
        a = await repo.get_by_serial_text(session, tenant.empresa_id, payload.serial_text)
        if a:
            ativo_id = a.id
    # Build ticket
    if payload.titulo is None or payload.titulo.strip() == "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Titulo é obrigatório")
    ticket_svc = TicketService()
    ticket = await ticket_svc.create_with_asset(
        session=session,
        empresa_id=tenant.empresa_id,
        solicitante_id=payload.solicitante_id or tenant.contato_id,
        ativo_id=ativo_id,
        titulo=payload.titulo,
        descricao=payload.descricao,
        prioridade_id=payload.prioridade_id,
        status_id=payload.status_id,
        categoria_id=payload.categoria_id,
    )
    await session.commit()
    return CreateTicketResponse(id=ticket.id, numero=ticket.numero, ativo_id=ticket.ativo_id)


@router.post("/service-orders", response_model=CreateServiceOrderResponse)
async def create_service_order(
    payload: CreateServiceOrderRequest,
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> CreateServiceOrderResponse:
    svc = OrdemServicoService()
    os = await svc.create(
        session=session,
        empresa_id=tenant.empresa_id,
        chamado_id=payload.chamado_id,
        tipo_os_id=payload.tipo_os_id,
        atividades_realizadas=payload.atividades_realizadas,
        observacao=payload.observacao,
        numero_apr=payload.numero_apr,
    )
    await session.commit()
    return CreateServiceOrderResponse(id=os.id, chamado_id=os.chamado_id)


@router.get(
    "/tickets",
    response_model=TicketListResponse,
    responses={
        200: {"description": "List of tickets with filtering and pagination"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="List tickets with filtering",
    description="Retrieve a paginated list of tickets with optional filtering by status, priority, assignment, etc."
)
async def list_tickets(
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
    status_id: Optional[int] = None,
    prioridade_id: Optional[int] = None,
    categoria_id: Optional[int] = None,
    agente_contato_id: Optional[int] = None,
    requisitante_contato_id: Optional[int] = None,
    ativo_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> TicketListResponse:
    """
    List tickets with comprehensive filtering and pagination.
    Requires view tickets permission.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.VIEW_TICKETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view tickets"
            )
        
        # Build filters
        filters = {}
        if status_id:
            filters["status_id"] = status_id
        if prioridade_id:
            filters["prioridade_id"] = prioridade_id
        if categoria_id:
            filters["categoria_id"] = categoria_id
        if agente_contato_id:
            filters["agente_contato_id"] = agente_contato_id
        if requisitante_contato_id:
            filters["requisitante_contato_id"] = requisitante_contato_id
        if ativo_id:
            filters["ativo_id"] = ativo_id
        if search:
            filters["search"] = search
        
        # For requesters, only show their own tickets
        if auth_context.role == "requester":
            filters["requisitante_contato_id"] = auth_context.user.contato_id
        
        ticket_svc = TicketService()
        tickets = await ticket_svc.list_tickets(
            session, auth_context.tenant.empresa_id, filters, limit, offset
        )
        
        # Convert to response format
        ticket_responses = []
        for ticket in tickets:
            ticket_detail = await _build_ticket_detail_response(
                session, ticket, auth_context.role
            )
            ticket_responses.append(ticket_detail)
        
        # Get total count (simplified - in production, use a separate count query)
        total = len(tickets)  # This is approximate for pagination
        
        logger.debug(f"Listed {len(tickets)} tickets for user {auth_context.user.id}")
        
        return TicketListResponse(
            tickets=ticket_responses,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error listing tickets: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error listing tickets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing tickets"
        )


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    responses={
        200: {"description": "Ticket details with SLA status and next actions"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Ticket not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get ticket details",
    description="Retrieve detailed information about a specific ticket including SLA status and suggested next actions."
)
async def get_ticket(
    ticket_id: int,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
) -> TicketDetailResponse:
    """
    Get detailed ticket information with workflow context.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.VIEW_TICKETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view tickets"
            )
        
        ticket_svc = TicketService()
        ticket = await ticket_svc.get_by_id(
            session, auth_context.tenant.empresa_id, ticket_id
        )
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found"
            )
        
        # Check if requester can only view their own tickets
        if auth_context.role == "requester":
            if ticket.requisitante_contato_id != auth_context.user.contato_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own tickets"
                )
        
        # Build detailed response
        ticket_detail = await _build_ticket_detail_response(
            session, ticket, auth_context.role, include_sla=True, include_actions=True
        )
        
        logger.debug(f"Retrieved ticket {ticket.numero} for user {auth_context.user.id}")
        
        return ticket_detail
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error getting ticket {ticket_id}: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error getting ticket {ticket_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the ticket"
        )


@router.put(
    "/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    responses={
        200: {"description": "Ticket updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid update data"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Ticket not found"},
        409: {"model": ErrorResponse, "description": "Invalid status transition"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Update ticket",
    description="Update ticket fields with workflow validation. Status changes are validated against the ticket state machine."
)
async def update_ticket(
    ticket_id: int,
    payload: UpdateTicketRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
) -> TicketDetailResponse:
    """
    Update a ticket with comprehensive workflow validation.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_TICKETS):
            # Requesters can only update their own tickets with limited fields
            if auth_context.role != "requester":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to update tickets"
                )
        
        # Convert payload to updates dict
        updates = {}
        for field, value in payload.dict(exclude_unset=True).items():
            if field != "comment":  # Comment is handled separately
                updates[field] = value
        
        # Requesters have limited update capabilities
        if auth_context.role == "requester":
            allowed_fields = {"titulo", "descricao"}
            invalid_fields = set(updates.keys()) - allowed_fields
            if invalid_fields:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requesters cannot update fields: {', '.join(invalid_fields)}"
                )
        
        ticket_svc = TicketService()
        updated_ticket = await ticket_svc.update_ticket(
            session=session,
            empresa_id=auth_context.tenant.empresa_id,
            ticket_id=ticket_id,
            user_id=auth_context.user.contato_id,
            user_role=auth_context.role,
            updates=updates,
            comment=payload.comment
        )
        
        await session.commit()
        
        # Build response with updated information
        ticket_detail = await _build_ticket_detail_response(
            session, updated_ticket, auth_context.role, include_sla=True, include_actions=True
        )
        
        logger.info(f"Updated ticket {updated_ticket.numero} by user {auth_context.user.id}")
        
        return ticket_detail
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error updating ticket {ticket_id}: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error updating ticket {ticket_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the ticket"
        )


@router.get(
    "/analytics",
    response_model=TicketAnalyticsResponse,
    responses={
        200: {"description": "Ticket analytics and SLA status"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get ticket analytics",
    description="Retrieve comprehensive ticket analytics including SLA breaches and escalation recommendations."
)
async def get_ticket_analytics(
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
    user_specific: bool = False,
) -> TicketAnalyticsResponse:
    """
    Get comprehensive ticket analytics with SLA tracking.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.VIEW_TICKETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view analytics"
            )
        
        # For requesters, always show only their analytics
        if auth_context.role == "requester":
            user_specific = True
        
        ticket_svc = TicketService()
        analytics = await ticket_svc.get_ticket_analytics(
            session=session,
            empresa_id=auth_context.tenant.empresa_id,
            user_id=auth_context.user.contato_id if user_specific else None
        )
        
        logger.debug(f"Generated analytics for user {auth_context.user.id}")
        
        return TicketAnalyticsResponse(**analytics)
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error getting analytics: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error getting analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating analytics"
        )


async def _build_ticket_detail_response(
    session: AsyncSession,
    ticket: "Chamado",
    user_role: str,
    include_sla: bool = False,
    include_actions: bool = False
) -> TicketDetailResponse:
    """Helper function to build detailed ticket response."""
    from app.core.ticket_workflow import TicketWorkflowEngine
    from datetime import datetime
    
    # Build basic response
    response_data = {
        "id": ticket.id,
        "numero": ticket.numero,
        "titulo": ticket.titulo,
        "descricao": ticket.descricao,
        "status": ticket.status.nome if ticket.status else None,
        "prioridade": ticket.prioridade.nome if ticket.prioridade else None,
        "categoria": ticket.categoria.nome if ticket.categoria else None,
        "ativo_id": ticket.ativo_id,
        "requisitante": ticket.requisitante.nome if ticket.requisitante else None,
        "agente": ticket.agente.nome if ticket.agente else None,
        "criado_em": ticket.criado_em.isoformat() if ticket.criado_em else None,
        "atualizado_em": ticket.atualizado_em.isoformat() if ticket.atualizado_em else None,
        "fechado_em": ticket.fechado_em.isoformat() if ticket.fechado_em else None,
    }
    
    # Add SLA information if requested
    if include_sla:
        workflow = TicketWorkflowEngine()
        sla_breaches = workflow.check_sla_breaches(ticket, datetime.utcnow())
        response_data["sla_status"] = sla_breaches
    
    # Add next actions if requested
    if include_actions:
        workflow = TicketWorkflowEngine()
        next_actions = workflow.suggest_next_actions(ticket, user_role)
        response_data["next_actions"] = next_actions
    
    return TicketDetailResponse(**response_data)


@router.get(
    "/service-orders",
    response_model=ServiceOrderListResponse,
    responses={
        200: {"description": "List of service orders with filtering and pagination"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="List service orders with filtering",
    description="Retrieve a paginated list of service orders with optional filtering by type, ticket, etc."
)
async def list_service_orders(
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
    tipo_os_id: Optional[int] = None,
    chamado_id: Optional[int] = None,
    numero_apr: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> ServiceOrderListResponse:
    """
    List service orders with comprehensive filtering and pagination.
    Requires manage service orders permission.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_SERVICE_ORDERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view service orders"
            )
        
        # Build filters
        filters = {}
        if tipo_os_id:
            filters["tipo_os_id"] = tipo_os_id
        if chamado_id:
            filters["chamado_id"] = chamado_id
        if numero_apr:
            filters["numero_apr"] = numero_apr
        if search:
            filters["search"] = search
        
        service_order_svc = OrdemServicoService()
        service_orders = await service_order_svc.list_service_orders(
            session, auth_context.tenant.empresa_id, filters, limit, offset
        )
        
        # Convert to response format
        so_responses = []
        for so in service_orders:
            so_detail = await _build_service_order_detail_response(session, so)
            so_responses.append(so_detail)
        
        # Get total count (simplified - in production, use a separate count query)
        total = len(service_orders)  # This is approximate for pagination
        
        logger.debug(f"Listed {len(service_orders)} service orders for user {auth_context.user.id}")
        
        return ServiceOrderListResponse(
            service_orders=so_responses,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error listing service orders: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error listing service orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing service orders"
        )


@router.get(
    "/service-orders/{service_order_id}",
    response_model=ServiceOrderDetailResponse,
    responses={
        200: {"description": "Service order details with activity tracking"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Service order not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get service order details",
    description="Retrieve detailed information about a specific service order including activity log and time tracking."
)
async def get_service_order(
    service_order_id: int,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
) -> ServiceOrderDetailResponse:
    """
    Get detailed service order information with activity tracking.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_SERVICE_ORDERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view service orders"
            )
        
        service_order_svc = OrdemServicoService()
        so = await service_order_svc.get_by_id(
            session, auth_context.tenant.empresa_id, service_order_id
        )
        
        if not so:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service order with ID {service_order_id} not found"
            )
        
        # Build detailed response
        so_detail = await _build_service_order_detail_response(
            session, so, include_activities=True, include_time_tracking=True
        )
        
        logger.debug(f"Retrieved service order {so.numero_os} for user {auth_context.user.id}")
        
        return so_detail
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error getting service order {service_order_id}: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error getting service order {service_order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the service order"
        )


@router.put(
    "/service-orders/{service_order_id}",
    response_model=ServiceOrderDetailResponse,
    responses={
        200: {"description": "Service order updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid update data"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Service order not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Update service order",
    description="Update service order fields with activity logging and time tracking."
)
async def update_service_order(
    service_order_id: int,
    payload: UpdateServiceOrderRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
) -> ServiceOrderDetailResponse:
    """
    Update a service order with comprehensive activity logging.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_SERVICE_ORDERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update service orders"
            )
        
        # Convert payload to updates dict
        updates = {}
        for field, value in payload.dict(exclude_unset=True).items():
            if field != "comment":  # Comment is handled separately
                updates[field] = value
        
        # Parse datetime fields if provided
        if "data_hora_inicio" in updates and updates["data_hora_inicio"]:
            try:
                from datetime import datetime
                updates["data_hora_inicio"] = datetime.fromisoformat(updates["data_hora_inicio"].replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid datetime format for data_hora_inicio. Use ISO format."
                )
        
        if "data_hora_fim" in updates and updates["data_hora_fim"]:
            try:
                from datetime import datetime
                updates["data_hora_fim"] = datetime.fromisoformat(updates["data_hora_fim"].replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid datetime format for data_hora_fim. Use ISO format."
                )
        
        service_order_svc = OrdemServicoService()
        updated_so = await service_order_svc.update_service_order(
            session=session,
            empresa_id=auth_context.tenant.empresa_id,
            service_order_id=service_order_id,
            user_id=auth_context.user.contato_id,
            user_role=auth_context.role,
            updates=updates,
            comment=payload.comment
        )
        
        await session.commit()
        
        # Build response with updated information
        so_detail = await _build_service_order_detail_response(
            session, updated_so, include_activities=True, include_time_tracking=True
        )
        
        logger.info(f"Updated service order {updated_so.numero_os} by user {auth_context.user.id}")
        
        return so_detail
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error updating service order {service_order_id}: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error updating service order {service_order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the service order"
        )


@router.post(
    "/service-orders/{service_order_id}/activities",
    responses={
        200: {"description": "Activity added successfully"},
        400: {"model": ErrorResponse, "description": "Invalid activity data"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Service order not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Add activity to service order",
    description="Add a new activity entry to a service order with time tracking."
)
async def add_service_order_activity(
    service_order_id: int,
    payload: AddActivityRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
):
    """
    Add an activity entry to a service order.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_SERVICE_ORDERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to add activities to service orders"
            )
        
        # Verify service order exists and belongs to company
        service_order_svc = OrdemServicoService()
        so = await service_order_svc.get_by_id(
            session, auth_context.tenant.empresa_id, service_order_id
        )
        
        if not so:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service order with ID {service_order_id} not found"
            )
        
        # Add the activity
        activity_data = payload.dict()
        await service_order_svc.add_activity(
            session, service_order_id, auth_context.user.contato_id, activity_data
        )
        
        await session.commit()
        
        logger.info(f"Added activity to service order {so.numero_os} by user {auth_context.user.id}")
        
        return {"message": "Activity added successfully"}
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error adding activity to service order {service_order_id}: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error adding activity to service order {service_order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding the activity"
        )


@router.get(
    "/service-orders/analytics",
    response_model=ServiceOrderAnalyticsResponse,
    responses={
        200: {"description": "Service order analytics and time tracking"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get service order analytics",
    description="Retrieve comprehensive service order analytics including time tracking and completion rates."
)
async def get_service_order_analytics(
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
    user_specific: bool = False,
) -> ServiceOrderAnalyticsResponse:
    """
    Get comprehensive service order analytics with time tracking.
    """
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_SERVICE_ORDERS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view service order analytics"
            )
        
        service_order_svc = OrdemServicoService()
        analytics = await service_order_svc.get_service_order_analytics(
            session=session,
            empresa_id=auth_context.tenant.empresa_id,
            user_id=auth_context.user.contato_id if user_specific else None
        )
        
        logger.debug(f"Generated service order analytics for user {auth_context.user.id}")
        
        return ServiceOrderAnalyticsResponse(**analytics)
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error getting service order analytics: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error getting service order analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating analytics"
        )


async def _build_service_order_detail_response(
    session: AsyncSession,
    service_order: "OrdemServico",
    include_activities: bool = False,
    include_time_tracking: bool = False
) -> ServiceOrderDetailResponse:
    """Helper function to build detailed service order response."""
    import json
    from app.core.service_order_workflow import ServiceOrderWorkflowEngine
    
    # Build basic response
    response_data = {
        "id": service_order.id,
        "numero_os": service_order.numero_os,
        "chamado_id": service_order.chamado_id,
        "tipo_os": service_order.tipo.nome if service_order.tipo else None,
        "atividades_realizadas": service_order.atividades_realizadas,
        "observacao": service_order.observacao,
        "numero_apr": service_order.numero_apr,
        "data_hora_inicio": service_order.data_hora_inicio.isoformat() if service_order.data_hora_inicio else None,
        "data_hora_fim": service_order.data_hora_fim.isoformat() if service_order.data_hora_fim else None,
        "duracao": service_order.duracao,
        "status": "draft",  # Default status (would be from actual status field in production)
    }
    
    # Add activities if requested
    if include_activities and service_order.observacao:
        try:
            activities = json.loads(service_order.observacao)
            if isinstance(activities, list):
                response_data["activities"] = activities
        except json.JSONDecodeError:
            # If observacao is not JSON, treat as single note
            response_data["activities"] = [{"description": service_order.observacao, "type": "note"}]
    
    # Add time tracking if requested
    if include_time_tracking and service_order.data_hora_inicio:
        workflow = ServiceOrderWorkflowEngine()
        if service_order.data_hora_fim:
            duration = workflow.calculate_duration(service_order.data_hora_inicio, service_order.data_hora_fim)
            response_data["time_tracking"] = {
                "total_hours": round(duration / 60, 2),
                "billable_hours": round(duration / 60, 2),  # Simplified - would calculate from activities
                "duration_minutes": duration
            }
    
    return ServiceOrderDetailResponse(**response_data)