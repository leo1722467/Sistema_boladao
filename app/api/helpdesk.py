from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

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
from app.db.models import StatusChamado, Prioridade, Contato
from app.repositories.chamado_defeito import ChamadoDefeitoRepository
from app.schemas.helpdesk import (
    InventoryIntakeRequest,
    InventoryIntakeResponse,
    CreateTicketRequest,
    CreateTicketResponse,
    CreateServiceOrderRequest,
    CreateServiceOrderResponse,
    AssetSummary,
    NamedEntity,
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
    CreateDefeitoRequest,
    DefeitoResponse,
    DefeitoListResponse,
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
        
        # Be tolerant with timestamp types: handle datetime and string
        from datetime import datetime as _dt

        def _format_created(value: Any) -> Optional[str]:
            if value is None:
                return None
            try:
                if isinstance(value, _dt):
                    return value.isoformat()
                # Already a string or other printable type
                return str(value)
            except Exception:
                # Fallback without breaking listing
                return None

        summaries: List[AssetSummary] = []
        for a in items:
            try:
                tipo = None
                if getattr(a, "tipo", None) is not None:
                    try:
                        tipo = NamedEntity(id=getattr(a.tipo, "id", None), nome=getattr(a.tipo, "nome", None))
                    except Exception:
                        tipo = None

                status = None
                if getattr(a, "status", None) is not None:
                    try:
                        status = NamedEntity(id=getattr(a.status, "id", None), nome=getattr(a.status, "nome", None))
                    except Exception:
                        status = None

                local_instalacao = None
                if getattr(a, "local_instalacao", None) is not None:
                    try:
                        local_instalacao = NamedEntity(id=getattr(a.local_instalacao, "id", None), nome=getattr(a.local_instalacao, "nome", None))
                    except Exception:
                        local_instalacao = None

                summaries.append(
                    AssetSummary(
                        id=a.id,
                        serial_text=getattr(a, "serial_text", None),
                        descricao=a.descricao,
                        tag=a.tag,
                        criado_em=_format_created(getattr(a, "criado_em", None)),
                        tipo=tipo,
                        status=status,
                        local_instalacao=local_instalacao,
                    )
                )
            except Exception as item_err:
                logger.warning(
                    f"Skipping asset {getattr(a, 'id', '?')} due to serialization error: {item_err}"
                )
                continue

        return summaries
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error listing assets: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error listing assets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"list_assets failed: {e}"
        )


@router.post("/tickets", response_model=TicketDetailResponse)
async def create_ticket(
    payload: CreateTicketRequest,
    session: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
) -> TicketDetailResponse:
    try:
        ativo_id: Optional[int] = payload.ativo_id
        if not ativo_id and payload.serial_text:
            repo = AtivoRepository()
            a = await repo.get_by_serial_text(session, tenant.empresa_id, payload.serial_text)
            if a:
                ativo_id = a.id
        if payload.titulo is None or payload.titulo.strip() == "":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Titulo é obrigatório")

        prioridade_id = payload.prioridade_id
        status_id = None
        try:
            if not prioridade_id:
                pr_text = (payload.prioridade or payload.priority or "").strip().lower()
                if pr_text:
                    result = await session.execute(select(Prioridade).where(Prioridade.nome.ilike(f"%{pr_text}%")))
                    prow = result.scalars().first()
                    if prow:
                        prioridade_id = prow.id
        except Exception:
            pass

        ticket_svc = TicketService()
        ticket = await ticket_svc.create_with_asset(
            session=session,
            empresa_id=tenant.empresa_id,
            solicitante_id=payload.solicitante_id or tenant.contato_id,
            ativo_id=ativo_id,
            titulo=payload.titulo,
            descricao=payload.descricao,
            prioridade_id=prioridade_id,
            status_id=status_id,
            categoria_id=payload.categoria_id,
            origem=(payload.origem or "web"),
        )
        await session.commit()
        try:
            await session.refresh(ticket, ['status', 'prioridade', 'categoria', 'requisitante', 'agente', 'comentarios'])
        except Exception:
            pass
        detail = await _build_ticket_detail_response(
            session, ticket, auth_context.role, include_sla=True, include_actions=False
        )
        return detail
    except BusinessLogicError as e:
        logger.warning(f"Business error creating ticket: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except IntegrityError as e:
        logger.exception(f"DB integrity error in create_ticket: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"IntegrityError: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error in create_ticket: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e.__class__.__name__}: {str(e)}")


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
    # UI-friendly textual filters
    status: Optional[str] = None,
    priority: Optional[str] = None,
    agent: Optional[str] = None,
    sla: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    page: int = 1,
) -> TicketListResponse:
    """
    List tickets with comprehensive filtering and pagination.
    Requires view tickets permission.
    """
    try:
        # Check permission
        if auth_context.role == "requester":
            if not auth_context.has_permission(Permission.VIEW_OWN_TICKETS):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view own tickets"
                )
        else:
            if not auth_context.has_permission(Permission.VIEW_TICKETS):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view tickets"
                )
        
        # Build filters
        filters: Dict[str, Any] = {}
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
        
        # Map textual filters to IDs
        if status and not filters.get("status_id"):
            status_name = status.strip().lower()
            result = await session.execute(select(StatusChamado).where(StatusChamado.nome.ilike(f"%{status_name}%")))
            row = result.scalars().first()
            if row:
                filters["status_id"] = row.id
        if priority and not filters.get("prioridade_id"):
            priority_name = priority.strip().lower()
            result = await session.execute(select(Prioridade).where(Prioridade.nome.ilike(f"%{priority_name}%")))
            prow = result.scalars().first()
            if prow:
                filters["prioridade_id"] = prow.id
        if agent and not filters.get("agente_contato_id"):
            agent_val = agent.strip().lower()
            if agent_val == "unassigned":
                # will filter after response build
                pass
            else:
                # try parse ID or resolve by name
                try:
                    filters["agente_contato_id"] = int(agent_val)
                except ValueError:
                    result = await session.execute(select(Contato).where(Contato.nome.ilike(f"%{agent}%")))
                    contact = result.scalars().first()
                    if contact:
                        filters["agente_contato_id"] = contact.id
        
        # For requesters, only show their own tickets
        if auth_context.role == "requester":
            filters["requisitante_contato_id"] = auth_context.user.contato_id
        
        # Compute offset from page
        computed_offset = offset
        if page and page > 1:
            computed_offset = (page - 1) * limit
        
        ticket_svc = TicketService()
        tickets = await ticket_svc.list_tickets(
            session, auth_context.tenant.empresa_id, filters, limit, computed_offset
        )
        
        # Convert to response format
        ticket_responses = []
        for ticket in tickets:
            ticket_detail = await _build_ticket_detail_response(
                session, ticket, auth_context.role, include_sla=True, include_actions=False
            )
            ticket_responses.append(ticket_detail)

        # Apply SLA filter if provided
        if sla:
            wanted = sla.strip().lower()
            ticket_responses = [t for t in ticket_responses if (t.sla_status or "").lower() == wanted]
        
        # Get total count (simplified - in production, use a separate count query)
        total = len(ticket_responses)
        total_pages = 1
        if limit:
            total_pages = max(1, (total + limit - 1) // limit)
        
        logger.debug(f"Listed {len(tickets)} tickets for user {auth_context.user.id}")
        
        return TicketListResponse(
            tickets=ticket_responses,
            total=total,
            limit=limit,
            offset=computed_offset,
            page=page,
            total_pages=total_pages
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
        
        # Build detailed response (include comments)
        try:
            await session.refresh(ticket, ['comentarios'])
        except Exception:
            pass
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
        # If requester, ensure they are the ticket owner (requisitante)
        if auth_context.role == "requester":
            # Load ticket with cross-tenant access for attendants only
            tsvc_chk = TicketService()
            ticket_chk = await tsvc_chk.get_by_id(session, auth_context.tenant.empresa_id, ticket_id)
            if not ticket_chk:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
            if ticket_chk.requisitante_contato_id != auth_context.user.contato_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requesters can only comment on their own tickets")
        
        # Convert payload to updates dict
        updates = {}
        for field, value in payload.dict(exclude_unset=True).items():
            if field != "comment":  # Comment is handled separately
                updates[field] = value

        # Map textual status/priority to IDs for flexibility (supports EN/PT)
        try:
            svc_map = TicketService()
            if "status" in updates and updates["status"]:
                status_name = str(updates["status"]).strip().lower()
                srow = await svc_map._get_default_status(session, status_name)
                if srow:
                    updates["status_id"] = srow.id
                del updates["status"]
            if "priority" in updates and updates["priority"]:
                priority_name = str(updates["priority"]).strip().lower()
                prow = await svc_map._get_default_priority(session, priority_name)
                if prow:
                    updates["prioridade_id"] = prow.id
                del updates["priority"]
        except Exception:
            # Fail-safe: if mapping fails, continue with provided IDs only
            pass
        
        # Requesters can only send comments; no field updates allowed
        if auth_context.role == "requester":
            if updates:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Requesters can only add comments to their tickets"
                )
        
        ticket_svc = TicketService()
        updated_ticket = await ticket_svc.update_ticket(
            session=session,
            # Empresa 1 (atendente) tem controle total e pode atuar fora do tenant
            empresa_id=1 if auth_context.tenant.empresa_id == 1 else auth_context.tenant.empresa_id,
            ticket_id=ticket_id,
            user_id=auth_context.user.contato_id,
            user_role=auth_context.role,
            updates=updates,
            comment=payload.comment
        )
        
        await session.commit()
        
        # Build response with updated information
        try:
            await session.refresh(updated_ticket, ['comentarios'])
        except Exception:
            pass
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
        if auth_context.role == "requester":
            if not auth_context.has_permission(Permission.VIEW_OWN_TICKETS):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view own analytics"
                )
        else:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error getting analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while generating analytics: {e}"
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
    # Safely load relations to prevent async lazy-load MissingGreenlet
    try:
        from app.db.models import StatusChamado, Prioridade, ChamadoCategoria, Contato, Ativo
    except Exception:
        StatusChamado = Prioridade = ChamadoCategoria = Contato = Ativo = None  # type: ignore
    try:
        await session.refresh(ticket, ["status", "prioridade", "categoria", "requisitante", "agente", "ativo", "comentarios"])
    except Exception:
        pass
    status_rel = getattr(ticket, "status", None)
    prioridade_rel = getattr(ticket, "prioridade", None)
    categoria_rel = getattr(ticket, "categoria", None)
    requisitante_rel = getattr(ticket, "requisitante", None)
    agente_rel = getattr(ticket, "agente", None)
    ativo_rel = getattr(ticket, "ativo", None)
    try:
        if not status_rel and StatusChamado and getattr(ticket, "status_id", None):
            status_rel = await session.get(StatusChamado, ticket.status_id)
        if not prioridade_rel and Prioridade and getattr(ticket, "prioridade_id", None):
            prioridade_rel = await session.get(Prioridade, ticket.prioridade_id)
        if not categoria_rel and ChamadoCategoria and getattr(ticket, "categoria_id", None):
            categoria_rel = await session.get(ChamadoCategoria, ticket.categoria_id)
        if not requisitante_rel and Contato and getattr(ticket, "requisitante_contato_id", None):
            requisitante_rel = await session.get(Contato, ticket.requisitante_contato_id)
        if not agente_rel and Contato and getattr(ticket, "agente_contato_id", None):
            agente_rel = await session.get(Contato, ticket.agente_contato_id)
        if not ativo_rel and Ativo and getattr(ticket, "ativo_id", None):
            ativo_rel = await session.get(Ativo, ticket.ativo_id)
    except Exception:
        # If any relation fails to load, continue building with available data
        pass
    
    # Build basic response with normalized status/priority for UI
    def _status_code(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        n = name.strip().lower()
        mapping = {
            "novo": "new",
            "new": "new",
            "aberto": "open",
            "open": "open",
            "em andamento": "in_progress",
            "em atendimento": "in_progress",
            "in_progress": "in_progress",
            "em espera": "pending_customer",
            "espera": "pending_customer",
            "aguardando": "pending_customer",
            "aguardando cliente": "pending_customer",
            "pending_customer": "pending_customer",
            "resolvido": "resolved",
            "resolved": "resolved",
            "fechado": "closed",
            "closed": "closed",
        }
        return mapping.get(n, n)

    def _priority_code(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        n = name.strip().lower()
        mapping = {
            "baixa": "low",
            "low": "low",
            "normal": "normal",
            "alta": "high",
            "high": "high",
            "urgente": "urgent",
            "urgent": "urgent",
        }
        return mapping.get(n, n)

    created = ticket.criado_em or datetime.utcnow()
    updated = ticket.atualizado_em or ticket.criado_em or datetime.utcnow()
    response_data = {
        "id": ticket.id,
        "numero": str(ticket.numero or ""),
        "titulo": str(ticket.titulo or ""),
        "descricao": ticket.descricao,
        "status": _status_code(getattr(status_rel, "nome", None) if status_rel else None),
        "status_id": getattr(ticket, "status_id", None),
        "prioridade": _priority_code(getattr(prioridade_rel, "nome", None) if prioridade_rel else None),
        "prioridade_id": getattr(ticket, "prioridade_id", None),
        "priority": _priority_code(getattr(prioridade_rel, "nome", None) if prioridade_rel else None),
        "categoria": (categoria_rel.nome if categoria_rel and getattr(categoria_rel, "nome", None) else None),
        "ativo_id": ticket.ativo_id,
        "requisitante": ({"id": requisitante_rel.id, "nome": requisitante_rel.nome} if requisitante_rel else None),
        "agente": ({"id": agente_rel.id, "nome": agente_rel.nome} if agente_rel else None),
        "criado_em": created.isoformat(),
        "atualizado_em": updated.isoformat(),
        "fechado_em": ticket.fechado_em.isoformat() if ticket.fechado_em else None,
    }
    # Add comments history
    try:
        comments_list = []
        for c in getattr(ticket, 'comentarios', []) or []:
            contato = None
            try:
                if getattr(c, 'contato', None) is not None:
                    contato = {"id": getattr(c.contato, 'id', None), "nome": getattr(c.contato, 'nome', None)}
            except Exception:
                contato = None
            comments_list.append({
                "id": getattr(c, 'id', None),
                "contato": contato,
                "comentario": getattr(c, 'comentario', None),
                "data_hora": getattr(c, 'data_hora', None).isoformat() if getattr(c, 'data_hora', None) else None,
            })
        response_data["comentarios"] = comments_list
    except Exception:
        response_data["comentarios"] = []
    
    # Add SLA information if requested
    if include_sla:
        workflow = TicketWorkflowEngine()
        sla_breaches = workflow.check_sla_breaches(ticket, datetime.utcnow())
        # Map breaches to UI-friendly indicator
        if sla_breaches.get("response_breach") or sla_breaches.get("resolution_breach"):
            sla_indicator = "breach"
        elif sla_breaches.get("escalation_needed"):
            sla_indicator = "warning"
        else:
            sla_indicator = "ok"
        response_data["sla_status"] = sla_indicator
    
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
    page: int = 1,
) -> ServiceOrderListResponse:
    """
    List service orders with comprehensive filtering and pagination.
    Requires manage service orders permission.
    """
    try:
        if auth_context.role == UserRole.REQUESTER:
            if not auth_context.has_permission(Permission.VIEW_OWN_TICKETS):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view own service orders"
                )
        else:
            if not auth_context.has_permission(Permission.MANAGE_SERVICE_ORDERS):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to view service orders"
                )
        # Ensure tenant context is available
        if not auth_context.tenant or not auth_context.tenant.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuário sem empresa associada"
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
        if auth_context.role == UserRole.REQUESTER:
            filters["requisitante_contato_id"] = auth_context.tenant.contato_id
        
        # Compute offset from page for UI parity with tickets
        computed_offset = offset
        if page and page > 1:
            computed_offset = (page - 1) * limit
        
        service_order_svc = OrdemServicoService()
        service_orders = await service_order_svc.list_service_orders(
            session, auth_context.tenant.empresa_id, filters, limit, computed_offset
        )
        
        # Convert to response format
        so_responses = []
        for so in service_orders:
            so_detail = await _build_service_order_detail_response(session, so)
            so_responses.append(so_detail)
        
        # Get total count (simplified - in production, use a separate count query)
        total = len(service_orders)
        total_pages = 1
        if limit:
            total_pages = max(1, (total + limit - 1) // limit)
        
        logger.debug(f"Listed {len(service_orders)} service orders for user {auth_context.user.id}")
        
        return ServiceOrderListResponse(
            service_orders=so_responses,
            total=total,
            limit=limit,
            offset=computed_offset,
            page=page,
            total_pages=total_pages
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
        # Ensure tenant context is available
        if not auth_context.tenant or not auth_context.tenant.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuário sem empresa associada"
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error getting service order analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while generating analytics: {e}"
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


@router.get(
    "/defeitos",
    response_model=DefeitoListResponse,
    summary="List defects by asset type",
)
async def list_defeitos(
    tipo_ativo_id: int,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_any_authenticated_role),
) -> DefeitoListResponse:
    # Any authenticated user can list defects to open tickets
    repo = ChamadoDefeitoRepository()
    items = await repo.list_by_tipo_ativo(session, tipo_ativo_id)
    def _to_response(d) -> DefeitoResponse:
        ta = None
        try:
            if getattr(d, "tipo_ativo", None) is not None:
                ta = NamedEntity(id=getattr(d.tipo_ativo, "id", None), nome=getattr(d.tipo_ativo, "nome", None))
        except Exception:
            ta = None
        return DefeitoResponse(id=d.id, nome=d.nome, tipo_ativo=ta)
    return DefeitoListResponse(defeitos=[_to_response(d) for d in items])


@router.post(
    "/defeitos",
    response_model=DefeitoResponse,
    summary="Create defect for asset type",
)
async def create_defeito(
    payload: CreateDefeitoRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_agent_or_admin_role),
) -> DefeitoResponse:
    if not auth_context.has_permission(Permission.MANAGE_TICKETS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    repo = ChamadoDefeitoRepository()
    entity = await repo.create(session, nome=payload.nome, tipo_ativo_id=payload.tipo_ativo_id)
    await session.commit()
    ta = None
    try:
        await session.refresh(entity, ["tipo_ativo"])  
        if getattr(entity, "tipo_ativo", None) is not None:
            ta = NamedEntity(id=getattr(entity.tipo_ativo, "id", None), nome=getattr(entity.tipo_ativo, "nome", None))
    except Exception:
        ta = None
    return DefeitoResponse(id=entity.id, nome=entity.nome, tipo_ativo=ta)


@router.delete(
    "/defeitos/{defeito_id}",
    summary="Delete defect",
)
async def delete_defeito(
    defeito_id: int,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_agent_or_admin_role),
):
    if not auth_context.has_permission(Permission.MANAGE_TICKETS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    repo = ChamadoDefeitoRepository()
    ok = await repo.delete(session, defeito_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Defeito não encontrado")
    await session.commit()
    return {"message": "Defeito removido"}
@router.post(
    "/tickets/{ticket_id}/apply-macro",
    response_model=TicketDetailResponse,
    responses={
        200: {"description": "Macro aplicada com sucesso"},
        403: {"model": ErrorResponse, "description": "Permissões insuficientes"},
        404: {"model": ErrorResponse, "description": "Ticket ou Macro não encontrado"},
        500: {"model": ErrorResponse, "description": "Erro interno"}
    },
    summary="Aplicar macro no ticket",
    description="Aplica uma macro configurada no ticket e retorna o ticket atualizado."
)
async def apply_macro_endpoint(
    ticket_id: int,
    macro_id: int,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
) -> TicketDetailResponse:
    try:
        if not auth_context.has_permission(Permission.MANAGE_TICKETS):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to apply macros")
        tsvc = TicketService()
        updated = await tsvc.apply_macro(
            session=session,
            empresa_id=auth_context.tenant.empresa_id,
            ticket_id=ticket_id,
            macro_id=macro_id,
            user_id=auth_context.user.contato_id,
            user_role=auth_context.role,
        )
        await session.commit()
        try:
            await session.refresh(updated, ['comentarios'])
        except Exception:
            pass
        detail = await _build_ticket_detail_response(session, updated, auth_context.role, include_sla=True, include_actions=True)
        return detail
    except BusinessLogicError as e:
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while applying macro")
@router.get("/kb/articles")
async def kb_list(session: AsyncSession = Depends(get_db), auth: AuthorizationContext = Depends(get_authorization_context), q: Optional[str] = None, limit: int = 20):
    from app.db.models import KBArticle
    empresa_id = auth.tenant.empresa_id
    qstmt = select(KBArticle).where(KBArticle.empresa_id == empresa_id)
    if auth.role == "requester":
        from sqlalchemy import and_
        qstmt = qstmt.where(and_(KBArticle.publicado == True, KBArticle.visibilidade == "external"))
    if q:
        like = f"%{q}%"
        qstmt = qstmt.where((KBArticle.titulo.ilike(like)) | (KBArticle.conteudo.ilike(like)) | (KBArticle.resumo.ilike(like)))
    qstmt = qstmt.limit(limit)
    res = await session.execute(qstmt)
    items = res.scalars().all()
    return [{"id": a.id, "titulo": a.titulo, "resumo": a.resumo, "categoria_id": a.categoria_id, "visibilidade": a.visibilidade} for a in items]

@router.get("/kb/articles/{article_id}")
async def kb_get(article_id: int, session: AsyncSession = Depends(get_db), auth: AuthorizationContext = Depends(get_authorization_context)):
    from app.db.models import KBArticle
    a = await session.get(KBArticle, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    if auth.role == "requester" and (not a.publicado or a.visibilidade != "external"):
        raise HTTPException(status_code=404, detail="Article not found")
    return {"id": a.id, "titulo": a.titulo, "resumo": a.resumo, "conteudo": a.conteudo, "tags": a.tags, "categoria_id": a.categoria_id}

@router.post("/kb/suggest")
async def kb_suggest(payload: Dict[str, Any], session: AsyncSession = Depends(get_db), auth: AuthorizationContext = Depends(get_authorization_context)):
    from app.db.models import KBArticle
    empresa_id = auth.tenant.empresa_id
    text = (str(payload.get("titulo") or "") + " " + str(payload.get("descricao") or "")).strip().lower()
    res = await session.execute(select(KBArticle).where(KBArticle.empresa_id == empresa_id))
    items = res.scalars().all()
    def score(a):
        s = 0
        t = (a.titulo or "") + " " + (a.resumo or "") + " " + (a.conteudo or "")
        t = t.lower()
        for w in set(text.split()):
            if len(w) < 3: continue
            if w in t:
                s += 1
        return s
    ranked = sorted(items, key=score, reverse=True)
    if auth.role == "requester":
        ranked = [a for a in ranked if a.publicado and a.visibilidade == "external"]
    top = ranked[:5]
    return [{"id": a.id, "titulo": a.titulo, "resumo": a.resumo} for a in top]
