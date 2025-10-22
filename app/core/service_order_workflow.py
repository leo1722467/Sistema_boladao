"""
Service Order workflow and management system for Sistema Boladão.
Handles service order status transitions, activity tracking, and time logging.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceOrderError, ValidationError
from app.db.models import OrdemServico, TipoOS

logger = logging.getLogger(__name__)


class ServiceOrderStatus(str, Enum):
    """Standard service order statuses with workflow transitions."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    APPROVED = "approved"
    INVOICED = "invoiced"


class ServiceOrderPriority(str, Enum):
    """Service order priorities."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    EMERGENCY = "emergency"


@dataclass
class ServiceOrderTransition:
    """Represents a valid service order status transition."""
    from_status: ServiceOrderStatus
    to_status: ServiceOrderStatus
    required_role: Optional[str] = None
    requires_comment: bool = False
    requires_approval: bool = False
    auto_timestamp: bool = True


@dataclass
class ActivityEntry:
    """Represents an activity entry in a service order."""
    timestamp: datetime
    user_id: int
    activity_type: str
    description: str
    duration_minutes: Optional[int] = None
    billable: bool = True


class ServiceOrderWorkflowEngine:
    """Manages service order workflow, status transitions, and activity tracking."""
    
    # Define valid status transitions
    VALID_TRANSITIONS: List[ServiceOrderTransition] = [
        # From DRAFT
        ServiceOrderTransition(ServiceOrderStatus.DRAFT, ServiceOrderStatus.SCHEDULED, required_role="agent"),
        ServiceOrderTransition(ServiceOrderStatus.DRAFT, ServiceOrderStatus.CANCELLED, required_role="agent"),
        
        # From SCHEDULED
        ServiceOrderTransition(ServiceOrderStatus.SCHEDULED, ServiceOrderStatus.IN_PROGRESS, required_role="agent", auto_timestamp=True),
        ServiceOrderTransition(ServiceOrderStatus.SCHEDULED, ServiceOrderStatus.ON_HOLD, required_role="agent", requires_comment=True),
        ServiceOrderTransition(ServiceOrderStatus.SCHEDULED, ServiceOrderStatus.CANCELLED, required_role="agent", requires_comment=True),
        
        # From IN_PROGRESS
        ServiceOrderTransition(ServiceOrderStatus.IN_PROGRESS, ServiceOrderStatus.ON_HOLD, required_role="agent", requires_comment=True),
        ServiceOrderTransition(ServiceOrderStatus.IN_PROGRESS, ServiceOrderStatus.COMPLETED, required_role="agent", requires_comment=True, auto_timestamp=True),
        ServiceOrderTransition(ServiceOrderStatus.IN_PROGRESS, ServiceOrderStatus.CANCELLED, required_role="agent", requires_comment=True),
        
        # From ON_HOLD
        ServiceOrderTransition(ServiceOrderStatus.ON_HOLD, ServiceOrderStatus.IN_PROGRESS, required_role="agent"),
        ServiceOrderTransition(ServiceOrderStatus.ON_HOLD, ServiceOrderStatus.SCHEDULED, required_role="agent"),
        ServiceOrderTransition(ServiceOrderStatus.ON_HOLD, ServiceOrderStatus.CANCELLED, required_role="agent", requires_comment=True),
        
        # From COMPLETED
        ServiceOrderTransition(ServiceOrderStatus.COMPLETED, ServiceOrderStatus.APPROVED, required_role="admin", requires_approval=True),
        ServiceOrderTransition(ServiceOrderStatus.COMPLETED, ServiceOrderStatus.IN_PROGRESS, required_role="agent", requires_comment=True),  # Reopen
        
        # From APPROVED
        ServiceOrderTransition(ServiceOrderStatus.APPROVED, ServiceOrderStatus.INVOICED, required_role="admin"),
        ServiceOrderTransition(ServiceOrderStatus.APPROVED, ServiceOrderStatus.COMPLETED, required_role="admin", requires_comment=True),  # Reject
    ]
    
    # Activity types
    ACTIVITY_TYPES = {
        "DIAGNOSTIC": "Diagnostic and troubleshooting",
        "REPAIR": "Repair and maintenance work",
        "INSTALLATION": "Installation and setup",
        "TESTING": "Testing and validation",
        "DOCUMENTATION": "Documentation and reporting",
        "TRAVEL": "Travel time",
        "WAITING": "Waiting for parts/approval",
        "TRAINING": "User training",
        "CONSULTATION": "Technical consultation",
        "OTHER": "Other activities"
    }
    
    def __init__(self):
        self._build_transition_map()
    
    def _build_transition_map(self) -> None:
        """Build a lookup map for valid transitions."""
        self.transition_map: Dict[ServiceOrderStatus, List[ServiceOrderTransition]] = {}
        for transition in self.VALID_TRANSITIONS:
            if transition.from_status not in self.transition_map:
                self.transition_map[transition.from_status] = []
            self.transition_map[transition.from_status].append(transition)
    
    def get_valid_transitions(self, current_status: ServiceOrderStatus, user_role: str) -> List[ServiceOrderStatus]:
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
        current_status: ServiceOrderStatus, 
        new_status: ServiceOrderStatus, 
        user_role: str,
        comment: Optional[str] = None
    ) -> ServiceOrderTransition:
        """
        Validate if a status transition is allowed.
        
        Args:
            current_status: Current service order status
            new_status: Desired new status
            user_role: Role of the user making the change
            comment: Optional comment for the transition
            
        Returns:
            ServiceOrderTransition object if valid
            
        Raises:
            ServiceOrderError: If transition is not valid
        """
        if current_status not in self.transition_map:
            raise ServiceOrderError(f"No transitions defined for status '{current_status}'")
        
        # Find the specific transition
        transition = None
        for t in self.transition_map[current_status]:
            if t.to_status == new_status:
                transition = t
                break
        
        if not transition:
            raise ServiceOrderError(
                f"Invalid transition from '{current_status}' to '{new_status}'",
                {"current_status": current_status, "new_status": new_status}
            )
        
        # Check role requirements
        if transition.required_role and user_role not in ["admin", transition.required_role]:
            raise ServiceOrderError(
                f"Insufficient permissions for transition to '{new_status}'. Required role: {transition.required_role}",
                {"required_role": transition.required_role, "user_role": user_role}
            )
        
        # Check comment requirements
        if transition.requires_comment and (not comment or not comment.strip()):
            raise ServiceOrderError(
                f"Comment is required for transition to '{new_status}'",
                {"transition": f"{current_status} -> {new_status}"}
            )
        
        return transition
    
    def calculate_duration(self, start_time: datetime, end_time: Optional[datetime] = None) -> int:
        """
        Calculate duration in minutes between start and end time.
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp (defaults to now)
            
        Returns:
            Duration in minutes
        """
        if not end_time:
            end_time = datetime.utcnow()
        
        duration = end_time - start_time
        return int(duration.total_seconds() / 60)
    
    def calculate_billable_time(self, activities: List[ActivityEntry]) -> Dict[str, int]:
        """
        Calculate billable and non-billable time from activities.
        
        Args:
            activities: List of activity entries
            
        Returns:
            Dictionary with billable and non-billable minutes
        """
        billable_minutes = 0
        non_billable_minutes = 0
        
        for activity in activities:
            if activity.duration_minutes:
                if activity.billable:
                    billable_minutes += activity.duration_minutes
                else:
                    non_billable_minutes += activity.duration_minutes
        
        return {
            "billable_minutes": billable_minutes,
            "non_billable_minutes": non_billable_minutes,
            "total_minutes": billable_minutes + non_billable_minutes,
            "billable_hours": round(billable_minutes / 60, 2),
            "total_hours": round((billable_minutes + non_billable_minutes) / 60, 2)
        }
    
    def suggest_next_actions(
        self, 
        service_order: OrdemServico, 
        user_role: str
    ) -> List[Dict[str, str]]:
        """
        Suggest next possible actions for a service order based on current state and user role.
        
        Args:
            service_order: Current service order
            user_role: Role of the current user
            
        Returns:
            List of suggested actions with descriptions
        """
        # Determine current status (simplified - in production, would use actual status field)
        current_status = ServiceOrderStatus.DRAFT  # Default
        
        valid_transitions = self.get_valid_transitions(current_status, user_role)
        
        actions = []
        
        for status in valid_transitions:
            action = {
                "action": f"transition_to_{status.value}",
                "description": f"Change status to {status.value.replace('_', ' ').title()}",
                "status": status.value
            }
            
            # Add specific guidance for certain transitions
            if status == ServiceOrderStatus.IN_PROGRESS:
                action["description"] += " (will start time tracking)"
            elif status == ServiceOrderStatus.COMPLETED:
                action["description"] += " (requires completion summary)"
            elif status == ServiceOrderStatus.ON_HOLD:
                action["description"] += " (requires reason comment)"
            
            actions.append(action)
        
        # Add activity-related actions
        if user_role in ["admin", "agent"]:
            actions.extend([
                {
                    "action": "add_activity",
                    "description": "Log work activity with time tracking",
                    "status": current_status.value
                },
                {
                    "action": "update_details",
                    "description": "Update service order details and observations",
                    "status": current_status.value
                }
            ])
        
        return actions
    
    def generate_service_order_number(self, empresa_id: int, year: Optional[int] = None) -> str:
        """
        Generate a service order number with company-specific sequence.
        
        Args:
            empresa_id: Company ID
            year: Year for the sequence (defaults to current year)
            
        Returns:
            Formatted service order number
        """
        if not year:
            year = datetime.utcnow().year
        
        # In production, this would use a database sequence or counter
        # For now, use timestamp-based generation with company prefix
        timestamp = int(datetime.utcnow().timestamp())
        sequence = timestamp % 100000  # Last 5 digits
        
        return f"OS-{empresa_id}-{year}-{sequence:05d}"
    
    def validate_activity_entry(self, activity: Dict[str, any]) -> ActivityEntry:
        """
        Validate and create an activity entry.
        
        Args:
            activity: Activity data dictionary
            
        Returns:
            Validated ActivityEntry object
            
        Raises:
            ValidationError: If activity data is invalid
        """
        required_fields = ["user_id", "activity_type", "description"]
        for field in required_fields:
            if field not in activity or not activity[field]:
                raise ValidationError(f"Activity field '{field}' is required")
        
        # Validate activity type
        if activity["activity_type"] not in self.ACTIVITY_TYPES:
            raise ValidationError(
                f"Invalid activity type '{activity['activity_type']}'. "
                f"Valid types: {', '.join(self.ACTIVITY_TYPES.keys())}"
            )
        
        # Validate duration if provided
        duration = activity.get("duration_minutes")
        if duration is not None:
            if not isinstance(duration, int) or duration < 0:
                raise ValidationError("Duration must be a non-negative integer")
            if duration > 24 * 60:  # More than 24 hours
                raise ValidationError("Duration cannot exceed 24 hours (1440 minutes)")
        
        return ActivityEntry(
            timestamp=activity.get("timestamp", datetime.utcnow()),
            user_id=activity["user_id"],
            activity_type=activity["activity_type"],
            description=activity["description"],
            duration_minutes=duration,
            billable=activity.get("billable", True)
        )
    
    def get_status_summary(self, status: ServiceOrderStatus) -> Dict[str, str]:
        """Get a summary description for a service order status."""
        status_descriptions = {
            ServiceOrderStatus.DRAFT: {
                "title": "Draft",
                "description": "Service order is being prepared and not yet scheduled",
                "color": "gray"
            },
            ServiceOrderStatus.SCHEDULED: {
                "title": "Scheduled", 
                "description": "Service order is scheduled and ready to begin",
                "color": "blue"
            },
            ServiceOrderStatus.IN_PROGRESS: {
                "title": "In Progress",
                "description": "Work is currently being performed",
                "color": "yellow"
            },
            ServiceOrderStatus.ON_HOLD: {
                "title": "On Hold",
                "description": "Work is temporarily paused",
                "color": "orange"
            },
            ServiceOrderStatus.COMPLETED: {
                "title": "Completed",
                "description": "Work has been completed and awaiting approval",
                "color": "green"
            },
            ServiceOrderStatus.CANCELLED: {
                "title": "Cancelled",
                "description": "Service order has been cancelled",
                "color": "red"
            },
            ServiceOrderStatus.APPROVED: {
                "title": "Approved",
                "description": "Completed work has been approved",
                "color": "green"
            },
            ServiceOrderStatus.INVOICED: {
                "title": "Invoiced",
                "description": "Service order has been invoiced",
                "color": "purple"
            }
        }
        
        return status_descriptions.get(status, {
            "title": status.value.title(),
            "description": f"Service order status: {status.value}",
            "color": "gray"
        })