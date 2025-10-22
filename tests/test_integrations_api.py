"""
Comprehensive tests for integration API endpoints.
Tests events, webhooks, WhatsApp, and AI gateway functionality.
"""

import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock

from app.core.events import event_dispatcher
from app.core.webhooks import webhook_manager
from app.integrations.whatsapp import whatsapp_service
from app.integrations.ai_gateway import ai_gateway_service


@pytest.mark.integration
class TestEventsAPI:
    """Integration tests for events API endpoints."""
    
    async def test_publish_event_success(self, client: AsyncClient, admin_user: dict):
        """Test successful event publishing."""
        response = await client.post("/api/integrations/events/publish",
            headers=admin_user["headers"],
            json={
                "event_type": "ticket.created",
                "aggregate_type": "ticket",
                "aggregate_id": "123",
                "payload": {
                    "ticket_id": 123,
                    "titulo": "Test Ticket"
                },
                "metadata": {"source": "test"}
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "event_id" in data
        assert data["event_type"] == "ticket.created"
    
    async def test_publish_event_unauthorized(self, client: AsyncClient, authenticated_user: dict):
        """Test event publishing without admin role."""
        response = await client.post("/api/integrations/events/publish",
            headers=authenticated_user["headers"],
            json={
                "event_type": "ticket.created",
                "aggregate_type": "ticket",
                "aggregate_id": "123",
                "payload": {"ticket_id": 123}
            }
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    async def test_get_pending_events_success(self, client: AsyncClient, admin_user: dict):
        """Test getting pending events."""
        response = await client.get("/api/integrations/events/pending",
            headers=admin_user["headers"]
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "events" in data
        assert "total" in data
    
    async def test_publish_event_invalid_data(self, client: AsyncClient, admin_user: dict):
        """Test event publishing with invalid data."""
        response = await client.post("/api/integrations/events/publish",
            headers=admin_user["headers"],
            json={
                "event_type": "",  # Empty event type
                "aggregate_type": "",  # Empty aggregate type
                "aggregate_id": "",  # Empty aggregate ID
                "payload": {}  # Empty payload
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
class TestWebhooksAPI:
    """Integration tests for webhooks API endpoints."""
    
    async def test_create_webhook_success(self, client: AsyncClient, admin_user: dict):
        """Test successful webhook creation."""
        response = await client.post("/api/integrations/webhooks",
            headers=admin_user["headers"],
            json={
                "name": "Test Webhook",
                "url": "https://api.example.com/webhook",
                "event_types": ["ticket.created", "ticket.updated"],
                "secret": "webhook-secret",
                "timeout_seconds": 30,
                "max_retries": 3
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "endpoint_id" in data
        assert data["name"] == "Test Webhook"
    
    async def test_create_webhook_invalid_url(self, client: AsyncClient, admin_user: dict):
        """Test webhook creation with invalid URL."""
        response = await client.post("/api/integrations/webhooks",
            headers=admin_user["headers"],
            json={
                "name": "Test Webhook",
                "url": "invalid-url",  # Invalid URL format
                "event_types": ["ticket.created"],
                "timeout_seconds": 30,
                "max_retries": 3
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    @patch('app.core.webhooks.aiohttp.ClientSession.post')
    async def test_test_webhook_success(self, mock_post, client: AsyncClient, admin_user: dict, db_session: AsyncSession):
        """Test webhook testing functionality."""
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")
        mock_response.headers = {}
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Create webhook first
        webhook = await webhook_manager.create_endpoint(
            session=db_session,
            name="Test Webhook",
            url="https://api.example.com/webhook",
            event_types=["ticket.created"],
            empresa_id=admin_user["user"].contato.empresa_id
        )
        await db_session.commit()
        
        response = await client.post(f"/api/integrations/webhooks/{webhook.id}/test",
            headers=admin_user["headers"]
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["test_result"]["success"] is True
    
    async def test_webhook_stats_success(self, client: AsyncClient, admin_user: dict, db_session: AsyncSession):
        """Test webhook statistics endpoint."""
        # Create webhook first
        webhook = await webhook_manager.create_endpoint(
            session=db_session,
            name="Test Webhook",
            url="https://api.example.com/webhook",
            event_types=["ticket.created"],
            empresa_id=admin_user["user"].contato.empresa_id
        )
        await db_session.commit()
        
        response = await client.get(f"/api/integrations/webhooks/{webhook.id}/stats",
            headers=admin_user["headers"]
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "statistics" in data
        assert "total_deliveries" in data["statistics"]


@pytest.mark.integration
class TestWhatsAppAPI:
    """Integration tests for WhatsApp API endpoints."""
    
    @patch('app.integrations.whatsapp.WhatsAppService._simulate_api_call')
    async def test_send_whatsapp_message_success(self, mock_api_call, client: AsyncClient, authenticated_user: dict, mock_whatsapp_response):
        """Test successful WhatsApp message sending."""
        mock_api_call.return_value = mock_whatsapp_response
        
        response = await client.post("/api/integrations/whatsapp/send",
            headers=authenticated_user["headers"],
            json={
                "phone_number": "+5511999999999",
                "message": "Test message"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["phone_number"] == "+5511999999999"
    
    async def test_send_whatsapp_invalid_phone(self, client: AsyncClient, authenticated_user: dict):
        """Test WhatsApp message with invalid phone number."""
        response = await client.post("/api/integrations/whatsapp/send",
            headers=authenticated_user["headers"],
            json={
                "phone_number": "invalid-phone",
                "message": "Test message"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    async def test_whatsapp_status_success(self, client: AsyncClient, authenticated_user: dict):
        """Test WhatsApp status endpoint."""
        response = await client.get("/api/integrations/whatsapp/status",
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "features" in data
        assert "available_templates" in data


@pytest.mark.integration
class TestAIAPI:
    """Integration tests for AI gateway API endpoints."""
    
    async def test_ai_analyze_ticket_classification(self, client: AsyncClient, authenticated_user: dict):
        """Test AI ticket classification analysis."""
        response = await client.post("/api/integrations/ai/analyze",
            headers=authenticated_user["headers"],
            json={
                "text": "Meu computador está muito lento e travando constantemente",
                "analysis_type": "ticket_classification"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "result" in data
        assert "classification" in data["result"]
        assert "category" in data["result"]["classification"]
    
    async def test_ai_analyze_sentiment(self, client: AsyncClient, authenticated_user: dict):
        """Test AI sentiment analysis."""
        response = await client.post("/api/integrations/ai/analyze",
            headers=authenticated_user["headers"],
            json={
                "text": "Estou muito insatisfeito com o atendimento",
                "analysis_type": "sentiment_analysis"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "result" in data
        assert "sentiment" in data["result"]
        assert "sentiment" in data["result"]["sentiment"]
    
    async def test_ai_analyze_invalid_type(self, client: AsyncClient, authenticated_user: dict):
        """Test AI analysis with invalid type."""
        response = await client.post("/api/integrations/ai/analyze",
            headers=authenticated_user["headers"],
            json={
                "text": "Test text",
                "analysis_type": "invalid_type"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    async def test_ai_status_success(self, client: AsyncClient, authenticated_user: dict):
        """Test AI gateway status endpoint."""
        response = await client.get("/api/integrations/ai/status",
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "features" in data
        assert "available_models" in data


@pytest.mark.unit
class TestEventDispatcher:
    """Unit tests for event dispatcher."""
    
    async def test_publish_event_to_outbox(self, db_session: AsyncSession):
        """Test publishing event to outbox table."""
        from app.core.events import DomainEvent
        
        event = DomainEvent(
            event_id="test-event-123",
            event_type="ticket.created",
            aggregate_type="ticket",
            aggregate_id="123",
            payload={"ticket_id": 123, "title": "Test Ticket"},
            empresa_id=1
        )
        
        await event_dispatcher.publish_event(db_session, event)
        await db_session.commit()
        
        # Verify event was stored in outbox
        pending_events = await event_dispatcher.get_pending_events(db_session)
        assert len(pending_events) >= 1
        
        stored_event = next((e for e in pending_events if e.event_id == "test-event-123"), None)
        assert stored_event is not None
        assert stored_event.event_type == "ticket.created"
        assert stored_event.payload["ticket_id"] == 123
    
    async def test_mark_event_published(self, db_session: AsyncSession):
        """Test marking event as published."""
        from app.core.events import DomainEvent
        
        event = DomainEvent(
            event_id="test-event-456",
            event_type="ticket.updated",
            aggregate_type="ticket",
            aggregate_id="456",
            payload={"ticket_id": 456},
            empresa_id=1
        )
        
        await event_dispatcher.publish_event(db_session, event)
        await event_dispatcher.mark_event_published(db_session, "test-event-456")
        await db_session.commit()
        
        # Event should no longer be pending
        pending_events = await event_dispatcher.get_pending_events(db_session)
        pending_event = next((e for e in pending_events if e.event_id == "test-event-456"), None)
        assert pending_event is None


@pytest.mark.unit
class TestWhatsAppService:
    """Unit tests for WhatsApp service."""
    
    async def test_validate_phone_number(self):
        """Test phone number validation."""
        service = whatsapp_service
        
        # Valid phone numbers
        assert service._validate_phone_number("+5511999999999")
        assert service._validate_phone_number("11999999999")
        assert service._validate_phone_number("+1234567890")
        
        # Invalid phone numbers
        assert not service._validate_phone_number("invalid")
        assert not service._validate_phone_number("123")
        assert not service._validate_phone_number("")
        assert not service._validate_phone_number("12345678901234567890")  # Too long
    
    async def test_prepare_message_payload(self):
        """Test message payload preparation."""
        from app.integrations.whatsapp import WhatsAppMessage, MessageType
        
        service = whatsapp_service
        
        # Text message
        text_message = WhatsAppMessage(
            to="+5511999999999",
            message_type=MessageType.TEXT,
            content={"text": "Hello World"}
        )
        
        payload = service._prepare_message_payload(text_message)
        
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "+5511999999999"
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Hello World"
        
        # Template message
        template_message = WhatsAppMessage(
            to="+5511999999999",
            message_type=MessageType.TEMPLATE,
            content={},
            template_name="ticket_created",
            template_language="pt_BR",
            template_parameters=["TKT-123", "Test Ticket"]
        )
        
        payload = service._prepare_message_payload(template_message)
        
        assert payload["type"] == "template"
        assert payload["template"]["name"] == "ticket_created"
        assert payload["template"]["language"]["code"] == "pt_BR"


@pytest.mark.unit
class TestAIGateway:
    """Unit tests for AI gateway service."""
    
    async def test_ticket_classification_simulation(self, db_session: AsyncSession):
        """Test AI ticket classification simulation."""
        service = ai_gateway_service
        
        # Hardware-related ticket
        classification = await service.classify_ticket(
            session=db_session,
            title="Computador com problema",
            description="Meu computador está travando constantemente",
            empresa_id=1
        )
        
        assert classification.category == "hardware"
        assert classification.priority in ["high", "normal", "low"]
        assert classification.confidence > 0
        
        # Software-related ticket
        classification = await service.classify_ticket(
            session=db_session,
            title="Erro no sistema",
            description="O software está apresentando erro",
            empresa_id=1
        )
        
        assert classification.category == "software"
        assert classification.confidence > 0
    
    async def test_sentiment_analysis_simulation(self, db_session: AsyncSession):
        """Test AI sentiment analysis simulation."""
        service = ai_gateway_service
        
        # Negative sentiment
        result = await service.analyze_sentiment(
            session=db_session,
            text="Estou muito insatisfeito com o atendimento ruim",
            empresa_id=1
        )
        
        assert result["sentiment"] == "negative"
        assert result["confidence"] > 0
        assert result["score"] < 0
        
        # Positive sentiment
        result = await service.analyze_sentiment(
            session=db_session,
            text="Excelente atendimento, muito obrigado",
            empresa_id=1
        )
        
        assert result["sentiment"] == "positive"
        assert result["confidence"] > 0
        assert result["score"] > 0


@pytest.mark.performance
class TestIntegrationsPerformance:
    """Performance tests for integration endpoints."""
    
    async def test_event_publishing_performance(self, client: AsyncClient, admin_user: dict, performance_timer):
        """Test event publishing performance."""
        performance_timer.start()
        response = await client.post("/api/integrations/events/publish",
            headers=admin_user["headers"],
            json={
                "event_type": "ticket.created",
                "aggregate_type": "ticket",
                "aggregate_id": "123",
                "payload": {"ticket_id": 123}
            }
        )
        performance_timer.stop()
        
        assert response.status_code == status.HTTP_200_OK
        assert performance_timer.duration < 1.0  # Should complete within 1 second
    
    async def test_ai_analysis_performance(self, client: AsyncClient, authenticated_user: dict, performance_timer):
        """Test AI analysis performance."""
        performance_timer.start()
        response = await client.post("/api/integrations/ai/analyze",
            headers=authenticated_user["headers"],
            json={
                "text": "Test text for analysis",
                "analysis_type": "sentiment_analysis"
            }
        )
        performance_timer.stop()
        
        assert response.status_code == status.HTTP_200_OK
        assert performance_timer.duration < 2.0  # Should complete within 2 seconds


@pytest.mark.security
class TestIntegrationsSecurity:
    """Security tests for integration endpoints."""
    
    async def test_webhook_secret_validation(self):
        """Test webhook secret generation and validation."""
        from app.core.webhooks import WebhookWorker
        
        worker = WebhookWorker()
        
        secret = "test-secret"
        payload = '{"test": "data"}'
        
        signature = worker._generate_signature(secret, payload)
        
        assert signature is not None
        assert len(signature) == 64  # SHA256 hex digest length
        
        # Same input should produce same signature
        signature2 = worker._generate_signature(secret, payload)
        assert signature == signature2
        
        # Different secret should produce different signature
        signature3 = worker._generate_signature("different-secret", payload)
        assert signature != signature3
    
    async def test_integration_authorization(self, client: AsyncClient, authenticated_user: dict):
        """Test that integration endpoints require proper authorization."""
        # Regular user should not be able to create webhooks
        response = await client.post("/api/integrations/webhooks",
            headers=authenticated_user["headers"],
            json={
                "name": "Test Webhook",
                "url": "https://api.example.com/webhook",
                "event_types": ["ticket.created"]
            }
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Regular user should not be able to publish events
        response = await client.post("/api/integrations/events/publish",
            headers=authenticated_user["headers"],
            json={
                "event_type": "ticket.created",
                "aggregate_type": "ticket",
                "aggregate_id": "123",
                "payload": {"ticket_id": 123}
            }
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN