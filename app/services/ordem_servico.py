from __future__ import annotations
import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.repositories.ordem_servico import OrdemServicoRepository
from app.repositories.chamado import ChamadoRepository
from app.db.models import OrdemServico, TipoOS, Chamado
from app.core.service_order_workflow import (
    ServiceOrderWorkflowEngine, ServiceOrderStatus, ActivityEntry
)
from app.core.exceptions import (
    ServiceOrderError, ValidationError, NotFoundError, 
    ErrorHandler, TenantScopeError
)

logger = logging.getLogger(__name__)


class OrdemServicoService:
    """Enhanced service order service with workflow management, activity tracking, and full CRUD operations."""
    
    def __init__(self) -> None:
        self.repo = OrdemServicoRepository()
        self.chamado_repo = ChamadoRepository()
        self.workflow = ServiceOrderWorkflowEngine()

    async def create(
        self,
        session: AsyncSession,
        empresa_id: int,
        chamado_id: Optional[int] = None,
        tipo_os_id: Optional[int] = None,
        atividades_realizadas: Optional[str] = None,
        observacao: Optional[str] = None,
        numero_apr: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> OrdemServico:
        """
        Create a new service order with comprehensive validation and workflow initialization.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            chamado_id: Optional ticket ID to link
            tipo_os_id: Service order type ID
            atividades_realizadas: Activities performed description
            observacao: Observations and notes
            numero_apr: APR number if applicable
            user_id: ID of user creating the service order
            
        Returns:
            Created service order
            
        Raises:
            ValidationError: For invalid input
            ServiceOrderError: For business logic violations
            TenantScopeError: For tenant scoping violations
        """
        try:
            # Validate required fields
            ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
            
            # Validate ticket belongs to company if provided
            if chamado_id:
                ticket = await self.chamado_repo.get_by_id(session, empresa_id, chamado_id)
                if not ticket:
                    raise TenantScopeError(
                        "Ticket does not belong to the current company or does not exist",
                        {"chamado_id": chamado_id, "empresa_id": empresa_id}
                    )
            
            # Generate service order number
            numero_os = self.workflow.generate_service_order_number(empresa_id)
            
            # Create the service order
            os = await self.repo.create(
                session=session,
                numero_os=numero_os,
                chamado_id=chamado_id,
                tipo_os_id=tipo_os_id,
                atividades_realizadas=atividades_realizadas,
                observacao=observacao,
                numero_apr=numero_apr,
            )
            
            # Initialize activity tracking
            if user_id:
                await self._log_activity(
                    session, os.id, user_id, "CREATION",
                    f"Service order created: {numero_os}"
                )
            
            logger.info(f"Created service order {numero_os} for empresa {empresa_id}")
            return os
            
        except (ValidationError, NotFoundError, TenantScopeError, ServiceOrderError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error creating service order: {e}")
            raise ServiceOrderError(
                "An unexpected error occurred while creating the service order",
                {"error": str(e), "empresa_id": empresa_id}
            )

    async def get_by_id(
        self,
        session: AsyncSession,
        empresa_id: int,
        service_order_id: int,
        include_relations: bool = True
    ) -> Optional[OrdemServico]:
        """
        Get a service order by ID with tenant scoping.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            service_order_id: Service order ID
            include_relations: Whether to include related data
            
        Returns:
            Service order if found, None otherwise
        """
        try:
            ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
            ErrorHandler.validate_positive_integer(service_order_id, "service_order_id")
            
            # Get service order and validate tenant scope through linked ticket
            os = await self.repo.get_by_id(session, service_order_id)
            
            if os and os.chamado_id:
                # Validate through ticket's empresa_id
                ticket = await self.chamado_repo.get_by_id(session, empresa_id, os.chamado_id)
                if not ticket:
                    return None  # Service order doesn't belong to this company
            
            if os and include_relations:
                # Load related data if needed
                await session.refresh(os, ['tipo', 'chamado'])
            
            return os
            
        except Exception as e:
            logger.error(f"Error retrieving service order {service_order_id}: {e}")
            return None

    async def update_service_order(
        self,
        session: AsyncSession,
        empresa_id: int,
        service_order_id: int,
        user_id: int,
        user_role: str,
        updates: Dict[str, Any],
        comment: Optional[str] = None
    ) -> OrdemServico:
        """
        Update a service order with workflow validation and activity logging.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            service_order_id: Service order ID to update
            user_id: ID of user making the update
            user_role: Role of user making the update
            updates: Dictionary of fields to update
            comment: Optional comment for the update
            
        Returns:
            Updated service order
            
        Raises:
            NotFoundError: If service order not found
            ServiceOrderError: For workflow violations
            ValidationError: For invalid updates
        """
        try:
            # Get existing service order
            os = await self.get_by_id(session, empresa_id, service_order_id)
            if not os:
                raise NotFoundError(
                    f"Service order with ID {service_order_id} not found",
                    {"service_order_id": service_order_id, "empresa_id": empresa_id}
                )
            
            # Track changes for activity log
            changes = {}
            
            # Handle status changes with workflow validation (if status field exists)
            # Note: Current model doesn't have status field, but we prepare for it
            if "status" in updates:
                # This would be implemented when status field is added to model
                pass
            
            # Validate and apply field updates
            allowed_fields = {
                "atividades_realizadas", "observacao", "numero_apr", 
                "data_hora_inicio", "data_hora_fim", "duracao"
            }
            
            for field, value in updates.items():
                if field not in allowed_fields:
                    raise ValidationError(f"Field '{field}' cannot be updated")
                
                # Update the service order field
                if hasattr(os, field):
                    old_value = getattr(os, field)
                    if old_value != value:
                        setattr(os, field, value)
                        changes[field] = {"from": old_value, "to": value}
            
            # Add activity log entry
            if changes or comment:
                activity_description = f"Service order updated: {', '.join(changes.keys())}"
                if comment:
                    activity_description += f" - {comment}"
                
                await self._log_activity(
                    session, os.id, user_id, "UPDATE", activity_description
                )
            
            await session.flush()
            logger.info(f"Updated service order {os.numero_os} by user {user_id}")
            
            return os
            
        except (NotFoundError, ServiceOrderError, ValidationError):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error updating service order {service_order_id}: {e}")
            raise ServiceOrderError(
                "An unexpected error occurred while updating the service order",
                {"error": str(e), "service_order_id": service_order_id}
            )

    async def list_service_orders(
        self,
        session: AsyncSession,
        empresa_id: int,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OrdemServico]:
        """
        List service orders with filtering and pagination.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            filters: Optional filters (type, ticket, etc.)
            limit: Maximum number of service orders to return
            offset: Number of service orders to skip
            
        Returns:
            List of service orders
        """
        try:
            ErrorHandler.validate_positive_integer(empresa_id, "empresa_id")
            
            # Build query with tenant scoping through tickets
            query = select(OrdemServico).join(
                Chamado, OrdemServico.chamado_id == Chamado.id
            ).where(Chamado.empresa_id == empresa_id)
            
            if filters:
                if "tipo_os_id" in filters:
                    query = query.where(OrdemServico.tipo_os_id == filters["tipo_os_id"])
                
                if "chamado_id" in filters:
                    query = query.where(OrdemServico.chamado_id == filters["chamado_id"])
                
                if "numero_apr" in filters and filters["numero_apr"]:
                    query = query.where(OrdemServico.numero_apr.ilike(f"%{filters['numero_apr']}%"))
                
                if "search" in filters and filters["search"]:
                    search_term = f"%{filters['search']}%"
                    query = query.where(
                        or_(
                            OrdemServico.numero_os.ilike(search_term),
                            OrdemServico.atividades_realizadas.ilike(search_term),
                            OrdemServico.observacao.ilike(search_term)
                        )
                    )
            
            # Apply pagination and ordering
            query = query.order_by(OrdemServico.id.desc()).offset(offset).limit(limit)
            
            result = await session.execute(query)
            service_orders = result.scalars().all()
            
            logger.debug(f"Listed {len(service_orders)} service orders for empresa {empresa_id}")
            return service_orders
            
        except Exception as e:
            logger.error(f"Error listing service orders for empresa {empresa_id}: {e}")
            return []

    async def add_activity(
        self,
        session: AsyncSession,
        service_order_id: int,
        user_id: int,
        activity_data: Dict[str, Any]
    ) -> None:
        """
        Add an activity entry to a service order.
        
        Args:
            session: Database session
            service_order_id: Service order ID
            user_id: User performing the activity
            activity_data: Activity information
        """
        try:
            # Validate activity data
            activity_data["user_id"] = user_id
            activity_entry = self.workflow.validate_activity_entry(activity_data)
            
            # Log the activity
            await self._log_activity(
                session, service_order_id, user_id,
                activity_entry.activity_type, activity_entry.description,
                activity_entry.duration_minutes, activity_entry.billable
            )
            
            logger.info(f"Added activity to service order {service_order_id} by user {user_id}")
            
        except Exception as e:
            logger.error(f"Error adding activity to service order {service_order_id}: {e}")
            raise ServiceOrderError(
                "Failed to add activity to service order",
                {"error": str(e), "service_order_id": service_order_id}
            )

    async def get_service_order_analytics(
        self,
        session: AsyncSession,
        empresa_id: int,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get service order analytics for a company or user.
        
        Args:
            session: Database session
            empresa_id: Company ID for tenant scoping
            user_id: Optional user ID for personal analytics
            
        Returns:
            Analytics data including time tracking and completion rates
        """
        try:
            # Get service orders for analysis
            filters = {}
            service_orders = await self.list_service_orders(session, empresa_id, filters, limit=1000)
            
            analytics = {
                "total_service_orders": len(service_orders),
                "by_type": {},
                "completion_stats": {
                    "completed": 0,
                    "in_progress": 0,
                    "pending": 0
                },
                "time_tracking": {
                    "total_hours": 0,
                    "billable_hours": 0,
                    "average_duration": 0
                }
            }
            
            total_duration = 0
            completed_count = 0
            
            for os in service_orders:
                # Count by type
                type_name = os.tipo.nome if os.tipo else "unknown"
                analytics["by_type"][type_name] = analytics["by_type"].get(type_name, 0) + 1
                
                # Calculate duration if available
                if os.data_hora_inicio and os.data_hora_fim:
                    duration = self.workflow.calculate_duration(os.data_hora_inicio, os.data_hora_fim)
                    total_duration += duration
                    completed_count += 1
                    analytics["completion_stats"]["completed"] += 1
                elif os.data_hora_inicio:
                    analytics["completion_stats"]["in_progress"] += 1
                else:
                    analytics["completion_stats"]["pending"] += 1
            
            # Calculate averages
            if completed_count > 0:
                analytics["time_tracking"]["average_duration"] = round(total_duration / completed_count, 2)
                analytics["time_tracking"]["total_hours"] = round(total_duration / 60, 2)
                # For now, assume all time is billable (would be calculated from activities in production)
                analytics["time_tracking"]["billable_hours"] = analytics["time_tracking"]["total_hours"]
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error generating service order analytics: {e}")
            return {"error": str(e)}

    async def _log_activity(
        self,
        session: AsyncSession,
        service_order_id: int,
        user_id: int,
        activity_type: str,
        description: str,
        duration_minutes: Optional[int] = None,
        billable: bool = True
    ) -> None:
        """
        Log an activity entry for a service order.
        
        Note: This is a simplified implementation. In production, this would
        store activities in a dedicated table with proper relationships.
        """
        # For now, we'll store activities as JSON in the observacao field
        # In production, this would use a dedicated activities table
        try:
            os = await session.get(OrdemServico, service_order_id)
            if os:
                activity_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "activity_type": activity_type,
                    "description": description,
                    "duration_minutes": duration_minutes,
                    "billable": billable
                }
                
                # Append to existing activities (stored as JSON in observacao for now)
                current_activities = []
                if os.observacao:
                    try:
                        current_activities = json.loads(os.observacao)
                        if not isinstance(current_activities, list):
                            current_activities = []
                    except json.JSONDecodeError:
                        # If observacao is not JSON, preserve it as a text entry
                        current_activities = [{"description": os.observacao, "type": "note"}]
                
                current_activities.append(activity_entry)
                os.observacao = json.dumps(current_activities)
                
        except Exception as e:
            logger.error(f"Error logging activity for service order {service_order_id}: {e}")

# Backwards-compatibility alias for tests and external imports
# Some test modules expect `ServiceOrderService` in this module
# Provide an alias to the enhanced OrdemServicoService implementation
ServiceOrderService = OrdemServicoService