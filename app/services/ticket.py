from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import time
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

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

    async def _get_next_counter(self, session: AsyncSession, empresa_id: int) -> int:
        from sqlalchemy import select, update, insert
        from app.db.models import TicketCounter, Chamado
        row = await session.execute(select(TicketCounter).where(TicketCounter.empresa_id == empresa_id))
        counter = row.scalars().first()

        # Determine max in new format: E{empresa}{ORIGIN}-{N}
        import re as _re
        pat = _re.compile(rf"^E{empresa_id}[A-Z]+-(\d+)$")
        nums_res = await session.execute(select(Chamado.numero).where(Chamado.empresa_id == empresa_id))
        max_n = 0
        for (num_str,) in nums_res.all():
            if not isinstance(num_str, str):
                continue
            m = pat.match(num_str.strip())
            if not m:
                continue
            try:
                n = int(m.group(1))
                if n > max_n:
                    max_n = n
            except Exception:
                continue

        if not counter:
            next_val = (max_n + 1) if max_n else 1
            await session.execute(insert(TicketCounter).values(empresa_id=empresa_id, next_value=next_val))
            await session.flush()
            await session.execute(update(TicketCounter).where(TicketCounter.empresa_id == empresa_id).values(next_value=next_val + 1))
            return next_val

        # If no new-format tickets exist, reset counter to 1
        if max_n == 0:
            await session.execute(update(TicketCounter).where(TicketCounter.id == counter.id).values(next_value=2))
            return 1

        # Otherwise, ensure we continue from max_n + 1
        next_val = max(counter.next_value or 1, max_n + 1)
        await session.execute(update(TicketCounter).where(TicketCounter.id == counter.id).values(next_value=next_val + 1))
        return next_val

    async def _gen_number(self, session: AsyncSession, empresa_id: int, origin: str) -> str:
        prefix = "WEB" if origin.lower() == "web" else ("WPP" if origin.lower() == "wpp" else origin.upper())
        seq = await self._get_next_counter(session, empresa_id)
        return f"E{empresa_id}{prefix}-{seq}"

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
        origem: str = "web",
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
                ativo = await ativo_repo.get_by_id(session, empresa_id, ativo_id)
                if not ativo or ativo.empresa_id != empresa_id:
                    raise TenantScopeError(
                        "Asset does not belong to the current company",
                        {"ativo_id": ativo_id, "empresa_id": empresa_id}
                    )
            
            # Set default status to 'open' (Aberto) if not provided
            if not status_id:
                new_status = await self._get_default_status(session, "open")
                status_id = new_status.id if new_status else None
            
            # Generate sequential ticket number per origin
            numero = await self._gen_number(session, empresa_id, origem)
            
            # Create the ticket
            attempts = 0
            from sqlalchemy.exc import IntegrityError
            while True:
                try:
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
                        # set origin field for tracking
                        agente_contato_id=None,
                        proprietario_contato_id=None,
                        origem=origem,
                    )
                    break
                except IntegrityError:
                    attempts += 1
                    await session.rollback()
                    if attempts > 5:
                        raise
                    numero = await self._gen_number(session, empresa_id, origem)
            
            await self._log_ticket_action(
                session, ticket.id, solicitante_id,
                "CREATED", f"Ticket created: {titulo}"
            )
            try:
                await self._apply_routing_rules(session, ticket)
            except Exception:
                pass
            
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
            
            # Empresa 1 (atendente) pode visualizar qualquer ticket
            ticket = await (
                self.repo.get_by_id_global(session, ticket_id)
                if empresa_id == 1 else
                self.repo.get_by_id(session, empresa_id, ticket_id)
            )
            
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
                    # Special-case: NEW -> PENDING_CUSTOMER should pass through IN_PROGRESS
                    try:
                        current_status_name = ticket.status.nome.lower() if ticket.status else "new"
                        # Resolve target status name
                        tgt = await session.get(StatusChamado, new_status_id)
                        target_name = tgt.nome.lower() if tgt else ""
                        # Normalize to english labels used by workflow
                        norm = lambda s: {
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
                        }.get((s or "").strip().lower(), (s or "").strip().lower())

                        cur_code = norm(current_status_name)
                        tgt_code = norm(target_name)

                        if cur_code == "new" and tgt_code == "pending_customer":
                            # Business rule: from NEW, move to OPEN first; do NOT jump to PENDING_CUSTOMER
                            open_status = await self._get_default_status(session, "open")
                            if open_status:
                                await self._validate_status_transition(session, ticket, open_status.id, user_role, comment)
                                if ticket.status_id != open_status.id:
                                    changes["status_id"] = {"from": ticket.status_id, "to": open_status.id}
                                    ticket.status_id = open_status.id
                                    await session.flush()
                                    try:
                                        await session.refresh(ticket, ["status"]) 
                                    except Exception:
                                        pass
                            # Do not proceed to pending_customer directly; require further action later
                            pass
                        else:
                            await self._validate_status_transition(
                                session, ticket, new_status_id, user_role, comment
                            )
                            changes["status_id"] = {"from": ticket.status_id, "to": new_status_id}
                            ticket.status_id = new_status_id
                            try:
                                tgt = await session.get(StatusChamado, new_status_id)
                                tgt_name = (tgt.nome or "").strip().lower() if tgt else ""
                                if tgt_name in ["in_progress", "em andamento", "em atendimento"]:
                                    if not ticket.agente_contato_id and user_role in ["admin", "agent"]:
                                        ticket.agente_contato_id = user_id
                                        changes["agente_contato_id"] = {"from": None, "to": user_id}
                            except Exception:
                                pass
                    except Exception:
                        # fall back to single-step validation
                        await self._validate_status_transition(
                            session, ticket, new_status_id, user_role, comment
                        )
                        changes["status_id"] = {"from": ticket.status_id, "to": new_status_id}
                        ticket.status_id = new_status_id
                        try:
                            tgt = await session.get(StatusChamado, new_status_id)
                            tgt_name = (tgt.nome or "").strip().lower() if tgt else ""
                            if tgt_name in ["in_progress", "em andamento", "em atendimento"]:
                                if not ticket.agente_contato_id and user_role in ["admin", "agent"]:
                                    ticket.agente_contato_id = user_id
                                    changes["agente_contato_id"] = {"from": None, "to": user_id}
                        except Exception:
                            pass

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
                # Auto progress status to in_progress when there is activity
                try:
                    current_status_name = ticket.status.nome.lower() if ticket.status else "new"
                    if current_status_name in ["new", "open"]:
                        target = await self._get_default_status(session, "in_progress")
                        if target:
                            await self._validate_status_transition(session, ticket, target.id, user_role, comment)
                            if ticket.status_id != target.id:
                                changes["status_id"] = {"from": ticket.status_id, "to": target.id}
                                ticket.status_id = target.id
                except Exception:
                    pass
            
            # Log the update
            if changes:
                await self._log_ticket_action(
                    session, ticket.id, user_id,
                    "UPDATED", f"Ticket updated: {', '.join(changes.keys())}"
                )
            
            await session.flush()
            logger.info(f"Updated ticket {ticket.numero} by user {user_id}")
            
            return ticket
            
        except (NotFoundError, TicketError, ValidationError, ConflictError):
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
            
            # Build query with filters and eager loading of relations
            query = (
                select(Chamado)
                .options(
                    selectinload(Chamado.status),
                    selectinload(Chamado.prioridade),
                    selectinload(Chamado.categoria),
                    selectinload(Chamado.requisitante),
                    selectinload(Chamado.agente),
                    selectinload(Chamado.comentarios),
                )
            )
            if empresa_id != 1:
                query = query.where(Chamado.empresa_id == empresa_id)
            
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
        norm = lambda s: {
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
        }.get((s or "").strip().lower(), (s or "").strip().lower())

        current_status_name = norm(ticket.status.nome if ticket.status else "new")
        new_status = await session.get(StatusChamado, new_status_id)
        if not new_status:
            raise ValidationError(f"Invalid status ID: {new_status_id}")
        new_status_name = norm(new_status.nome)

        try:
            current_status = TicketStatus(current_status_name)
            new_status_enum = TicketStatus(new_status_name)
        except ValueError as e:
            raise TicketError(f"Invalid status transition: {e}")

        self.workflow.validate_transition(current_status, new_status_enum, user_role, comment)

    async def _get_default_status(self, session: AsyncSession, status_name: str) -> Optional[StatusChamado]:
        """Get a status by name (supports EN/PT)."""
        # Try exact English
        result = await session.execute(select(StatusChamado).where(StatusChamado.nome == status_name))
        status = result.scalars().first()
        if status:
            return status
        # Try exact Portuguese common label
        if status_name.lower() == "open":
            result_pt = await session.execute(select(StatusChamado).where(StatusChamado.nome == "Aberto"))
            status = result_pt.scalars().first()
            if status:
                return status
        if status_name.lower() == "in_progress":
            # Common Portuguese labels: "Em Andamento" or "Em atendimento"
            result_pt2 = await session.execute(select(StatusChamado).where(StatusChamado.nome == "Em Andamento"))
            status = result_pt2.scalars().first()
            if status:
                return status
            result_pt3 = await session.execute(select(StatusChamado).where(StatusChamado.nome == "Em atendimento"))
            status = result_pt3.scalars().first()
            if status:
                return status
        if status_name.lower() == "pending_customer":
            # Common Portuguese labels for waiting: "Aguardando Cliente", "Em espera"
            result_wc1 = await session.execute(select(StatusChamado).where(StatusChamado.nome == "Aguardando Cliente"))
            status = result_wc1.scalars().first()
            if status:
                return status
            result_wc2 = await session.execute(select(StatusChamado).where(StatusChamado.nome == "Em espera"))
            status = result_wc2.scalars().first()
            if status:
                return status
        # Fallback contains
        result2 = await session.execute(select(StatusChamado).where(StatusChamado.nome.ilike(f"%{status_name}%")))
        status = result2.scalars().first()
        if status:
            return status
        if status_name.lower() == "open":
            result2_pt = await session.execute(select(StatusChamado).where(StatusChamado.nome.ilike("%aberto%")))
            return result2_pt.scalars().first()
        if status_name.lower() == "in_progress":
            result2_pt2 = await session.execute(select(StatusChamado).where(StatusChamado.nome.ilike("%andamento%")))
            status = result2_pt2.scalars().first()
            if status:
                return status
            result2_pt3 = await session.execute(select(StatusChamado).where(StatusChamado.nome.ilike("%atendimento%")))
            return result2_pt3.scalars().first()
        if status_name.lower() == "pending_customer":
            result2_wc1 = await session.execute(select(StatusChamado).where(StatusChamado.nome.ilike("%aguardando%")))
            status = result2_wc1.scalars().first()
            if status:
                return status
            result2_wc2 = await session.execute(select(StatusChamado).where(StatusChamado.nome.ilike("%espera%")))
            return result2_wc2.scalars().first()
        return None

    async def _get_default_priority(self, session: AsyncSession, priority_name: str) -> Optional[Prioridade]:
        from sqlalchemy import select
        # Try exact English
        mapping_en_pt = {
            "low": "Baixa",
            "normal": "Normal",
            "high": "Alta",
            "urgent": "Urgente",
        }
        name = priority_name.strip().lower()
        # Exact match by English
        for en, pt in mapping_en_pt.items():
            if name == en:
                result = await session.execute(select(Prioridade).where(Prioridade.nome == pt))
                prow = result.scalars().first()
                if prow:
                    return prow
        # Try exact Portuguese provided
        result_pt = await session.execute(select(Prioridade).where(Prioridade.nome.ilike(f"%{priority_name}%")))
        prow = result_pt.scalars().first()
        if prow:
            return prow
        # Fallback contains common terms
        terms = ["baixa", "normal", "alta", "urgente"]
        for term in terms:
            result = await session.execute(select(Prioridade).where(Prioridade.nome.ilike(f"%{term}%")))
            prow = result.scalars().first()
            if prow:
                return prow
        return None

    async def _apply_routing_rules(self, session: AsyncSession, ticket: Chamado) -> None:
        from sqlalchemy import select
        from app.db.models import HelpdeskRoutingRule
        empresa_id = getattr(ticket, "empresa_id", None) or 1
        agent_id = None
        if ticket.categoria_id:
            res = await session.execute(
                select(HelpdeskRoutingRule).where(
                    HelpdeskRoutingRule.empresa_id == empresa_id,
                    HelpdeskRoutingRule.categoria_id == ticket.categoria_id,
                    HelpdeskRoutingRule.ativo == True,
                )
            )
            row = res.scalars().first()
            agent_id = row.agente_contato_id if row else None
        if not agent_id and ticket.prioridade_id:
            res2 = await session.execute(
                select(HelpdeskRoutingRule).where(
                    HelpdeskRoutingRule.empresa_id == empresa_id,
                    HelpdeskRoutingRule.prioridade_id == ticket.prioridade_id,
                    HelpdeskRoutingRule.ativo == True,
                )
            )
            row2 = res2.scalars().first()
            agent_id = row2.agente_contato_id if row2 else None
        if not agent_id:
            res3 = await session.execute(
                select(HelpdeskRoutingRule).where(
                    HelpdeskRoutingRule.empresa_id == empresa_id,
                    HelpdeskRoutingRule.categoria_id.is_(None),
                    HelpdeskRoutingRule.prioridade_id.is_(None),
                    HelpdeskRoutingRule.ativo == True,
                )
            )
            row3 = res3.scalars().first()
            agent_id = row3.agente_contato_id if row3 else None
        if agent_id:
            old = ticket.agente_contato_id
            ticket.agente_contato_id = int(agent_id)
            if old != ticket.agente_contato_id:
                await self._log_ticket_action(session, ticket.id, None, "ROUTED", "Ticket routed to agent")

    async def apply_macro(
        self,
        session: AsyncSession,
        empresa_id: int,
        ticket_id: int,
        macro_id: int,
        user_id: int,
        user_role: str,
    ) -> Chamado:
        from sqlalchemy import select
        from app.db.models import HelpdeskMacro, StatusChamado, ChamadoCategoria, Prioridade
        ticket = await self.get_by_id(session, empresa_id, ticket_id)
        if not ticket:
            raise NotFoundError("Ticket not found", {"ticket_id": ticket_id})
        res = await session.execute(select(HelpdeskMacro).where(HelpdeskMacro.id == macro_id, HelpdeskMacro.empresa_id == empresa_id))
        macro = res.scalars().first()
        if not macro:
            raise NotFoundError("Macro not found", {"macro_id": macro_id})
        actions = macro.actions or {}
        if isinstance(actions, list):
            seq = actions
        else:
            seq = []
            for k, v in actions.items():
                seq.append({"type": k, "value": v})
        for act in seq:
            t = str(act.get("type") or "").strip().lower()
            v = act.get("value")
            if t == "set_status":
                new_id = None
                if isinstance(v, int):
                    new_id = v
                elif isinstance(v, str) and v.strip():
                    row = await self._get_default_status(session, v)
                    new_id = row.id if row else None
                if new_id:
                    await self._validate_status_transition(session, ticket, new_id, user_role, None)
                    ticket.status_id = new_id
                    try:
                        tgt = await session.get(StatusChamado, new_id)
                        tgt_name = (tgt.nome or "").strip().lower() if tgt else ""
                        if tgt_name in ["in_progress", "em andamento", "em atendimento"] and not ticket.agente_contato_id and user_role in ["admin", "agent"]:
                            ticket.agente_contato_id = user_id
                    except Exception:
                        pass
            elif t == "add_comment":
                if isinstance(v, str) and v.strip():
                    await self._add_comment(session, ticket.id, user_id, v.strip())
            elif t == "assign_agent":
                if isinstance(v, int):
                    ticket.agente_contato_id = v
            elif t == "set_priority":
                if isinstance(v, int):
                    ticket.prioridade_id = v
                elif isinstance(v, str) and v.strip():
                    prow = await self._get_default_priority(session, v)
                    ticket.prioridade_id = prow.id if prow else ticket.prioridade_id
            elif t == "set_category":
                if isinstance(v, int):
                    ticket.categoria_id = v
            await self._log_ticket_action(session, ticket.id, user_id, "MACRO", t)
        ticket.atualizado_em = datetime.utcnow()
        await session.flush()
        return ticket

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
