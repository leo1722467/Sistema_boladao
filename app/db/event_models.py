"""
Event models for outbox pattern and domain event publishing.
Provides reliable event publishing with transactional guarantees.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import text
from app.db.base import Base
from datetime import datetime
from enum import Enum


class EventStatus(str, Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    RETRYING = "retrying"


class EventType(str, Enum):
    """Domain event types."""
    # Inventory events
    INVENTORY_ITEM_CREATED = "inventory.item.created"
    INVENTORY_ITEM_UPDATED = "inventory.item.updated"
    INVENTORY_ITEM_DELETED = "inventory.item.deleted"
    
    # Asset events
    ASSET_CREATED = "asset.created"
    ASSET_UPDATED = "asset.updated"
    ASSET_STATUS_CHANGED = "asset.status.changed"
    ASSET_ASSIGNED = "asset.assigned"
    
    # Ticket events
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_STATUS_CHANGED = "ticket.status.changed"
    TICKET_ASSIGNED = "ticket.assigned"
    TICKET_RESOLVED = "ticket.resolved"
    TICKET_CLOSED = "ticket.closed"
    TICKET_SLA_BREACHED = "ticket.sla.breached"
    
    # Service Order events
    SERVICE_ORDER_CREATED = "service_order.created"
    SERVICE_ORDER_UPDATED = "service_order.updated"
    SERVICE_ORDER_STATUS_CHANGED = "service_order.status.changed"
    SERVICE_ORDER_ACTIVITY_ADDED = "service_order.activity.added"
    SERVICE_ORDER_COMPLETED = "service_order.completed"
    
    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_LOGIN = "user.login"
    
    # Company events
    COMPANY_CREATED = "company.created"
    COMPANY_UPDATED = "company.updated"


class OutboxEvent(Base):
    """
    Outbox table for reliable event publishing using the outbox pattern.
    Events are stored transactionally with business operations and published asynchronously.
    """
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, index=True)
    
    # Event identification
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Event data
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    # NOTE: 'metadata' is a reserved attribute in SQLAlchemy Declarative
    # Rename to avoid collision with Base.metadata
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Processing status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=EventStatus.PENDING, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False, index=True
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, index=True)
    
    # Error tracking
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Tenant scoping
    empresa_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)


class WebhookEndpoint(Base):
    """
    Webhook endpoint configuration for external system integrations.
    """
    __tablename__ = "webhook_endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Endpoint configuration
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=True)  # For signature verification
    
    # Event filtering
    event_types: Mapped[list] = mapped_column(JSON, nullable=False)  # List of event types to send
    
    # Configuration
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    # Tenant scoping
    empresa_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class WebhookDelivery(Base):
    """
    Webhook delivery tracking for monitoring and debugging.
    """
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, index=True)
    
    # References
    webhook_endpoint_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Delivery details
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    http_method: Mapped[str] = mapped_column(String(10), nullable=False, default="POST")
    headers: Mapped[dict] = mapped_column(JSON, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Response details
    status_code: Mapped[int] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str] = mapped_column(Text, nullable=True)
    response_headers: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Timing
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Status
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False, index=True
    )


class IntegrationLog(Base):
    """
    General integration activity log for monitoring external system interactions.
    """
    __tablename__ = "integration_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, index=True)
    
    # Integration details
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # whatsapp, ai_gateway, etc.
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Request/Response data
    request_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    response_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Status
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timing
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Context
    user_id: Mapped[int] = mapped_column(Integer, nullable=True)
    empresa_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False, index=True
    )