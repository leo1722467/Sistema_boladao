# Ticket Management Functions Guide

## Overview
- Core UI files: `app/web/templates/tickets.html`, `app/web/templates/ticket_edit.html`, `app/web/templates/ticket_create.html`
- Core API: `app/api/helpdesk.py`
- Service layer: `app/services/ticket.py`
- Workflow and validation: `app/core/ticket_workflow.py`
- Auth/redirect and middleware: `app/main.py`, `app/core/middleware.py`

## UI Actions on Tickets List
- `assignToMe(id)` 
  - File: `app/web/templates/tickets.html:980`
  - Called from row action button “Atribuir para mim”, sets current user as agent and adds comment.
  - Behavior: `PUT /api/helpdesk/tickets/{id}` with `agente_contato_id` and `comment`, then refreshes list.
  - Important: Uses `getMe()` to resolve current contact ID; handles failure with alert.

- `changeStatus(id, status)`
  - File: `app/web/templates/tickets.html:995`
  - Called from row action buttons like “Em Andamento”, “Aguardando Cliente”.
  - Behavior:
    - Fetches current status via `GET /api/helpdesk/tickets/{id}` (authorization via `apiHeaders()`).
    - If current is `new` and target is not `open`, performs transition to `open` first (`PUT`).
    - Requires `prompt` comment for `pending_customer` and `resolved`.
    - Sends `PUT /api/helpdesk/tickets/{id}` with `{ status, comment? }`.
    - Refreshes the list with `loadTickets(currentPage)`.
  - References: `app/web/templates/tickets.html:1020–1044` (open-first handling, payload build, error handling).

- `resolveTicket(e, id)`
  - File: `app/web/templates/tickets.html:1046`
  - Called from row action button “Resolver” (`onclick="resolveTicket(event, ${ticket.id})"` at `app/web/templates/tickets.html:514`).
  - Behavior:
    - Non-blocking: defers to the next tick (`setTimeout`) and disables the button to avoid duplicates.
    - Requires resolution comment via `prompt`.
    - If current status is `new`, first moves to `open` (`PUT`).
    - Transitions to `resolved` with `comment` (`PUT`), then transitions to `closed` (`PUT`).
    - On `401`, redirects to `/` immediately; on success, refreshes tickets.
  - References: `app/web/templates/tickets.html:1053–1087`.

- Row action buttons and table rendering
  - Buttons for view, edit, workflow, assign, in-progress, pending-customer, resolve created in `renderTicketsTable`.
  - References:
    - Button markup: `app/web/templates/tickets.html:496–516`
    - Table and rows: `app/web/templates/tickets.html:448–520`, sections rendering and `innerHTML` update: `app/web/templates/tickets.html:522–587`

- `loadTickets`, stats, filters
  - Fetches tickets list with filters and updates UI.
  - References: `app/web/templates/tickets.html:376–427`

## UI Actions on Ticket Edit
- `saveTicket` (Update Ticket)
  - File: `app/web/templates/ticket_edit.html:240–266`
  - Called by Save button in edit page; builds `UpdateTicketRequest` payload including `status/status_id`, `prioridade_id`, `agente_contato_id`, `categoria_id`, and an optional `comment`.
  - Behavior:
    - Requires comment for certain transitions (UI enforces with `requiresComment` checks).
    - Sends `PUT /api/helpdesk/tickets/{ticketId}`; redirects to `/tickets` after success.
    - On `401` during load, redirects to `/`.
  - References:
    - Load and auth checks: `app/web/templates/ticket_edit.html:115–137`
    - Save flow: `app/web/templates/ticket_edit.html:255–266`

## UI Actions on Ticket Create
- `submitTicket` (Create Ticket)
  - File: `app/web/templates/ticket_create.html:232–268`
  - Called by Create button; composes payload (title, description, priority, status, agent, owner, asset).
  - Behavior: `POST /api/helpdesk/tickets` and displays result; logs fetch errors with detailed payload.
  - References: options loading and auth: `app/web/templates/ticket_create.html:156–220`

## API Endpoints
- `GET /api/helpdesk/tickets`
  - File: `app/api/helpdesk.py:305`
  - Returns a paginated list with normalized textual `status` and `priority` for UI, plus IDs. Supports filters and access permissions.
  - Response building references: `app/api/helpdesk.py:780–815` (status/priority normalization and comment history).

- `GET /api/helpdesk/tickets/{ticket_id}`
  - File: `app/api/helpdesk.py:452`
  - Returns detailed ticket info; enforces role-based permissions.

- `PUT /api/helpdesk/tickets/{ticket_id}` (Update)
  - File: `app/api/helpdesk.py:550–617`
  - Accepts `UpdateTicketRequest`:
    - Textual `status` and `priority` mapped to IDs for flexibility (PT/EN).
    - Requesters can only add `comment`; attendants/admins can change fields.
  - Commits and returns updated `TicketDetailResponse`.
  - References:
    - Textual mapping: `app/api/helpdesk.py:581–596`
    - Response building after update: `app/api/helpdesk.py:626–636`

## Service Layer (Business Logic)
- `TicketService.update_ticket(...)`
  - File: `app/services/ticket.py:224`
  - Responsibilities:
    - Loads ticket by tenant, validates changes.
    - Status transitions validated via `TicketWorkflowEngine` (`_validate_status_transition`).
    - Special case: `new -> pending_customer` is blocked; moves `new -> open` first (business rule).
    - Auto-assign agent on transition to `in_progress` if none and role is `admin/agent`.
    - Adds `ChamadoComentario` when `comment` provided and may auto-progress from `new/open` to `in_progress`.
    - Logs updates via `ChamadoLog`.
  - References:
    - NEW to PENDING_CUSTOMER rule and OPEN pass-through: `app/services/ticket.py:248–307`
    - Auto-assign on IN_PROGRESS: `app/services/ticket.py:302–307`, fallbacks at `app/services/ticket.py:343–350`
    - Comment handling and auto-progress: `app/services/ticket.py:369–387`
    - Logging: `app/services/ticket.py:395–408`, `app/services/ticket.py:812–827`

- Ticket creation, routing and counters
  - File: `app/services/ticket.py:120–182` (create flow)
  - Auto-routing rules may assign agent: `app/services/ticket.py:719–729`
  - Ticket number and counters: `app/services/ticket.py:1–68`, `app/services/ticket.py:147–182`

## Workflow and Validation
- `TicketWorkflowEngine`
  - File: `app/core/ticket_workflow.py:1`
  - Defines valid transitions with role and comment requirements:
    - From OPEN/IN_PROGRESS to `resolved` requires a comment.
    - From `resolved` to `closed` allowed for agent/admin.
    - Reopens from `resolved/closed` to `open` allowed.
  - Key methods:
    - `get_valid_transitions`: `app/core/ticket_workflow.py:118–130`
    - `validate_transition`: `app/core/ticket_workflow.py:132–184`
    - SLA tracking: `app/core/ticket_workflow.py:212–254`
    - Next actions suggestions: `app/core/ticket_workflow.py:289–369`

## Authentication and Redirect Behavior
- UI header composition:
  - `apiHeaders()` reads `access_token` from cookie and sets `Authorization` header if present.
  - References: `app/web/templates/tickets.html:965–971`, `app/web/templates/ticket_edit.html:83–101`
- Redirects on 401:
  - In list and handlers, 401 triggers `window.location.href = '/'`.
  - References:
    - Tickets list load: `app/web/templates/tickets.html:276–281`
    - Edit page: `app/web/templates/ticket_edit.html:124–136`
    - Resolve flow: `app/web/templates/tickets.html:1058, 1069, 1077, 1079`
- Middleware and exception handler:
  - Middleware treats web paths as redirect and API paths as JSON 401: `app/core/middleware.py:69–75`
  - Global HTTP 401 redirect for non-API paths: `app/main.py:198` (redirects `/` for web pages)
  - Protected path configuration: `app/main.py:117–123`

## Status Names and Mapping
- UI uses textual `status` values: `"new"`, `"open"`, `"in_progress"`, `"pending_customer"`, `"resolved"`, `"closed"`
- API maps textual inputs to IDs and normalizes PT/EN:
  - Normalization and mapping: `app/api/helpdesk.py:755–778`, `app/api/helpdesk.py:781–793`
  - Service-level mapping for status lookups: `app/services/ticket.py:626–656`

## Typical Flows
- Open a ticket (NEW -> OPEN):
  - UI: `changeStatus(id, 'open')` or auto on activity comments.
  - Server: Validated by workflow engine; may auto-assign agent in `in_progress`.
- Move to In Progress:
  - UI: `changeStatus(id, 'in_progress')`
  - Server: Auto-assign agent if none; logs update.
- Pending Customer:
  - UI: `changeStatus(id, 'pending_customer')` requires comment.
  - Server: Validates comment requirement; logs.
- Resolve and Close:
  - UI: `resolveTicket(event, id)` requires comment; transitions to `resolved` then `closed`.
  - Server: Transition validation; logs; SLA resolution updated.

## Buttons and Where They’re Called
- Row action buttons:
  - `Visualizar`: `viewTicket(${ticket.id})` — navigation, defined elsewhere.
  - `Editar`: `editTicket(${ticket.id})`
  - `Workflow`: `showWorkflow(${ticket.id})`
  - `Atribuir para mim`: `assignToMe(${ticket.id})` — `app/web/templates/tickets.html:505–507`
  - `Em Andamento`: `changeStatus(${ticket.id}, 'in_progress')` — `app/web/templates/tickets.html:508–510`
  - `Aguardando Cliente`: `changeStatus(${ticket.id}, 'pending_customer')` — `app/web/templates/tickets.html:511–513`
  - `Resolver`: `resolveTicket(event, ${ticket.id})` — `app/web/templates/tickets.html:514–516`

## Notes
- Comment requirements enforced both client-side (prompt) and server-side (workflow validation).
- Some transitions are multi-step (e.g., NEW requires OPEN before other statuses).
- Requesters have limited abilities: typically only adding comments; attendants/admins perform status changes.
- SLA indicators and next actions are derived in server responses for UI guidance.
