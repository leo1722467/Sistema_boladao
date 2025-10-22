from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import time
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.repositories.chamado import ChamadoRepository
from app.db.models import Chamado, StatusChamado, Prioridade, ChamadoComentario, ChamadoLog
from app.core.ticket_workflow import TicketWorkflowEngine, TicketStatus, TicketPriority
from app.core.exceptions import (
    TicketError, ValidationError, NotFoundError, 
    ErrorHandler, TenantScopeError
)

logger = logging.getLogger(__name__)


class TicketService:
    """Enhanced ticket service with workflow management, SLA tracking, and full CRUD operations."""
    
    def __init__(self) -> None:
        self.repo = ChamadoRepository()
        self.workflow = TicketWorkflowEngine()

    def _gen_number(self, empresa_id: int) -> str:
        """Generate a unique ticket number."""
        timestamp = int(time.time())
        random_part = random.randint(1000, 9999)
        return f"TKT-{empresa_id}-{timestamp}-{random_part}"

    async def create_with_asset(
        self,
        session: AsyncSession,
        empresa_id: int,
        solicitante_id: Optional[int] = None,
        ativo_id: Optional[int] = None,
        titulo: Optional[str] = None,
        descricao: Optional[str] = None,
        prioridade_id: Optional[int] = None,
        status_id: Optional[int] = None,
        categoria_id: Optional[int] = None,
    ) -> Chamado:
        """
        Create a new ticket with comprehensive validation and workflow initialization.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            solicitante_id: Requester contact ID
            ativo_id: Optional asset ID to link
            titulo: Ticket title (required)
            descricao: Ticket description
            prioridade_id: Priority ID
            status_id: Status ID (defaults to 'new')
            categoria_id: Category ID
            
        Returns:
            Created ticket
            
        Raises:
            ValidationError: For invalid input
            TicketError: For business logic violations
        """
        try:
            # Validate required fields
            ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
            if not titulo or not titulo.strip():
                raise ValidationError("Ticket title is required")
            
            # Validate asset belongs to company if provided
            if ativo_id:
                from app.repositories.ativo import AtivoRepository
                ativo_repo = AtivoRepository()
                ativo = await ativo_repo.get_by_id(session, ativo_id)
                if not ativo or ativo.empresa_id != empresa_id:
                    raise TenantScopeError(
                        "Asset does not belong to the current company",
                        {"ativo_id": ativo_id, "empresa_id": empresa_id}
                    )
            
            # Set default status to 'new' if not provided
            if not status_id:
                new_status = await self._get_default_status(session, "new")
                status_id = new_status.id if new_status else None
            
            # Generate unique ticket number
            numero = self._gen_number(empresa_id)
            
            # Create the ticket
            ticket = await self.repo.create(
                session=session,
                empresa_id=empresa_id,
                numero=numero,
                ativo_id=ativo_id,
                titulo=titulo.strip(),
                descricao=descricao,
                categoria_id=categoria_id,
                prioridade_id=prioridade_id,
                status_id=status_id,
                requisitante_contato_id=solicitante_id,
            )
            
            # Log ticket creation
            await self._log_ticket_action(
                session, ticket.id, solicitante_id, 
                "CREATED", f"Ticket created: {titulo}"
            )
            
            logger.info(f"Created ticket {ticket.numero} for empresa {empresa_id}")
            return ticket
            
        except (ValidationError, NotFoundError, TenantScopeError, TicketError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error creating ticket: {e}")
            raise TicketError(
                "An unexpected error occurred while creating the ticket",
                {"error": str(e), "empresa_id": empresa_id}
            )

    async def get_by_id(
        self,
        session: AsyncSession,
        empresa_id: int,
        ticket_id: int,
        include_relations: bool = True
    ) -> Optional[Chamado]:
        """
        Get a ticket by ID with tenant scoping.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            ticket_id: Ticket ID
            include_relations: Whether to include related data
            
        Returns:
            Ticket if found, None otherwise
        """
        try:
            ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
            ErrorHandler.validate_positive_integer(ticket_id, "ticket_id")
            
            ticket = await self.repo.get_by_id(session, empresa_id, ticket_id)
            
            if ticket and include_relations:
                # Load related data if needed
                await session.refresh(ticket, ['status', 'prioridade', 'categoria', 'ativo'])
            
            return ticket
            
        except Exception as e:
            logger.error(f"Error retrieving ticket {ticket_id}: {e}")
            return None

    async def update_ticket(
        self,
        session: AsyncSession,
        empresa_id: int,
        ticket_id: int,
        user_id: int,
        user_role: str,
        updates: Dict[str, Any],
        comment: Optional[str] = None
    ) -> Chamado:
        """
        Update a ticket with workflow validation and audit logging.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            ticket_id: Ticket ID to update
            user_id: ID of user making the update
            user_role: Role of user making the update
            updates: Dictionary of fields to update
            comment: Optional comment for the update
            
        Returns:
            Updated ticket
            
        Raises:
            NotFoundError: If ticket not found
            TicketError: For workflow violations
            ValidationError: For invalid updates
        """
        try:
            # Get existing ticket
            ticket = await self.get_by_id(session, empresa_id, ticket_id)
            if not ticket:
                raise NotFoundError(
                    f"Ticket with ID {ticket_id} not found",
                    {"ticket_id": ticket_id, "empresa_id": empresa_id}
                )
            
            # Track changes for audit log
            changes = {}
            
            # Handle status changes with workflow validation
            if "status_id" in updates:
                new_status_id = updates["status_id"]
                if new_status_id != ticket.status_id:
                    await self._validate_status_transition(
                        session, ticket, new_status_id, user_role, comment
                    )
                    changes["status_id"] = {"from": ticket.status_id, "to": new_status_id}
            
            # Handle assignment changes
            if "agente_contato_id" in updates:
                new_agent_id = updates["agente_contato_id"]
                if new_agent_id != ticket.agente_contato_id:
                    changes["agente_contato_id"] = {"from": ticket.agente_contato_id, "to": new_agent_id}
            
            # Validate other field updates
            allowed_fields = {
                "titulo", "descricao", "prioridade_id", "categoria_id", 
                "agente_contato_id", "proprietario_contato_id", "status_id"
            }
            
            for field, value in updates.items():
                if field not in allowed_fields:
                    raise ValidationError(f"Field '{field}' cannot be updated")
                
                # Update the ticket field
                if hasattr(ticket, field):
                    old_value = getattr(ticket, field)
                    if old_value != value:
                        setattr(ticket, field, value)
                        if field not in changes:
                            changes[field] = {"from": old_value, "to": value}
            
            # Update timestamp
            ticket.atualizado_em = datetime.utcnow()
            
            # Add comment if provided
            if comment and comment.strip():
                await self._add_comment(session, ticket.id, user_id, comment.strip())
            
            # Log the update
            if changes:
                await self._log_ticket_action(
                    session, ticket.id, user_id,
                    "UPDATED", f"Ticket updated: {', '.join(changes.keys())}"
                )
            
            await session.flush()
            logger.info(f"Updated ticket {ticket.numero} by user {user_id}")
            
            return ticket
            
        except (NotFoundError, TicketError, ValidationError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error updating ticket {ticket_id}: {e}")
            raise TicketError(
                "An unexpected error occurred while updating the ticket",
                {"error": str(e), "ticket_id": ticket_id}
            )

    async def list_tickets(
        self,
        session: AsyncSession,
        empresa_id: int,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Chamado]:
        """
        List tickets with filtering and pagination.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            filters: Optional filters (status, priority, assigned_to, etc.)
            limit: Maximum number of tickets to return
            offset: Number of tickets to skip
            
        Returns:
            List of tickets
        """
        try:
            ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
            
            # Build query with filters
            query = select(Chamado).where(Chamado.empresa_id == empresa_id)
            
            if filters:
                if "status_id" in filters:
                    query = query.where(Chamado.status_id == filters["status_id"])
                
                if "prioridade_id" in filters:
                    query = query.where(Chamado.prioridade_id == filters["prioridade_id"])
                
                if "agente_contato_id" in filters:
                    query = query.where(Chamado.agente_contato_id == filters["agente_contato_id"])
                
                if "requisitante_contato_id" in filters:
                    query = query.where(Chamado.requisitante_contato_id == filters["requisitante_contato_id"])
                
                if "ativo_id" in filters:
                    query = query.where(Chamado.ativo_id == filters["ativo_id"])
                
                if "search" in filters and filters["search"]:
                    search_term = f"%{filters['search']}%"
                    query = query.where(
                        or_(
                            Chamado.titulo.ilike(search_term),
                            Chamado.descricao.ilike(search_term),
                            Chamado.numero.ilike(search_term)
                        )
                    )
            
            # Apply pagination and ordering
            query = query.order_by(Chamado.criado_em.desc()).offset(offset).limit(limit)
            
            result = await session.execute(query)
            tickets = result.scalars().all()
            
            logger.debug(f"Listed {len(tickets)} tickets for empresa {empresa_id}")
            return tickets
            
        except Exception as e:
            logger.error(f"Error listing tickets for empresa {empresa_id}: {e}")
            return []

    async def get_ticket_analytics(
        self,
        session: AsyncSession,
        empresa_id: int,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get ticket analytics and SLA status for a company or user.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            user_id: Optional user ID for personal analytics
            
        Returns:
            Analytics data including SLA breaches and recommendations
        """
        try:
            # Get tickets for analysis
            filters = {"agente_contato_id": user_id} if user_id else {}
            tickets = await self.list_tickets(session, empresa_id, filters, limit=1000)
            
            analytics = {
                "total_tickets": len(tickets),
                "by_status": {},
                "by_priority": {},
                "sla_breaches": {
                    "response_breaches": 0,
                    "resolution_breaches": 0,
                    "escalation_needed": 0
                },
                "escalation_recommendations": []
            }
            
            current_time = datetime.utcnow()
            
            for ticket in tickets:
                # Count by status
                status_name = ticket.status.nome if ticket.status else "unknown"
                analytics["by_status"][status_name] = analytics["by_status"].get(status_name, 0) + 1
                
                # Count by priority
                priority_name = ticket.prioridade.nome if ticket.prioridade else "normal"
                analytics["by_priority"][priority_name] = analytics["by_priority"].get(priority_name, 0) + 1
                
                # Check SLA breaches
                sla_breaches = self.workflow.check_sla_breaches(ticket, current_time)
                
                if sla_breaches["response_breach"]:
                    analytics["sla_breaches"]["response_breaches"] += 1
                
                if sla_breaches["resolution_breach"]:
                    analytics["sla_breaches"]["resolution_breaches"] += 1
                
                if sla_breaches["escalation_needed"]:
                    analytics["sla_breaches"]["escalation_needed"] += 1
                    
                    # Get escalation recommendations
                    recommendations = self.workflow.get_escalation_recommendations(ticket, sla_breaches)
                    for rec in recommendations:
                        analytics["escalation_recommendations"].append({
                            "ticket_id": ticket.id,
                            "ticket_number": ticket.numero,
                            "recommendation": rec
                        })
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error generating ticket analytics: {e}")
            return {"error": str(e)}

    async def _validate_status_transition(
        self,
        session: AsyncSession,
        ticket: Chamado,
        new_status_id: int,
        user_role: str,
        comment: Optional[str] = None
    ) -> None:
        """Validate a status transition using the workflow engine."""
        # Get current and new status names
        current_status_name = ticket.status.nome.lower() if ticket.status else "new"
        
        new_status = await session.get(StatusChamado, new_status_id)
        if not new_status:
            raise ValidationError(f"Invalid status ID: {new_status_id}")
        
        new_status_name = new_status.nome.lower()
        
        # Convert to workflow enum values
        try:
            current_status = TicketStatus(current_status_name)
            new_status_enum = TicketStatus(new_status_name)
        except ValueError as e:
            raise TicketError(f"Invalid status transition: {e}")
        
        # Validate transition
        self.workflow.validate_transition(current_status, new_status_enum, user_role, comment)

    async def _get_default_status(self, session: AsyncSession, status_name: str) -> Optional[StatusChamado]:
        """Get a status by name."""
        stmt = select(StatusChamado).where(StatusChamado.nome.ilike(f"%{status_name}%"))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _add_comment(
        self,
        session: AsyncSession,
        ticket_id: int,
        user_id: int,
        comment: str
    ) -> None:
        """Add a comment to a ticket."""
        comment_obj = ChamadoComentario(
            chamado_id=ticket_id,
            contato_id=user_id,
            comentario=comment,
            data_hora=datetime.utcnow()
        )
        session.add(comment_obj)

    async def _log_ticket_action(
        self,
        session: AsyncSession,
        ticket_id: int,
        user_id: Optional[int],
        action: str,
        details: str
    ) -> None:
        """Log a ticket action for audit purposes."""
        log_entry = ChamadoLog(
            chamado_id=ticket_id,
            contato_id=user_id,
            id_alteracao=action,
            data_hora=datetime.utcnow()
        )
        session.add(log_entry)