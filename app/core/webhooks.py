"""
Webhook worker system for reliable external system integrations.
Handles webhook delivery, retry logic, and monitoring.
"""

import logging
import json
import hmac
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.event_models import (
    OutboxEvent, WebhookEndpoint, WebhookDelivery, 
    EventStatus, IntegrationLog
)
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class WebhookWorker:
    """
    Webhook worker for delivering events to external systems.
    Handles retry logic, signature verification, and delivery tracking.
    """
    
    def __init__(self, max_concurrent_deliveries: int = 10):
        self.max_concurrent_deliveries = max_concurrent_deliveries
        self._session_timeout = aiohttp.ClientTimeout(total=30)
    
    async def process_events(self, session: AsyncSession) -> int:
        """
        Process pending events and deliver them to configured webhooks.
        
        Args:
            session: Database session
            
        Returns:
            Number of events processed
        """
        try:
            # Get pending events
            events = await self._get_pending_events(session)
            if not events:
                return 0
            
            # Get active webhook endpoints
            endpoints = await self._get_active_endpoints(session)
            if not endpoints:
                logger.info("No active webhook endpoints configured")
                return 0
            
            processed_count = 0
            
            # Process events in batches to avoid overwhelming external systems
            for event in events:
                matching_endpoints = self._filter_endpoints_for_event(endpoints, event)
                
                if matching_endpoints:
                    await self._deliver_event_to_endpoints(session, event, matching_endpoints)
                    processed_count += 1
                
                # Small delay between events to be respectful to external systems
                await asyncio.sleep(0.1)
            
            logger.info(f"Processed {processed_count} events for webhook delivery")
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing webhook events: {e}")
            return 0
    
    async def _get_pending_events(self, session: AsyncSession, limit: int = 50) -> List[OutboxEvent]:
        """Get pending events that need webhook delivery."""
        query = select(OutboxEvent).where(
            OutboxEvent.status == EventStatus.PUBLISHED
        ).order_by(OutboxEvent.created_at).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def _get_active_endpoints(self, session: AsyncSession) -> List[WebhookEndpoint]:
        """Get all active webhook endpoints."""
        query = select(WebhookEndpoint).where(WebhookEndpoint.active == True)
        result = await session.execute(query)
        return result.scalars().all()
    
    def _filter_endpoints_for_event(
        self, 
        endpoints: List[WebhookEndpoint], 
        event: OutboxEvent
    ) -> List[WebhookEndpoint]:
        """Filter endpoints that should receive this event."""
        matching_endpoints = []
        
        for endpoint in endpoints:
            # Check if endpoint is interested in this event type
            if event.event_type in endpoint.event_types:
                # Check tenant scoping
                if endpoint.empresa_id is None or endpoint.empresa_id == event.empresa_id:
                    matching_endpoints.append(endpoint)
        
        return matching_endpoints
    
    async def _deliver_event_to_endpoints(
        self, 
        session: AsyncSession, 
        event: OutboxEvent, 
        endpoints: List[WebhookEndpoint]
    ) -> None:
        """Deliver an event to multiple webhook endpoints."""
        delivery_tasks = []
        
        for endpoint in endpoints:
            task = self._deliver_to_endpoint(session, event, endpoint)
            delivery_tasks.append(task)
        
        # Execute deliveries concurrently but limit concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent_deliveries)
        
        async def limited_delivery(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(
            *[limited_delivery(task) for task in delivery_tasks],
            return_exceptions=True
        )
        
        # Log any delivery failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Webhook delivery failed for endpoint {endpoints[i].id}: {result}")
    
    async def _deliver_to_endpoint(
        self, 
        session: AsyncSession, 
        event: OutboxEvent, 
        endpoint: WebhookEndpoint
    ) -> bool:
        """
        Deliver an event to a specific webhook endpoint.
        
        Args:
            session: Database session
            event: Event to deliver
            endpoint: Webhook endpoint configuration
            
        Returns:
            True if delivery succeeded, False otherwise
        """
        delivery_start = datetime.utcnow()
        
        try:
            # Prepare webhook payload
            payload = self._prepare_webhook_payload(event)
            headers = self._prepare_headers(endpoint, payload)
            
            # Make HTTP request
            async with aiohttp.ClientSession(timeout=self._session_timeout) as client_session:
                start_time = datetime.utcnow()
                
                async with client_session.post(
                    endpoint.url,
                    json=payload,
                    headers=headers
                ) as response:
                    end_time = datetime.utcnow()
                    duration_ms = int((end_time - start_time).total_seconds() * 1000)
                    
                    response_body = await response.text()
                    response_headers = dict(response.headers)
                    
                    success = 200 <= response.status < 300
                    
                    # Log delivery attempt
                    await self._log_delivery(
                        session, endpoint, event, payload, headers,
                        response.status, response_body, response_headers,
                        duration_ms, success, None
                    )
                    
                    if success:
                        logger.info(f"Webhook delivered successfully to {endpoint.url} for event {event.event_id}")
                        return True
                    else:
                        logger.warning(f"Webhook delivery failed with status {response.status} to {endpoint.url}")
                        return False
        
        except asyncio.TimeoutError:
            error_msg = f"Webhook delivery timeout to {endpoint.url}"
            logger.warning(error_msg)
            await self._log_delivery(
                session, endpoint, event, payload, headers,
                None, None, None, None, False, error_msg
            )
            return False
        
        except Exception as e:
            error_msg = f"Webhook delivery error to {endpoint.url}: {str(e)}"
            logger.error(error_msg)
            await self._log_delivery(
                session, endpoint, event, payload, headers,
                None, None, None, None, False, error_msg
            )
            return False
    
    def _prepare_webhook_payload(self, event: OutboxEvent) -> Dict[str, Any]:
        """Prepare the webhook payload from an outbox event."""
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "payload": event.payload,
            "metadata": event.metadata or {},
            "timestamp": event.created_at.isoformat(),
            "empresa_id": event.empresa_id
        }
    
    def _prepare_headers(self, endpoint: WebhookEndpoint, payload: Dict[str, Any]) -> Dict[str, str]:
        """Prepare HTTP headers for webhook delivery."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Sistema-Boladao-Webhook/1.0",
            "X-Webhook-Delivery": str(datetime.utcnow().timestamp())
        }
        
        # Add signature if secret is configured
        if endpoint.secret:
            signature = self._generate_signature(endpoint.secret, json.dumps(payload))
            headers["X-Hub-Signature-256"] = f"sha256={signature}"
        
        return headers
    
    def _generate_signature(self, secret: str, payload: str) -> str:
        """Generate HMAC signature for webhook verification."""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _log_delivery(
        self,
        session: AsyncSession,
        endpoint: WebhookEndpoint,
        event: OutboxEvent,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        status_code: Optional[int],
        response_body: Optional[str],
        response_headers: Optional[Dict[str, str]],
        duration_ms: Optional[int],
        success: bool,
        error_message: Optional[str]
    ) -> None:
        """Log webhook delivery attempt."""
        delivery = WebhookDelivery(
            webhook_endpoint_id=endpoint.id,
            event_id=event.event_id,
            url=endpoint.url,
            headers=headers,
            payload=payload,
            status_code=status_code,
            response_body=response_body,
            response_headers=response_headers,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        )
        
        session.add(delivery)
        await session.flush()
    
    async def cleanup_old_deliveries(
        self, 
        session: AsyncSession, 
        days_old: int = 7
    ) -> int:
        """
        Clean up old webhook delivery logs.
        
        Args:
            session: Database session
            days_old: Delete deliveries older than this many days
            
        Returns:
            Number of deliveries deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        query = select(WebhookDelivery).where(
            WebhookDelivery.attempted_at < cutoff_date
        )
        
        result = await session.execute(query)
        deliveries_to_delete = result.scalars().all()
        
        for delivery in deliveries_to_delete:
            await session.delete(delivery)
        
        await session.flush()
        
        logger.info(f"Cleaned up {len(deliveries_to_delete)} old webhook deliveries")
        return len(deliveries_to_delete)


class WebhookManager:
    """Manager for webhook endpoint configuration and testing."""
    
    async def create_endpoint(
        self,
        session: AsyncSession,
        name: str,
        url: str,
        event_types: List[str],
        empresa_id: Optional[int] = None,
        secret: Optional[str] = None,
        timeout_seconds: int = 30,
        max_retries: int = 3
    ) -> WebhookEndpoint:
        """Create a new webhook endpoint."""
        if not url.startswith(('http://', 'https://')):
            raise ValidationError("Webhook URL must start with http:// or https://")
        
        if not event_types:
            raise ValidationError("At least one event type must be specified")
        
        endpoint = WebhookEndpoint(
            name=name,
            url=url,
            secret=secret,
            event_types=event_types,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            empresa_id=empresa_id
        )
        
        session.add(endpoint)
        await session.flush()
        
        logger.info(f"Created webhook endpoint: {name} -> {url}")
        return endpoint
    
    async def test_endpoint(
        self,
        session: AsyncSession,
        endpoint_id: int
    ) -> Dict[str, Any]:
        """Test a webhook endpoint with a sample payload."""
        query = select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id)
        result = await session.execute(query)
        endpoint = result.scalar_one_or_none()
        
        if not endpoint:
            raise ValidationError(f"Webhook endpoint {endpoint_id} not found")
        
        # Create test payload
        test_payload = {
            "event_id": "test-event-id",
            "event_type": "webhook.test",
            "aggregate_type": "test",
            "aggregate_id": "test-123",
            "payload": {"message": "This is a test webhook delivery"},
            "metadata": {"test": True},
            "timestamp": datetime.utcnow().isoformat(),
            "empresa_id": endpoint.empresa_id
        }
        
        worker = WebhookWorker()
        headers = worker._prepare_headers(endpoint, test_payload)
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=endpoint.timeout_seconds)) as client_session:
                start_time = datetime.utcnow()
                
                async with client_session.post(
                    endpoint.url,
                    json=test_payload,
                    headers=headers
                ) as response:
                    end_time = datetime.utcnow()
                    duration_ms = int((end_time - start_time).total_seconds() * 1000)
                    
                    response_body = await response.text()
                    success = 200 <= response.status < 300
                    
                    # Log test delivery
                    await worker._log_delivery(
                        session, endpoint, None, test_payload, headers,
                        response.status, response_body, dict(response.headers),
                        duration_ms, success, None
                    )
                    
                    return {
                        "success": success,
                        "status_code": response.status,
                        "response_body": response_body,
                        "duration_ms": duration_ms
                    }
        
        except Exception as e:
            error_msg = str(e)
            
            # Log failed test
            await worker._log_delivery(
                session, endpoint, None, test_payload, headers,
                None, None, None, None, False, error_msg
            )
            
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_endpoint_stats(
        self,
        session: AsyncSession,
        endpoint_id: int,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get delivery statistics for a webhook endpoint."""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(WebhookDelivery).where(
            and_(
                WebhookDelivery.webhook_endpoint_id == endpoint_id,
                WebhookDelivery.attempted_at >= since_date
            )
        )
        
        result = await session.execute(query)
        deliveries = result.scalars().all()
        
        total_deliveries = len(deliveries)
        successful_deliveries = sum(1 for d in deliveries if d.success)
        failed_deliveries = total_deliveries - successful_deliveries
        
        avg_duration = 0
        if deliveries:
            durations = [d.duration_ms for d in deliveries if d.duration_ms is not None]
            if durations:
                avg_duration = sum(durations) / len(durations)
        
        return {
            "total_deliveries": total_deliveries,
            "successful_deliveries": successful_deliveries,
            "failed_deliveries": failed_deliveries,
            "success_rate": successful_deliveries / total_deliveries if total_deliveries > 0 else 0,
            "average_duration_ms": round(avg_duration, 2),
            "period_days": days
        }


# Global instances
webhook_worker = WebhookWorker()
webhook_manager = WebhookManager()