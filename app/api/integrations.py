"""
API endpoints for integrations, events, and external system management.
Provides endpoints for webhook management, event publishing, and integration monitoring.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.core.authorization import (
    get_authorization_context, AuthorizationContext,
    Permission, require_admin_role
)
from app.core.exceptions import business_exception_to_http, BusinessLogicError
from app.core.events import event_dispatcher, DomainEvent
from app.core.webhooks import webhook_manager, webhook_worker
from app.integrations.whatsapp import whatsapp_notification_service
from app.integrations.ai_gateway import ai_assistant_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations", tags=["integrations"])


# Pydantic models for API requests/responses
class EventPublishRequest(BaseModel):
    """Request model for publishing domain events."""
    event_type: str = Field(..., description="Type of event to publish")
    aggregate_type: str = Field(..., description="Type of aggregate")
    aggregate_id: str = Field(..., description="ID of the aggregate")
    payload: Dict[str, Any] = Field(..., description="Event payload data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional event metadata")

    class Config:
        schema_extra = {
            "example": {
                "event_type": "ticket.created",
                "aggregate_type": "ticket",
                "aggregate_id": "123",
                "payload": {
                    "ticket_id": 123,
                    "numero": "TKT-2023-001234",
                    "titulo": "Test ticket"
                },
                "metadata": {"source": "api"}
            }
        }


class WebhookEndpointRequest(BaseModel):
    """Request model for creating webhook endpoints."""
    name: str = Field(..., description="Webhook endpoint name")
    url: str = Field(..., description="Webhook URL")
    event_types: List[str] = Field(..., description="List of event types to send")
    secret: Optional[str] = Field(None, description="Secret for signature verification")
    timeout_seconds: int = Field(30, ge=5, le=300, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")

    class Config:
        schema_extra = {
            "example": {
                "name": "External CRM Integration",
                "url": "https://api.example.com/webhooks/sistema-boladao",
                "event_types": ["ticket.created", "ticket.status.changed"],
                "secret": "webhook-secret-key",
                "timeout_seconds": 30,
                "max_retries": 3
            }
        }


class WhatsAppMessageRequest(BaseModel):
    """Request model for sending WhatsApp messages."""
    phone_number: str = Field(..., description="Recipient phone number with country code")
    message: str = Field(..., description="Message text to send")

    class Config:
        schema_extra = {
            "example": {
                "phone_number": "+5511999999999",
                "message": "Olá! Seu chamado foi atualizado."
            }
        }


class AIAnalysisRequest(BaseModel):
    """Request model for AI analysis."""
    text: str = Field(..., description="Text to analyze")
    analysis_type: str = Field(..., description="Type of analysis to perform")

    class Config:
        schema_extra = {
            "example": {
                "text": "Meu computador está muito lento e travando constantemente",
                "analysis_type": "ticket_classification"
            }
        }


@router.post(
    "/events/publish",
    responses={
        200: {"description": "Event published successfully"},
        400: {"description": "Invalid event data"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Publish domain event",
    description="Publish a domain event to the outbox for reliable delivery to external systems."
)
async def publish_event(
    payload: EventPublishRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_admin_role),
):
    """
    Publish a domain event to the outbox table.
    Requires admin role.
    """
    try:
        # Create domain event
        event = DomainEvent(
            event_id="",  # Will be auto-generated
            event_type=payload.event_type,
            aggregate_type=payload.aggregate_type,
            aggregate_id=payload.aggregate_id,
            payload=payload.payload,
            metadata=payload.metadata,
            empresa_id=auth_context.tenant.empresa_id
        )
        
        # Publish to outbox
        await event_dispatcher.publish_event(session, event)
        await session.commit()
        
        logger.info(f"Published event {payload.event_type} for {payload.aggregate_type}:{payload.aggregate_id}")
        
        return {
            "message": "Event published successfully",
            "event_id": event.event_id,
            "event_type": payload.event_type
        }
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error publishing event: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error publishing event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while publishing the event"
        )


@router.get(
    "/events/pending",
    responses={
        200: {"description": "List of pending events"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Get pending events",
    description="Retrieve list of pending events in the outbox."
)
async def get_pending_events(
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_admin_role),
    limit: int = 50,
):
    """Get pending events from the outbox."""
    try:
        events = await event_dispatcher.get_pending_events(session, limit)
        
        return {
            "events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": event.aggregate_id,
                    "status": event.status,
                    "created_at": event.created_at.isoformat(),
                    "retry_count": event.retry_count
                }
                for event in events
            ],
            "total": len(events)
        }
        
    except Exception as e:
        logger.exception(f"Error retrieving pending events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving events"
        )


@router.post(
    "/webhooks",
    responses={
        201: {"description": "Webhook endpoint created successfully"},
        400: {"description": "Invalid webhook configuration"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Create webhook endpoint",
    description="Create a new webhook endpoint for receiving event notifications."
)
async def create_webhook_endpoint(
    payload: WebhookEndpointRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_admin_role),
):
    """Create a new webhook endpoint."""
    try:
        endpoint = await webhook_manager.create_endpoint(
            session=session,
            name=payload.name,
            url=payload.url,
            event_types=payload.event_types,
            empresa_id=auth_context.tenant.empresa_id,
            secret=payload.secret,
            timeout_seconds=payload.timeout_seconds,
            max_retries=payload.max_retries
        )
        
        await session.commit()
        
        return {
            "message": "Webhook endpoint created successfully",
            "endpoint_id": endpoint.id,
            "name": endpoint.name,
            "url": endpoint.url
        }
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error creating webhook: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error creating webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the webhook endpoint"
        )


@router.post(
    "/webhooks/{endpoint_id}/test",
    responses={
        200: {"description": "Webhook test completed"},
        404: {"description": "Webhook endpoint not found"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Test webhook endpoint",
    description="Send a test message to a webhook endpoint to verify connectivity."
)
async def test_webhook_endpoint(
    endpoint_id: int,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_admin_role),
):
    """Test a webhook endpoint."""
    try:
        result = await webhook_manager.test_endpoint(session, endpoint_id)
        await session.commit()
        
        return {
            "message": "Webhook test completed",
            "endpoint_id": endpoint_id,
            "test_result": result
        }
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error testing webhook: {e}")
        raise business_exception_to_http(e)
    except Exception as e:
        logger.exception(f"Unexpected error testing webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while testing the webhook"
        )


@router.get(
    "/webhooks/{endpoint_id}/stats",
    responses={
        200: {"description": "Webhook endpoint statistics"},
        404: {"description": "Webhook endpoint not found"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Get webhook statistics",
    description="Retrieve delivery statistics for a webhook endpoint."
)
async def get_webhook_stats(
    endpoint_id: int,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_admin_role),
    days: int = 7,
):
    """Get webhook endpoint statistics."""
    try:
        stats = await webhook_manager.get_endpoint_stats(session, endpoint_id, days)
        
        return {
            "endpoint_id": endpoint_id,
            "statistics": stats
        }
        
    except Exception as e:
        logger.exception(f"Error retrieving webhook stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving webhook statistics"
        )


@router.post(
    "/webhooks/process",
    responses={
        200: {"description": "Webhook processing completed"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Process pending webhooks",
    description="Manually trigger processing of pending webhook deliveries."
)
async def process_webhooks(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(require_admin_role),
):
    """Manually trigger webhook processing."""
    try:
        # Process webhooks in background
        background_tasks.add_task(webhook_worker.process_events, session)
        
        return {
            "message": "Webhook processing started",
            "status": "processing"
        }
        
    except Exception as e:
        logger.exception(f"Error starting webhook processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while starting webhook processing"
        )


@router.post(
    "/whatsapp/send",
    responses={
        200: {"description": "WhatsApp message sent successfully"},
        400: {"description": "Invalid message data"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Send WhatsApp message",
    description="Send a WhatsApp message to a customer."
)
async def send_whatsapp_message(
    payload: WhatsAppMessageRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
):
    """Send a WhatsApp message."""
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_TICKETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to send WhatsApp messages"
            )
        
        success = await whatsapp_notification_service.send_custom_message(
            session=session,
            phone_number=payload.phone_number,
            message=payload.message,
            empresa_id=auth_context.tenant.empresa_id
        )
        
        await session.commit()
        
        if success:
            return {
                "message": "WhatsApp message sent successfully",
                "phone_number": payload.phone_number
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send WhatsApp message"
            )
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error sending WhatsApp message: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error sending WhatsApp message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while sending the WhatsApp message"
        )


@router.get(
    "/whatsapp/status",
    responses={
        200: {"description": "WhatsApp integration status"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Get WhatsApp integration status",
    description="Check the status of WhatsApp integration and configuration."
)
async def get_whatsapp_status(
    auth_context: AuthorizationContext = Depends(get_authorization_context),
):
    """Get WhatsApp integration status."""
    try:
        # Check permission
        if not auth_context.has_permission(Permission.VIEW_TICKETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view WhatsApp status"
            )
        
        return {
            "status": "configured",
            "integration_type": "whatsapp_business_api",
            "features": [
                "template_messaging",
                "text_messaging",
                "delivery_tracking"
            ],
            "available_templates": [
                "ticket_created",
                "ticket_status_changed",
                "service_order_completed",
                "sla_breach_warning"
            ]
        }
        
    except Exception as e:
        logger.exception(f"Error retrieving WhatsApp status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving WhatsApp status"
        )


@router.post(
    "/ai/analyze",
    responses={
        200: {"description": "AI analysis completed"},
        400: {"description": "Invalid analysis request"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Perform AI analysis",
    description="Perform AI analysis on text for classification, sentiment, or other insights."
)
async def perform_ai_analysis(
    payload: AIAnalysisRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthorizationContext = Depends(get_authorization_context),
):
    """Perform AI analysis on text."""
    try:
        # Check permission
        if not auth_context.has_permission(Permission.MANAGE_TICKETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to use AI analysis"
            )
        
        if payload.analysis_type == "ticket_classification":
            # Split text into title and description for classification
            lines = payload.text.split('\n', 1)
            title = lines[0]
            description = lines[1] if len(lines) > 1 else ""
            
            classification = await ai_assistant_service.ai_gateway.classify_ticket(
                session, title, description, auth_context.tenant.empresa_id
            )
            
            result = {
                "analysis_type": "ticket_classification",
                "classification": {
                    "category": classification.category,
                    "subcategory": classification.subcategory,
                    "priority": classification.priority,
                    "urgency": classification.urgency,
                    "confidence": classification.confidence,
                    "reasoning": classification.reasoning
                }
            }
        
        elif payload.analysis_type == "sentiment_analysis":
            sentiment = await ai_assistant_service.ai_gateway.analyze_sentiment(
                session, payload.text, auth_context.tenant.empresa_id
            )
            
            result = {
                "analysis_type": "sentiment_analysis",
                "sentiment": sentiment
            }
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported analysis type: {payload.analysis_type}"
            )
        
        await session.commit()
        
        return {
            "message": "AI analysis completed",
            "result": result
        }
        
    except BusinessLogicError as e:
        logger.warning(f"Business logic error in AI analysis: {e}")
        raise business_exception_to_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in AI analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during AI analysis"
        )


@router.get(
    "/ai/status",
    responses={
        200: {"description": "AI gateway status"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    },
    summary="Get AI gateway status",
    description="Check the status of AI gateway and available features."
)
async def get_ai_status(
    auth_context: AuthorizationContext = Depends(get_authorization_context),
):
    """Get AI gateway status."""
    try:
        # Check permission
        if not auth_context.has_permission(Permission.VIEW_TICKETS):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view AI status"
            )
        
        return {
            "status": "configured",
            "provider": "simulation",
            "features": [
                "ticket_classification",
                "sentiment_analysis",
                "automated_responses",
                "solution_suggestions",
                "conversation_summarization"
            ],
            "available_models": [
                "text_classification",
                "sentiment_analysis",
                "response_generation"
            ]
        }
        
    except Exception as e:
        logger.exception(f"Error retrieving AI status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving AI status"
        )