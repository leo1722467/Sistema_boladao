"""
Role-based authorization system for Sistema Boladão.
Provides decorators and dependencies for controlling access based on user roles.
"""

import logging
from enum import Enum
from typing import List, Optional, Callable, Any
from functools import wraps
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.auth import get_current_user
from app.core.tenant import get_tenant_context, TenantContext
from app.db.models import UserAuth, Contato
from app.core.exceptions import TenantScopeError, ValidationError

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User roles in the system."""
    ADMIN = "admin"
    AGENT = "agent"
    REQUESTER = "requester"
    VIEWER = "viewer"


class Permission(str, Enum):
    """System permissions."""
    # Admin permissions
    MANAGE_COMPANIES = "manage_companies"
    MANAGE_USERS = "manage_users"
    MANAGE_SYSTEM = "manage_system"
    
    # Agent permissions
    MANAGE_TICKETS = "manage_tickets"
    MANAGE_ASSETS = "manage_assets"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_SERVICE_ORDERS = "manage_service_orders"
    
    # Requester permissions
    CREATE_TICKETS = "create_tickets"
    VIEW_OWN_TICKETS = "view_own_tickets"
    UPDATE_OWN_TICKETS = "update_own_tickets"
    
    # Viewer permissions
    VIEW_ASSETS = "view_assets"
    VIEW_TICKETS = "view_tickets"
    VIEW_INVENTORY = "view_inventory"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.MANAGE_COMPANIES,
        Permission.MANAGE_USERS,
        Permission.MANAGE_SYSTEM,
        Permission.MANAGE_TICKETS,
        Permission.MANAGE_ASSETS,
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_SERVICE_ORDERS,
        Permission.CREATE_TICKETS,
        Permission.VIEW_OWN_TICKETS,
        Permission.UPDATE_OWN_TICKETS,
        Permission.VIEW_ASSETS,
        Permission.VIEW_TICKETS,
        Permission.VIEW_INVENTORY,
    ],
    UserRole.AGENT: [
        Permission.MANAGE_TICKETS,
        Permission.MANAGE_ASSETS,
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_SERVICE_ORDERS,
        Permission.CREATE_TICKETS,
        Permission.VIEW_OWN_TICKETS,
        Permission.UPDATE_OWN_TICKETS,
        Permission.VIEW_ASSETS,
        Permission.VIEW_TICKETS,
        Permission.VIEW_INVENTORY,
    ],
    UserRole.REQUESTER: [
        Permission.CREATE_TICKETS,
        Permission.VIEW_OWN_TICKETS,
        Permission.UPDATE_OWN_TICKETS,
        Permission.VIEW_ASSETS,
    ],
    UserRole.VIEWER: [
        Permission.VIEW_ASSETS,
        Permission.VIEW_TICKETS,
        Permission.VIEW_INVENTORY,
    ],
}


class AuthorizationContext:
    """Authorization context containing user and tenant information."""
    
    def __init__(
        self,
        user: UserAuth,
        tenant: TenantContext,
        role: UserRole,
        permissions: List[Permission]
    ):
        self.user = user
        self.tenant = tenant
        self.role = role
        self.permissions = permissions
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if the user has a specific permission."""
        return permission in self.permissions
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if the user has any of the specified permissions."""
        return any(perm in self.permissions for perm in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """Check if the user has all of the specified permissions."""
        return all(perm in self.permissions for perm in permissions)


async def get_user_role(session: AsyncSession, user: UserAuth) -> UserRole:
    """
    Determine user role based on user data and business logic.
    This is a simplified implementation - in production, roles would be stored in the database.
    """
    try:
        # Load the user's contact information
        contato = await session.get(Contato, user.contato_id)
        if not contato:
            logger.warning(f"No contact found for user {user.id}")
            return UserRole.VIEWER
        
        # Simple role determination logic - can be enhanced based on requirements
        # For now, we'll use email patterns or specific logic
        if contato.email and "admin" in contato.email.lower():
            return UserRole.ADMIN
        elif contato.email and ("agent" in contato.email.lower() or "support" in contato.email.lower()):
            return UserRole.AGENT
        else:
            return UserRole.REQUESTER
            
    except Exception as e:
        logger.error(f"Error determining user role for user {user.id}: {e}")
        return UserRole.VIEWER


async def get_authorization_context(
    session: AsyncSession = Depends(get_db),
    user: UserAuth = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AuthorizationContext:
    """Get the complete authorization context for the current user."""
    try:
        role = await get_user_role(session, user)
        permissions = ROLE_PERMISSIONS.get(role, [])
        
        return AuthorizationContext(
            user=user,
            tenant=tenant,
            role=role,
            permissions=permissions
        )
    except Exception as e:
        logger.error(f"Error creating authorization context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to determine user authorization"
        )


def require_permission(permission: Permission):
    """Decorator to require a specific permission for an endpoint."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract auth_context from kwargs
            auth_context = kwargs.get('auth_context')
            if not auth_context or not isinstance(auth_context, AuthorizationContext):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authorization context not found"
                )
            
            if not auth_context.has_permission(permission):
                logger.warning(
                    f"User {auth_context.user.id} with role {auth_context.role} "
                    f"attempted to access endpoint requiring {permission}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(permissions: List[Permission]):
    """Decorator to require any of the specified permissions for an endpoint."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            auth_context = kwargs.get('auth_context')
            if not auth_context or not isinstance(auth_context, AuthorizationContext):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authorization context not found"
                )
            
            if not auth_context.has_any_permission(permissions):
                logger.warning(
                    f"User {auth_context.user.id} with role {auth_context.role} "
                    f"attempted to access endpoint requiring any of {permissions}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required any of: {permissions}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: UserRole):
    """Decorator to require a specific role for an endpoint."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            auth_context = kwargs.get('auth_context')
            if not auth_context or not isinstance(auth_context, AuthorizationContext):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authorization context not found"
                )
            
            if auth_context.role != role:
                logger.warning(
                    f"User {auth_context.user.id} with role {auth_context.role} "
                    f"attempted to access endpoint requiring role {role}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient role. Required: {role}, Current: {auth_context.role}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Convenience dependencies for common role checks
async def require_admin_role(auth_context: AuthorizationContext = Depends(get_authorization_context)):
    """Dependency to require admin role."""
    if auth_context.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    return auth_context


async def require_agent_or_admin_role(auth_context: AuthorizationContext = Depends(get_authorization_context)):
    """Dependency to require agent or admin role."""
    if auth_context.role not in [UserRole.AGENT, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent or Admin role required"
        )
    return auth_context


async def require_any_authenticated_role(auth_context: AuthorizationContext = Depends(get_authorization_context)):
    """Dependency to require any authenticated role (not just viewer)."""
    if auth_context.role == UserRole.VIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user role required"
        )
    return auth_context


class ResourceOwnershipValidator:
    """Utility class for validating resource ownership and access rights."""
    
    @staticmethod
    def validate_ticket_access(
        auth_context: AuthorizationContext,
        ticket_requester_id: Optional[int],
        ticket_agent_id: Optional[int] = None
    ) -> bool:
        """Validate if user can access a specific ticket."""
        # Admins and agents can access all tickets
        if auth_context.role in [UserRole.ADMIN, UserRole.AGENT]:
            return True
        
        # Requesters can only access their own tickets
        if auth_context.role == UserRole.REQUESTER:
            return ticket_requester_id == auth_context.user.contato_id
        
        return False
    
    @staticmethod
    def validate_asset_access(
        auth_context: AuthorizationContext,
        asset_empresa_id: int
    ) -> bool:
        """Validate if user can access a specific asset."""
        # Check tenant scoping
        if asset_empresa_id != auth_context.tenant.empresa_id:
            return False
        
        # Check role permissions
        return auth_context.has_permission(Permission.VIEW_ASSETS)
    
    @staticmethod
    def validate_service_order_access(
        auth_context: AuthorizationContext,
        service_order_empresa_id: int
    ) -> bool:
        """Validate if user can access a specific service order."""
        # Check tenant scoping
        if service_order_empresa_id != auth_context.tenant.empresa_id:
            return False
        
        # Check role permissions
        return auth_context.has_any_permission([
            Permission.MANAGE_SERVICE_ORDERS,
            Permission.VIEW_TICKETS
        ])