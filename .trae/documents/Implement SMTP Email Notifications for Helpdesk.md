## Objectives
- Send email notifications for helpdesk events (create, status, assignment, pending customer, concluded) and SLA-related alerts.
- Use Python SMTP with HTML templates and config-driven toggles.

## Triggers & Recipients
- Ticket Created: requester, assigned agent.
- Status Changed: requester, agent; include comment.
- Assignment Changed: new agent; optional requester.
- Pending Customer: requester.
- Concluded: requester and agent.
- SLA Alerts (support team):
  - Ticket-level SLA state change to breach/warning:
    - Response breach (no initial response by deadline) → notify support team.
    - Resolution breach (not resolved by resolution deadline) → notify support team.
    - Escalation needed (past escalation deadline) → notify support team.
  - SLA Overrides updated (admin) → notify support team that policy changed.
- Recipients resolution:
  - Support team emails: config list (`NOTIFY_SLA_TEAM_EMAILS`).
  - Contacts’ emails via `Contato` linked to ticket fields.

## Email Content & Templates
- Templates under `app/web/templates/email/`:
  - Event: `ticket_created.html`, `ticket_status_changed.html`, `ticket_assigned.html`, `ticket_pending_customer.html`, `ticket_concluded.html`
  - SLA: `sla_breach_response.html`, `sla_breach_resolution.html`, `sla_escalation_needed.html`, `sla_overrides_updated.html`
- Variables: ticket number, title, description, status, priority, deadlines, breach type, agent/requester names, comment, links.
- Text fallback auto-generated.

## Delivery Pipeline
- `app/services/notification_email.py`
  - `EmailNotifier` methods for each event + SLA alerts.
  - `_send_email(to[], subject, html, text)` using `smtplib` (`SMTP_SSL` or `SMTP` + TLS).
  - Template render with Jinja2 (`Jinja2Templates`).
- Hook points:
  - Create: `TicketService.create_ticket(...)` → send created.
  - Update: `TicketService.update_ticket(...)` → inspect `changes` dict for status/assignment → send.
  - SLA ticket alerts: after update, compute SLA via `TicketWorkflowEngine.check_sla_breaches(...)` and compare to previous snapshot; if new breach/warning → send to support team.
    - Persist last-known SLA flags on ticket (optional minimal field), or infer in v1 by sending only on transitions to critical statuses (e.g., set when status changes to an at-risk state and if deadlines passed).
  - SLA overrides updated: in `app/api/helpdesk_admin.py` `PUT /admin/helpdesk/sla-overrides` → after commit, send `sla_overrides_updated` to support team.

## Configuration
- Extend `app/core/config.py`:
  - SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_USE_SSL`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`.
  - Global toggles: `NOTIFY_ENABLED`.
  - Per-event toggles: `NOTIFY_ON_CREATE`, `NOTIFY_ON_STATUS`, `NOTIFY_ON_ASSIGN`, `NOTIFY_ON_PENDING_CUSTOMER`, `NOTIFY_ON_CONCLUDED`.
  - SLA toggles: `NOTIFY_SLA_ENABLED`, `NOTIFY_SLA_ON_RESPONSE_BREACH`, `NOTIFY_SLA_ON_RESOLUTION_BREACH`, `NOTIFY_SLA_ON_ESCALATION`, `NOTIFY_SLA_ON_OVERRIDES_UPDATED`.
  - `NOTIFY_SLA_TEAM_EMAILS` (comma-separated list).

## Security & Reliability
- Mask credentials in logs; timeouts (connect 10s).
- Basic recipient email validation; skip invalid.
- Debounce SLA alerts (optional): ensure we don’t send the same breach repeatedly; v1: only on first detection in an update, phase 2: store flags per ticket.

## Admin Controls (Phase 2)
- Add toggles in `admin_helpdesk.html` for SLA alerts and team emails.
- New endpoint `PUT /admin/helpdesk/notifications` to save toggles per tenant.

## Testing & Verification
- Mock SMTP for unit tests of `EmailNotifier`.
- Integration: create/update tickets across timelines to simulate breaches; verify emails queued.
- Admin: update SLA overrides and confirm support team notification.

## Rollout Steps
1. Add config entries.
2. Implement `EmailNotifier` with template rendering and SMTP send.
3. Add event templates.
4. Wire create/update hooks in `TicketService` for events and SLA checks.
5. Wire SLA overrides hook in `helpdesk_admin` API.
6. Add logs and toggles; test with local SMTP.

## Future Enhancements
- Persist SLA alert flags on tickets to avoid duplicates.
- Scheduled background job to scan all tickets hourly for breaches.
- Per-user notification preferences; richer templates.