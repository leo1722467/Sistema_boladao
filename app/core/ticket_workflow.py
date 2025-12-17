"""
Ticket workflow and state machine management for Sistema Boladão.
Handles ticket status transitions, SLA tracking, and escalation rules.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TicketError, ValidationError, ConflictError
from app.db.models import Chamado, StatusChamado, Prioridade

logger = logging.getLogger(__name__)


class TicketStatus(str, Enum):
    """Standard ticket statuses with workflow transitions."""
    NEW = "new"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_CUSTOMER = "pending_customer"
    PENDING_VENDOR = "pending_vendor"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketPriority(str, Enum):
    """Standard ticket priorities with SLA definitions."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


@dataclass
class SLAConfiguration:
    """SLA configuration for different priority levels."""
    priority: TicketPriority
    response_time_hours: int
    resolution_time_hours: int
    escalation_time_hours: int


@dataclass
class TicketTransition:
    """Represents a valid ticket status transition."""
    from_status: TicketStatus
    to_status: TicketStatus
    required_role: Optional[str] = None
    requires_comment: bool = False
    auto_assign: bool = False


class TicketWorkflowEngine:
    """Manages ticket workflow, state transitions, and SLA tracking."""
    
    # Define valid status transitions
    VALID_TRANSITIONS: List[TicketTransition] = [
        # From NEW
        TicketTransition(TicketStatus.NEW, TicketStatus.OPEN, required_role="agent"),
        TicketTransition(TicketStatus.NEW, TicketStatus.CANCELLED, required_role="agent"),
        
        # From OPEN
        TicketTransition(TicketStatus.OPEN, TicketStatus.IN_PROGRESS, required_role="agent", auto_assign=True),
        TicketTransition(TicketStatus.OPEN, TicketStatus.PENDING_CUSTOMER, required_role="agent", requires_comment=True),
        TicketTransition(TicketStatus.OPEN, TicketStatus.PENDING_VENDOR, required_role="agent", requires_comment=True),
        TicketTransition(TicketStatus.OPEN, TicketStatus.RESOLVED, required_role="agent", requires_comment=True),
        TicketTransition(TicketStatus.OPEN, TicketStatus.CANCELLED, required_role="agent"),
        
        # From IN_PROGRESS
        TicketTransition(TicketStatus.IN_PROGRESS, TicketStatus.PENDING_CUSTOMER, required_role="agent", requires_comment=True),
        TicketTransition(TicketStatus.IN_PROGRESS, TicketStatus.PENDING_VENDOR, required_role="agent", requires_comment=True),
        TicketTransition(TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, required_role="agent", requires_comment=True),
        TicketTransition(TicketStatus.IN_PROGRESS, TicketStatus.OPEN, required_role="agent"),
        
        # From PENDING_CUSTOMER
        TicketTransition(TicketStatus.PENDING_CUSTOMER, TicketStatus.OPEN),  # Customer can respond
        TicketTransition(TicketStatus.PENDING_CUSTOMER, TicketStatus.IN_PROGRESS, required_role="agent"),
        TicketTransition(TicketStatus.PENDING_CUSTOMER, TicketStatus.CANCELLED, required_role="agent"),
        
        # From PENDING_VENDOR
        TicketTransition(TicketStatus.PENDING_VENDOR, TicketStatus.IN_PROGRESS, required_role="agent"),
        TicketTransition(TicketStatus.PENDING_VENDOR, TicketStatus.OPEN, required_role="agent"),
        
        # From RESOLVED
        TicketTransition(TicketStatus.RESOLVED, TicketStatus.CLOSED, required_role="agent"),
        TicketTransition(TicketStatus.RESOLVED, TicketStatus.OPEN),  # Customer can reopen
        
        # From CLOSED (limited reopening)
        TicketTransition(TicketStatus.CLOSED, TicketStatus.OPEN, required_role="agent"),
    ]
    
    # SLA configurations by priority
    SLA_CONFIGS: Dict[TicketPriority, SLAConfiguration] = {
        TicketPriority.LOW: SLAConfiguration(TicketPriority.LOW, 48, 168, 72),  # 2 days, 1 week, 3 days
        TicketPriority.NORMAL: SLAConfiguration(TicketPriority.NORMAL, 24, 72, 48),  # 1 day, 3 days, 2 days
        TicketPriority.HIGH: SLAConfiguration(TicketPriority.HIGH, 8, 24, 16),  # 8 hours, 1 day, 16 hours
        TicketPriority.URGENT: SLAConfiguration(TicketPriority.URGENT, 4, 12, 8),  # 4 hours, 12 hours, 8 hours
        TicketPriority.CRITICAL: SLAConfiguration(TicketPriority.CRITICAL, 1, 4, 2),  # 1 hour, 4 hours, 2 hours
    }
    
    def __init__(self):
        self._build_transition_map()
    
    def _build_transition_map(self) -> None:
        """Build a lookup map for valid transitions."""
        self.transition_map: Dict[TicketStatus, List[TicketTransition]] = {}
        for transition in self.VALID_TRANSITIONS:
            if transition.from_status not in self.transition_map:
                self.transition_map[transition.from_status] = []
            self.transition_map[transition.from_status].append(transition)
    
    def get_valid_transitions(self, current_status: TicketStatus, user_role: str) -> List[TicketStatus]:
        """Get list of valid status transitions for current status and user role."""
        if current_status not in self.transition_map:
            return []
        
        valid_statuses = []
        for transition in self.transition_map[current_status]:
            # Check if user has required role for this transition
            if transition.required_role and user_role not in ["admin", transition.required_role]:
                continue
            valid_statuses.append(transition.to_status)
        
        return valid_statuses
    
    def validate_transition(
        self, 
        current_status: TicketStatus, 
        new_status: TicketStatus, 
        user_role: str,
        comment: Optional[str] = None
    ) -> TicketTransition:
        """
        Validate if a status transition is allowed.
        
        Args:
            current_status: Current ticket status
            new_status: Desired new status
            user_role: Role of the user making the change
            comment: Optional comment for the transition
            
        Returns:
            TicketTransition object if valid
            
        Raises:
            TicketError: If transition is not valid
        """
        if current_status not in self.transition_map:
            raise TicketError(f"No transitions defined for status '{current_status}'")
        
        # Find the specific transition
        transition = None
        for t in self.transition_map[current_status]:
            if t.to_status == new_status:
                transition = t
                break
        
        if not transition:
            raise ConflictError(
                f"Invalid transition from '{current_status}' to '{new_status}'",
                {"current_status": current_status, "new_status": new_status}
            )
        
        # Check role requirements
        if transition.required_role and user_role not in ["admin", transition.required_role]:
            raise ConflictError(
                f"Insufficient permissions for transition to '{new_status}'. Required role: {transition.required_role}",
                {"required_role": transition.required_role, "user_role": user_role}
            )
        
        # Check comment requirements
        if transition.requires_comment and (not comment or not comment.strip()):
            raise ValidationError(
                f"Comment is required for transition to '{new_status}'",
                {"transition": f"{current_status} -> {new_status}"}
            )
        
        return transition
    
    def calculate_sla_deadlines(
        self, 
        priority: TicketPriority, 
        created_at: datetime
    ) -> Dict[str, datetime]:
        """
        Calculate SLA deadlines for a ticket based on priority and creation time.
        
        Args:
            priority: Ticket priority
            created_at: Ticket creation timestamp
            
        Returns:
            Dictionary with SLA deadline timestamps
        """
        if priority not in self.SLA_CONFIGS:
            priority = TicketPriority.NORMAL  # Default fallback
        
        sla_config = self.SLA_CONFIGS[priority]
        
        return {
            "response_deadline": created_at + timedelta(hours=sla_config.response_time_hours),
            "resolution_deadline": created_at + timedelta(hours=sla_config.resolution_time_hours),
            "escalation_deadline": created_at + timedelta(hours=sla_config.escalation_time_hours),
        }
    
    def check_sla_breaches(
        self, 
        ticket: Chamado, 
        current_time: Optional[datetime] = None
    ) -> Dict[str, bool]:
        """
        Check if a ticket has breached any SLA deadlines.
        
        Args:
            ticket: Ticket to check
            current_time: Current timestamp (defaults to now)
            
        Returns:
            Dictionary indicating which SLAs have been breached
        """
        if not current_time:
            current_time = datetime.utcnow()
        
        # Determine priority from ticket
        priority = TicketPriority.NORMAL  # Default
        if ticket.prioridade and hasattr(ticket.prioridade, 'nome'):
            priority_name = ticket.prioridade.nome.lower()
            for p in TicketPriority:
                if p.value in priority_name:
                    priority = p
                    break
        
        deadlines = self.calculate_sla_deadlines(priority, ticket.criado_em)
        
        # Check if ticket has been responded to (has agent assigned or comments)
        has_response = (
            ticket.agente_contato_id is not None or 
            (hasattr(ticket, 'comentarios') and len(ticket.comentarios) > 0)
        )
        
        # Check if ticket is resolved
        is_resolved = ticket.status and ticket.status.nome.lower() in ['resolved', 'closed']
        
        return {
            "response_breach": not has_response and current_time > deadlines["response_deadline"],
            "resolution_breach": not is_resolved and current_time > deadlines["resolution_deadline"],
            "escalation_needed": current_time > deadlines["escalation_deadline"] and not is_resolved,
        }
    
    def get_escalation_recommendations(
        self, 
        ticket: Chamado, 
        sla_breaches: Dict[str, bool]
    ) -> List[str]:
        """
        Get escalation recommendations based on SLA breaches.
        
        Args:
            ticket: Ticket to analyze
            sla_breaches: SLA breach status
            
        Returns:
            List of escalation recommendations
        """
        recommendations = []
        
        if sla_breaches["response_breach"]:
            recommendations.append("Assign agent immediately - response SLA breached")
        
        if sla_breaches["resolution_breach"]:
            recommendations.append("Escalate to senior agent - resolution SLA breached")
        
        if sla_breaches["escalation_needed"]:
            recommendations.append("Escalate to manager - ticket requires immediate attention")
        
        # Additional business rules
        if ticket.prioridade and "critical" in ticket.prioridade.nome.lower():
            if not ticket.agente_contato_id:
                recommendations.append("Critical ticket requires immediate agent assignment")
        
        return recommendations
    
    def suggest_next_actions(
        self, 
        ticket: Chamado, 
        user_role: str
    ) -> List[Dict[str, str]]:
        """
        Suggest next possible actions for a ticket based on current state and user role.
        
        Args:
            ticket: Current ticket
            user_role: Role of the current user
            
        Returns:
            List of suggested actions with descriptions
        """
        current_status = TicketStatus(ticket.status.nome.lower()) if ticket.status else TicketStatus.NEW
        valid_transitions = self.get_valid_transitions(current_status, user_role)
        
        actions = []
        
        for status in valid_transitions:
            action = {
                "action": f"transition_to_{status.value}",
                "description": f"Change status to {status.value.replace('_', ' ').title()}",
                "status": status.value
            }
            
            # Add specific guidance for certain transitions
            if status == TicketStatus.IN_PROGRESS:
                action["description"] += " (will auto-assign to you)"
            elif status == TicketStatus.RESOLVED:
                action["description"] += " (requires resolution comment)"
            elif status == TicketStatus.PENDING_CUSTOMER:
                action["description"] += " (requires explanation comment)"
            
            actions.append(action)
        
        # Add non-status actions
        if user_role in ["admin", "agent"]:
            if not ticket.agente_contato_id:
                actions.append({
                    "action": "assign_to_self",
                    "description": "Assign ticket to yourself",
                    "status": current_status.value
                })
            
            actions.append({
                "action": "add_comment",
                "description": "Add internal or customer comment",
                "status": current_status.value
            })
        
        return actions
