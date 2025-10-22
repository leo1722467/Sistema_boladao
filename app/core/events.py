"""
Event dispatcher system for reliable domain event publishing and cross-service communication.
Implements the outbox pattern for transactional event publishing.
"""

import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.db.event_models import OutboxEvent, EventStatus, EventType
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class DomainEvent:
    """Base domain event structure."""
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    empresa_id: Optional[int] = None
    occurred_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = datetime.utcnow()
        if not self.event_id:
            self.event_id = str(uuid.uuid4())


@dataclass
class InventoryItemCreatedEvent(DomainEvent):
    """Event fired when an inventory item is created."""
    
    def __init__(self, item_id: int, empresa_id: int, catalog_id: int, quantity: int, **kwargs):
        super().__init__(
            event_id=str(uuid.uuid4()),
            event_type=EventType.INVENTORY_ITEM_CREATED,
            aggregate_type="inventory_item",
            aggregate_id=str(item_id),
            payload={
                "item_id": item_id,
                "catalog_id": catalog_id,
                "quantity": quantity,
                **kwargs
            },
            empresa_id=empresa_id
        )


@dataclass
class AssetCreatedEvent(DomainEvent):
    """Event fired when an asset is created."""
    
    def __init__(self, asset_id: int, empresa_id: int, serial_text: str, **kwargs):
        super().__init__(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ASSET_CREATED,
            aggregate_type="asset",
            aggregate_id=str(asset_id),
            payload={
                "asset_id": asset_id,
                "serial_text": serial_text,
                **kwargs
            },
            empresa_id=empresa_id
        )


@dataclass
class TicketCreatedEvent(DomainEvent):
    """Event fired when a ticket is created."""
    
    def __init__(self, ticket_id: int, empresa_id: int, numero: str, titulo: str, **kwargs):
        super().__init__(
            event_id=str(uuid.uuid4()),
            event_type=EventType.TICKET_CREATED,
            aggregate_type="ticket",
            aggregate_id=str(ticket_id),
            payload={
                "ticket_id": ticket_id,
                "numero": numero,
                "titulo": titulo,
                **kwargs
            },
            empresa_id=empresa_id
        )


@dataclass
class TicketStatusChangedEvent(DomainEvent):
    """Event fired when a ticket status changes."""
    
    def __init__(self, ticket_id: int, empresa_id: int, old_status: str, new_status: str, **kwargs):
        super().__init__(
            event_id=str(uuid.uuid4()),
            event_type=EventType.TICKET_STATUS_CHANGED,
            aggregate_type="ticket",
            aggregate_id=str(ticket_id),
            payload={
                "ticket_id": ticket_id,
                "old_status": old_status,
                "new_status": new_status,
                **kwargs
            },
            empresa_id=empresa_id
        )


@dataclass
class ServiceOrderCreatedEvent(DomainEvent):
    """Event fired when a service order is created."""
    
    def __init__(self, service_order_id: int, empresa_id: int, numero_os: str, **kwargs):
        super().__init__(
            event_id=str(uuid.uuid4()),
            event_type=EventType.SERVICE_ORDER_CREATED,
            aggregate_type="service_order",
            aggregate_id=str(service_order_id),
            payload={
                "service_order_id": service_order_id,
                "numero_os": numero_os,
                **kwargs
            },
            empresa_id=empresa_id
        )


class EventDispatcher:
    """
    Event dispatcher for publishing domain events using the outbox pattern.
    Ensures transactional consistency between business operations and event publishing.
    """
    
    def __init__(self):
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    async def publish_event(self, session: AsyncSession, event: DomainEvent) -> None:
        """
        Publish a domain event to the outbox table.
        
        Args:
            session: Database session (must be part of the business transaction)
            event: Domain event to publish
        """
        try:
            # Validate event
            if not event.event_type or not event.aggregate_type or not event.aggregate_id:
                raise ValidationError("Event must have type, aggregate_type, and aggregate_id")
            
            # Create outbox entry
            outbox_event = OutboxEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                payload=event.payload,
                metadata=event.metadata or {},
                empresa_id=event.empresa_id,
                status=EventStatus.PENDING
            )
            
            session.add(outbox_event)
            await session.flush()
            
            logger.info(f"Published event {event.event_type} for {event.aggregate_type}:{event.aggregate_id}")
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_type}: {e}")
            raise
    
    async def publish_events(self, session: AsyncSession, events: List[DomainEvent]) -> None:
        """
        Publish multiple domain events in a single transaction.
        
        Args:
            session: Database session
            events: List of domain events to publish
        """
        for event in events:
            await self.publish_event(session, event)
    
    async def get_pending_events(
        self, 
        session: AsyncSession, 
        limit: int = 100,
        event_types: Optional[List[str]] = None
    ) -> List[OutboxEvent]:
        """
        Get pending events for processing.
        
        Args:
            session: Database session
            limit: Maximum number of events to retrieve
            event_types: Optional filter by event types
            
        Returns:
            List of pending outbox events
        """
        query = select(OutboxEvent).where(
            and_(
                OutboxEvent.status == EventStatus.PENDING,
                or_(
                    OutboxEvent.next_retry_at.is_(None),
                    OutboxEvent.next_retry_at <= datetime.utcnow()
                )
            )
        ).order_by(OutboxEvent.created_at).limit(limit)
        
        if event_types:
            query = query.where(OutboxEvent.event_type.in_(event_types))
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def mark_event_processing(self, session: AsyncSession, event_id: str) -> None:
        """Mark an event as being processed."""
        query = select(OutboxEvent).where(OutboxEvent.event_id == event_id)
        result = await session.execute(query)
        event = result.scalar_one_or_none()
        
        if event:
            event.status = EventStatus.PROCESSING
            await session.flush()
    
    async def mark_event_published(self, session: AsyncSession, event_id: str) -> None:
        """Mark an event as successfully published."""
        query = select(OutboxEvent).where(OutboxEvent.event_id == event_id)
        result = await session.execute(query)
        event = result.scalar_one_or_none()
        
        if event:
            event.status = EventStatus.PUBLISHED
            event.processed_at = datetime.utcnow()
            await session.flush()
    
    async def mark_event_failed(
        self, 
        session: AsyncSession, 
        event_id: str, 
        error_message: str,
        retry_delay_minutes: int = 5
    ) -> None:
        """Mark an event as failed and schedule retry if applicable."""
        query = select(OutboxEvent).where(OutboxEvent.event_id == event_id)
        result = await session.execute(query)
        event = result.scalar_one_or_none()
        
        if event:
            event.retry_count += 1
            event.last_error = error_message
            
            if event.retry_count >= event.max_retries:
                event.status = EventStatus.FAILED
                logger.error(f"Event {event_id} failed permanently after {event.retry_count} retries")
            else:
                event.status = EventStatus.RETRYING
                event.next_retry_at = datetime.utcnow() + timedelta(minutes=retry_delay_minutes * event.retry_count)
                logger.warning(f"Event {event_id} failed, scheduling retry {event.retry_count}/{event.max_retries}")
            
            await session.flush()
    
    def register_handler(self, event_type: str, handler: Callable) -> None:
        """
        Register an event handler for a specific event type.
        
        Args:
            event_type: Event type to handle
            handler: Async function to handle the event
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.info(f"Registered handler for event type: {event_type}")
    
    async def process_event(self, session: AsyncSession, event: OutboxEvent) -> bool:
        """
        Process a single event by calling registered handlers.
        
        Args:
            session: Database session
            event: Outbox event to process
            
        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            await self.mark_event_processing(session, event.event_id)
            
            # Get handlers for this event type
            handlers = self._event_handlers.get(event.event_type, [])
            
            if not handlers:
                logger.warning(f"No handlers registered for event type: {event.event_type}")
                await self.mark_event_published(session, event.event_id)
                return True
            
            # Execute all handlers
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Handler failed for event {event.event_id}: {e}")
                    raise
            
            await self.mark_event_published(session, event.event_id)
            logger.info(f"Successfully processed event {event.event_id}")
            return True
            
        except Exception as e:
            await self.mark_event_failed(session, event.event_id, str(e))
            return False
    
    async def cleanup_old_events(
        self, 
        session: AsyncSession, 
        days_old: int = 30
    ) -> int:
        """
        Clean up old processed events to prevent table growth.
        
        Args:
            session: Database session
            days_old: Delete events older than this many days
            
        Returns:
            Number of events deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        query = select(OutboxEvent).where(
            and_(
                OutboxEvent.status == EventStatus.PUBLISHED,
                OutboxEvent.processed_at < cutoff_date
            )
        )
        
        result = await session.execute(query)
        events_to_delete = result.scalars().all()
        
        for event in events_to_delete:
            await session.delete(event)
        
        await session.flush()
        
        logger.info(f"Cleaned up {len(events_to_delete)} old events")
        return len(events_to_delete)


# Global event dispatcher instance
event_dispatcher = EventDispatcher()


# Convenience functions for common events
async def publish_inventory_created(
    session: AsyncSession, 
    item_id: int, 
    empresa_id: int, 
    catalog_id: int, 
    quantity: int,
    **kwargs
) -> None:
    """Publish inventory item created event."""
    event = InventoryItemCreatedEvent(item_id, empresa_id, catalog_id, quantity, **kwargs)
    await event_dispatcher.publish_event(session, event)


async def publish_asset_created(
    session: AsyncSession, 
    asset_id: int, 
    empresa_id: int, 
    serial_text: str,
    **kwargs
) -> None:
    """Publish asset created event."""
    event = AssetCreatedEvent(asset_id, empresa_id, serial_text, **kwargs)
    await event_dispatcher.publish_event(session, event)


async def publish_ticket_created(
    session: AsyncSession, 
    ticket_id: int, 
    empresa_id: int, 
    numero: str, 
    titulo: str,
    **kwargs
) -> None:
    """Publish ticket created event."""
    event = TicketCreatedEvent(ticket_id, empresa_id, numero, titulo, **kwargs)
    await event_dispatcher.publish_event(session, event)


async def publish_ticket_status_changed(
    session: AsyncSession, 
    ticket_id: int, 
    empresa_id: int, 
    old_status: str, 
    new_status: str,
    **kwargs
) -> None:
    """Publish ticket status changed event."""
    event = TicketStatusChangedEvent(ticket_id, empresa_id, old_status, new_status, **kwargs)
    await event_dispatcher.publish_event(session, event)


async def publish_service_order_created(
    session: AsyncSession, 
    service_order_id: int, 
    empresa_id: int, 
    numero_os: str,
    **kwargs
) -> None:
    """Publish service order created event."""
    event = ServiceOrderCreatedEvent(service_order_id, empresa_id, numero_os, **kwargs)
    await event_dispatcher.publish_event(session, event)