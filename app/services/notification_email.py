import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Dict, Any, Optional
from fastapi.templating import Jinja2Templates
from app.core.config import get_settings

templates = Jinja2Templates(directory="app/web/templates")
settings = get_settings()

class EmailNotifier:
    def __init__(self) -> None:
        self.enabled = bool(settings.NOTIFY_ENABLED)
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT or (465 if settings.SMTP_USE_SSL else 587)
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.use_tls = bool(settings.SMTP_USE_TLS)
        self.use_ssl = bool(settings.SMTP_USE_SSL)
        self.from_email = settings.SMTP_FROM_EMAIL or (self.smtp_user or "no-reply@example.com")
        self.from_name = settings.SMTP_FROM_NAME or "Sistema Boladão"

    def _send_email(self, to: List[str], subject: str, html: str, text: Optional[str] = None) -> None:
        if not self.enabled or not self.smtp_host or not to:
            return
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = ", ".join([t for t in to if t and "@" in t])
        if not msg["To"]:
            return
        msg.set_content(text or "")
        msg.add_alternative(html, subtype="html")
        if self.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

    def _render(self, request_ctx: Dict[str, Any], template_name: str, context: Dict[str, Any]) -> str:
        # Simple render via Jinja2Templates, using a fake request
        class _Req: pass
        req = _Req()
        setattr(req, "headers", {})
        html = templates.get_template(f"email/{template_name}").render({"request": req, **context})
        return html

    def send_ticket_created(self, to: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_ON_CREATE: return
        html = self._render({}, "ticket_created.html", context)
        subject = f"[Chamado] Criado · {context.get('numero')}"
        self._send_email(to, subject, html, context.get("text_fallback"))

    def send_status_changed(self, to: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_ON_STATUS: return
        html = self._render({}, "ticket_status_changed.html", context)
        subject = f"[Chamado] Status: {context.get('old_status')} → {context.get('new_status')} · {context.get('numero')}"
        self._send_email(to, subject, html, context.get("text_fallback"))

    def send_assigned(self, to: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_ON_ASSIGN: return
        html = self._render({}, "ticket_assigned.html", context)
        subject = f"[Chamado] Atribuído · {context.get('numero')}"
        self._send_email(to, subject, html, context.get("text_fallback"))

    def send_pending_customer(self, to: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_ON_PENDING_CUSTOMER: return
        html = self._render({}, "ticket_pending_customer.html", context)
        subject = f"[Chamado] Aguardando Cliente · {context.get('numero')}"
        self._send_email(to, subject, html, context.get("text_fallback"))

    def send_concluded(self, to: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_ON_CONCLUDED: return
        html = self._render({}, "ticket_concluded.html", context)
        subject = f"[Chamado] Concluído · {context.get('numero')}"
        self._send_email(to, subject, html, context.get("text_fallback"))

    def send_sla_response_breach(self, to_team: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_SLA_ENABLED or not settings.NOTIFY_SLA_ON_RESPONSE_BREACH: return
        html = self._render({}, "sla_breach_response.html", context)
        subject = f"[SLA] Sem resposta no prazo · {context.get('numero')}"
        self._send_email(to_team, subject, html, context.get("text_fallback"))

    def send_sla_resolution_breach(self, to_team: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_SLA_ENABLED or not settings.NOTIFY_SLA_ON_RESOLUTION_BREACH: return
        html = self._render({}, "sla_breach_resolution.html", context)
        subject = f"[SLA] Não resolvido no prazo · {context.get('numero')}"
        self._send_email(to_team, subject, html, context.get("text_fallback"))

    def send_sla_escalation_needed(self, to_team: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_SLA_ENABLED or not settings.NOTIFY_SLA_ON_ESCALATION: return
        html = self._render({}, "sla_escalation_needed.html", context)
        subject = f"[SLA] Escalonamento necessário · {context.get('numero')}"
        self._send_email(to_team, subject, html, context.get("text_fallback"))

    def send_sla_overrides_updated(self, to_team: List[str], context: Dict[str, Any]) -> None:
        if not settings.NOTIFY_SLA_ENABLED or not settings.NOTIFY_SLA_ON_OVERRIDES_UPDATED: return
        html = self._render({}, "sla_overrides_updated.html", context)
        subject = "[SLA] Política atualizada"
        self._send_email(to_team, subject, html, context.get("text_fallback"))
