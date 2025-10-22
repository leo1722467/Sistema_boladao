"""
WhatsApp integration for customer notifications and communication.
Provides stubs for WhatsApp Business API integration with template messaging.
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.event_models import IntegrationLog
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class MessageStatus(str, Enum):
    """WhatsApp message status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageType(str, Enum):
    """WhatsApp message types."""
    TEXT = "text"
    TEMPLATE = "template"
    INTERACTIVE = "interactive"
    DOCUMENT = "document"
    IMAGE = "image"


@dataclass
class WhatsAppMessage:
    """WhatsApp message structure."""
    to: str  # Phone number with country code
    message_type: MessageType
    content: Dict[str, Any]
    template_name: Optional[str] = None
    template_language: str = "pt_BR"
    template_parameters: Optional[List[str]] = None


@dataclass
class WhatsAppTemplate:
    """WhatsApp message template."""
    name: str
    language: str
    category: str  # AUTHENTICATION, MARKETING, UTILITY
    components: List[Dict[str, Any]]
    description: str


class WhatsAppService:
    """
    WhatsApp Business API integration service.
    Handles message sending, template management, and webhook processing.
    """
    
    def __init__(self, access_token: Optional[str] = None, phone_number_id: Optional[str] = None):
        self.access_token = access_token or "WHATSAPP_ACCESS_TOKEN_PLACEHOLDER"
        self.phone_number_id = phone_number_id or "WHATSAPP_PHONE_NUMBER_ID_PLACEHOLDER"
        self.base_url = "https://graph.facebook.com/v18.0"
        self._session_timeout = aiohttp.ClientTimeout(total=30)
    
    async def send_message(
        self, 
        session: AsyncSession, 
        message: WhatsAppMessage,
        empresa_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message.
        
        Args:
            session: Database session for logging
            message: WhatsApp message to send
            empresa_id: Company ID for tenant scoping
            
        Returns:
            Response from WhatsApp API
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate phone number format
            if not self._validate_phone_number(message.to):
                raise ValidationError(f"Invalid phone number format: {message.to}")
            
            # Prepare API payload
            payload = self._prepare_message_payload(message)
            
            # In production, this would make actual API call
            # For now, we simulate the response
            response_data = await self._simulate_api_call(payload)
            
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Log the integration attempt
            await self._log_integration(
                session, "send_message", payload, response_data,
                True, None, duration_ms, empresa_id
            )
            
            logger.info(f"WhatsApp message sent to {message.to}: {response_data.get('message_id')}")
            return response_data
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            await self._log_integration(
                session, "send_message", {"to": message.to}, None,
                False, str(e), duration_ms, empresa_id
            )
            
            logger.error(f"Failed to send WhatsApp message to {message.to}: {e}")
            raise
    
    async def send_template_message(
        self,
        session: AsyncSession,
        to: str,
        template_name: str,
        parameters: Optional[List[str]] = None,
        language: str = "pt_BR",
        empresa_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp template message.
        
        Args:
            session: Database session
            to: Recipient phone number
            template_name: Template name
            parameters: Template parameters
            language: Template language
            empresa_id: Company ID
            
        Returns:
            API response
        """
        message = WhatsAppMessage(
            to=to,
            message_type=MessageType.TEMPLATE,
            content={},
            template_name=template_name,
            template_language=language,
            template_parameters=parameters or []
        )
        
        return await self.send_message(session, message, empresa_id)
    
    async def send_text_message(
        self,
        session: AsyncSession,
        to: str,
        text: str,
        empresa_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send a simple text message.
        
        Args:
            session: Database session
            to: Recipient phone number
            text: Message text
            empresa_id: Company ID
            
        Returns:
            API response
        """
        message = WhatsAppMessage(
            to=to,
            message_type=MessageType.TEXT,
            content={"text": text}
        )
        
        return await self.send_message(session, message, empresa_id)
    
    def _validate_phone_number(self, phone: str) -> bool:
        """Validate phone number format (basic validation)."""
        # Remove common formatting characters
        clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        
        # Check if it's all digits and has reasonable length
        return clean_phone.isdigit() and 10 <= len(clean_phone) <= 15
    
    def _prepare_message_payload(self, message: WhatsAppMessage) -> Dict[str, Any]:
        """Prepare WhatsApp API payload."""
        payload = {
            "messaging_product": "whatsapp",
            "to": message.to,
            "type": message.message_type.value
        }
        
        if message.message_type == MessageType.TEXT:
            payload["text"] = {"body": message.content["text"]}
        
        elif message.message_type == MessageType.TEMPLATE:
            template_payload = {
                "name": message.template_name,
                "language": {"code": message.template_language}
            }
            
            if message.template_parameters:
                template_payload["components"] = [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": param} for param in message.template_parameters]
                }]
            
            payload["template"] = template_payload
        
        return payload
    
    async def _simulate_api_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate WhatsApp API call for development/testing.
        In production, this would make actual HTTP request to WhatsApp API.
        """
        # Simulate API response
        return {
            "messaging_product": "whatsapp",
            "contacts": [{"input": payload["to"], "wa_id": payload["to"]}],
            "messages": [{"id": f"wamid.{datetime.utcnow().timestamp()}"}],
            "message_id": f"msg_{int(datetime.utcnow().timestamp())}",
            "status": "sent"
        }
    
    async def _log_integration(
        self,
        session: AsyncSession,
        operation: str,
        request_data: Dict[str, Any],
        response_data: Optional[Dict[str, Any]],
        success: bool,
        error_message: Optional[str],
        duration_ms: int,
        empresa_id: Optional[int]
    ) -> None:
        """Log WhatsApp integration activity."""
        log_entry = IntegrationLog(
            integration_type="whatsapp",
            operation=operation,
            request_data=request_data,
            response_data=response_data,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            empresa_id=empresa_id
        )
        
        session.add(log_entry)
        await session.flush()


class WhatsAppTemplateManager:
    """Manager for WhatsApp message templates."""
    
    # Predefined templates for common notifications
    TEMPLATES = {
        "ticket_created": WhatsAppTemplate(
            name="ticket_created",
            language="pt_BR",
            category="UTILITY",
            description="Notification when a new ticket is created",
            components=[
                {
                    "type": "BODY",
                    "text": "Olá! Seu chamado #{ticket_number} foi criado com sucesso. Título: {title}. Acompanhe o status pelo nosso sistema."
                }
            ]
        ),
        "ticket_status_changed": WhatsAppTemplate(
            name="ticket_status_changed",
            language="pt_BR",
            category="UTILITY",
            description="Notification when ticket status changes",
            components=[
                {
                    "type": "BODY",
                    "text": "Seu chamado #{ticket_number} teve o status alterado para: {new_status}. Acesse nosso sistema para mais detalhes."
                }
            ]
        ),
        "service_order_completed": WhatsAppTemplate(
            name="service_order_completed",
            language="pt_BR",
            category="UTILITY",
            description="Notification when service order is completed",
            components=[
                {
                    "type": "BODY",
                    "text": "A ordem de serviço {service_order_number} foi concluída. Atividades realizadas: {activities}. Obrigado pela confiança!"
                }
            ]
        ),
        "sla_breach_warning": WhatsAppTemplate(
            name="sla_breach_warning",
            language="pt_BR",
            category="UTILITY",
            description="Warning when SLA is about to be breached",
            components=[
                {
                    "type": "BODY",
                    "text": "ATENÇÃO: O chamado #{ticket_number} está próximo do vencimento do SLA. Nossa equipe está trabalhando para resolver rapidamente."
                }
            ]
        )
    }
    
    @classmethod
    def get_template(cls, template_name: str) -> Optional[WhatsAppTemplate]:
        """Get a predefined template by name."""
        return cls.TEMPLATES.get(template_name)
    
    @classmethod
    def list_templates(cls) -> List[WhatsAppTemplate]:
        """List all available templates."""
        return list(cls.TEMPLATES.values())


class WhatsAppNotificationService:
    """
    High-level service for sending WhatsApp notifications based on business events.
    """
    
    def __init__(self, whatsapp_service: Optional[WhatsAppService] = None):
        self.whatsapp_service = whatsapp_service or WhatsAppService()
    
    async def notify_ticket_created(
        self,
        session: AsyncSession,
        phone_number: str,
        ticket_number: str,
        title: str,
        empresa_id: Optional[int] = None
    ) -> bool:
        """Send notification when a ticket is created."""
        try:
            await self.whatsapp_service.send_template_message(
                session=session,
                to=phone_number,
                template_name="ticket_created",
                parameters=[ticket_number, title],
                empresa_id=empresa_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send ticket created notification: {e}")
            return False
    
    async def notify_ticket_status_changed(
        self,
        session: AsyncSession,
        phone_number: str,
        ticket_number: str,
        new_status: str,
        empresa_id: Optional[int] = None
    ) -> bool:
        """Send notification when ticket status changes."""
        try:
            await self.whatsapp_service.send_template_message(
                session=session,
                to=phone_number,
                template_name="ticket_status_changed",
                parameters=[ticket_number, new_status],
                empresa_id=empresa_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send ticket status change notification: {e}")
            return False
    
    async def notify_service_order_completed(
        self,
        session: AsyncSession,
        phone_number: str,
        service_order_number: str,
        activities: str,
        empresa_id: Optional[int] = None
    ) -> bool:
        """Send notification when service order is completed."""
        try:
            await self.whatsapp_service.send_template_message(
                session=session,
                to=phone_number,
                template_name="service_order_completed",
                parameters=[service_order_number, activities],
                empresa_id=empresa_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send service order completion notification: {e}")
            return False
    
    async def notify_sla_breach_warning(
        self,
        session: AsyncSession,
        phone_number: str,
        ticket_number: str,
        empresa_id: Optional[int] = None
    ) -> bool:
        """Send warning when SLA is about to be breached."""
        try:
            await self.whatsapp_service.send_template_message(
                session=session,
                to=phone_number,
                template_name="sla_breach_warning",
                parameters=[ticket_number],
                empresa_id=empresa_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send SLA breach warning: {e}")
            return False
    
    async def send_custom_message(
        self,
        session: AsyncSession,
        phone_number: str,
        message: str,
        empresa_id: Optional[int] = None
    ) -> bool:
        """Send a custom text message."""
        try:
            await self.whatsapp_service.send_text_message(
                session=session,
                to=phone_number,
                text=message,
                empresa_id=empresa_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send custom WhatsApp message: {e}")
            return False


# Global instances
whatsapp_service = WhatsAppService()
whatsapp_notification_service = WhatsAppNotificationService(whatsapp_service)