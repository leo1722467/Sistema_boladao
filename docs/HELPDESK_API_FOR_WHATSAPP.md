# Helpdesk API for WhatsApp Integration

## Overview
- Purpose: allow a WhatsApp system to open, update, comment and close helpdesk tickets.
- Base URL: `http://localhost:8081`
- Auth: JWT Bearer token in `Authorization` header or `access_token` cookie.
- Core endpoints live under `GET/POST/PUT /api/helpdesk/...`.

## Authentication
- Obtain tokens
  - `POST /auth/login` with user credentials returns `access_token`.
  - Alternatively OAuth2 password flow: `POST /auth/token`.
- Current user info
  - `GET /auth/me` returns basic user profile.
- Header
  - Include `Authorization: Bearer <ACCESS_TOKEN>` for all API calls.

## Status Model
- Recommended statuses used by this deployment:
  - `Aberto`, `Em Atendimento`, `Pendente Cliente`, `Incidente`, `Concluído`, `Atendimento pausado`
- Free transitions
  - Server accepts setting any status directly; no “ordered” workflow constraints.
- Use IDs rather than text
  - Prefer `status_id` for updates (stable across languages and naming).
  - Discover IDs via:
    - `GET /admin/StatusChamado/items` → full records
    - `GET /admin/Chamado/foreign-key-options/status_id` → `{id, display}` pairs

## Tickets: Endpoints
- Create ticket
  - `POST /api/helpdesk/tickets`
  - Body example:
    ```json
    {
      "titulo": "WhatsApp: problema no equipamento",
      "descricao": "Mensagem do cliente via WhatsApp",
      "prioridade_id": 2,
      "status_id": 1,
      "agente_contato_id": 1,
      "proprietario_contato_id": 10,
      "ativo_id": 456
    }
    ```
  - Response: `201` with `id`, `numero` and details
  - Requirements:
    - The asset (`ativo_id` or `serial_text`) must belong to the same tenant (empresa) as the authenticated user; otherwise returns 403 with `tenant_scope_error`
    - `titulo` is required, otherwise 400
    - If `prioridade_id` is omitted, textual `prioridade` is mapped when possible
  - Find the right asset:
    - `GET /api/helpdesk/assets?search=<text>` lists assets for your tenant; use `id` or `serial_text` from the results in the ticket payload
  - Example cURL:
    ```bash
    curl -X POST http://localhost:8081/api/helpdesk/tickets \
      -H "Authorization: Bearer <ACCESS_TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{
        "titulo": "Laptop not turning on",
        "descricao": "No lights or sounds",
        "prioridade": "normal",
        "origem": "web",
        "ativo_id": 123
      }'
    ```
  - Common errors:
    - 403: {"detail": "{'message': 'Asset does not belong to the current company', 'type': 'tenant_scope_error', 'ativo_id': <id>, 'empresa_id': <id>}"}
    - 400: {"detail": "Titulo é obrigatório"}

- List tickets
  - `GET /api/helpdesk/tickets?search=<text>&status_id=<id>&limit=50&offset=0`
  - Useful for locating by number or text: `search=123` matches number/title/description

- Get ticket details
  - `GET /api/helpdesk/tickets/{ticket_id}`
  - Returns normalized details, including `status_id`, textual `status`, comments history, SLA hints

- Update ticket (status, assignment, fields, comment)
  - `PUT /api/helpdesk/tickets/{ticket_id}`
  - Body fields (all optional):
    - `status_id`: integer
    - `prioridade_id`: integer
    - `categoria_id`: integer
    - `agente_contato_id`: integer
    - `titulo`, `descricao`: strings
    - `comment`: string (adds a comment to the ticket)
  - Response: updated ticket details

## Typical WhatsApp Flows
- Comment on a ticket
  - Use only `comment` to append a message:
    `PUT /api/helpdesk/tickets/789`
    ```json
    {
      "comment": "Cliente respondeu via WhatsApp: teste realizado."
    }
    ```

- Open or start attending
  - Set status to `Aberto` or `Em Atendimento` via IDs:
    `PUT /api/helpdesk/tickets/789`
    ```json
    {
      "status_id": <ID_EM_ATENDIMENTO>,
      "agente_contato_id": 1
    }
    ```
  - The server auto-assigns the agent when moving to “Em Atendimento” if none is set

- Pause attendance
  - `PUT /api/helpdesk/tickets/789`
    ```json
    {
      "status_id": <ID_ATENDIMENTO_PAUSADO>,
      "comment": "Aguardando peças conforme WhatsApp."
    }
    ```

- Mark as pending customer
  - `PUT /api/helpdesk/tickets/789`
    ```json
    {
      "status_id": <ID_PENDENTE_CLIENTE>,
      "comment": "Solicitamos retorno do cliente via WhatsApp."
    }
    ```

- Close or conclude
  - `PUT /api/helpdesk/tickets/789`
    ```json
    {
      "status_id": <ID_CONCLUIDO>,
      "comment": "Concluído conforme confirmação no WhatsApp."
    }
    ```

- Create from WhatsApp message
  - `POST /api/helpdesk/tickets`
    ```json
    {
      "titulo": "WhatsApp: Impressora não imprime",
      "descricao": "Mensagem do cliente: erro 0x01",
      "prioridade_id": 2,
      "status_id": <ID_ABERTO>,
      "agente_contato_id": 1,
      "proprietario_contato_id": 10
    }
    ```

## Discover Status IDs
- Quick options
  - `GET /admin/Chamado/foreign-key-options/status_id`
  - Response example:
    ```json
    [
      {"id": 1, "display": "Aberto"},
      {"id": 2, "display": "Em Atendimento"},
      {"id": 3, "display": "Pendente Cliente"},
      {"id": 4, "display": "Incidente"},
      {"id": 5, "display": "Concluído"},
      {"id": 6, "display": "Atendimento pausado"}
    ]
    ```
- Full records
  - `GET /admin/StatusChamado/items` for complete fields

## Errors
- `401 Unauthorized`
  - Login required or token expired; refresh token or re-login.
  - Web pages redirect to `/`; APIs return JSON 401.
- `403 Forbidden`
  - User lacks permission for the operation.
- `404 Not Found`
  - Ticket ID does not exist.
- `400 Bad Request`
  - Invalid field or payload.

## Security Notes
- Always send `Authorization: Bearer <ACCESS_TOKEN>`.
- Prefer HTTPS in production.
- Do not store tokens in plaintext; rotate if leaked.

## WhatsApp Side Integration Code (Node.js)

### Setup

```json
{
  "name": "whatsapp-helpdesk-integration",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "axios": "^1.6.7",
    "express": "^4.18.2"
  }
}
```

### Client Library

```js
import axios from 'axios'

class HelpdeskClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl
    this.accessToken = null
    this.statusCache = null
  }
  async login(email, password) {
    const r = await axios.post(`${this.baseUrl}/auth/login`, { email, password })
    this.accessToken = r.data?.access_token || null
    return this.accessToken
  }
  headers() {
    const h = { 'Content-Type': 'application/json' }
    if (this.accessToken) h['Authorization'] = `Bearer ${this.accessToken}`
    return h
  }
  async getStatusId(label) {
    if (!this.statusCache) {
      const r = await axios.get(`${this.baseUrl}/admin/Chamado/foreign-key-options/status_id`, { headers: this.headers(), withCredentials: true })
      this.statusCache = r.data || []
    }
    const norm = s => String(s || '').trim().toLowerCase()
    const target = norm(label)
    const found = this.statusCache.find(o => norm(o.display || o.nome || o.label) === target)
    return found ? Number(found.id) : null
  }
  async createTicket(payload) {
    const r = await axios.post(`${this.baseUrl}/api/helpdesk/tickets`, payload, { headers: this.headers(), withCredentials: true })
    return r.data
  }
  async getTicket(ticketId) {
    const r = await axios.get(`${this.baseUrl}/api/helpdesk/tickets/${ticketId}`, { headers: this.headers(), withCredentials: true })
    return r.data
  }
  async updateTicket(ticketId, payload) {
    const r = await axios.put(`${this.baseUrl}/api/helpdesk/tickets/${ticketId}`, payload, { headers: this.headers(), withCredentials: true })
    return r.data
  }
  async addComment(ticketId, comment) {
    return this.updateTicket(ticketId, { comment })
  }
  async setStatus(ticketId, statusLabel) {
    const id = await this.getStatusId(statusLabel)
    const payload = id ? { status_id: id } : {}
    return this.updateTicket(ticketId, payload)
  }
}

export default HelpdeskClient
```

### WhatsApp Event Handlers

```js
import express from 'express'
import HelpdeskClient from './helpdesk-client.js'

const app = express()
app.use(express.json())

const HELP_URL = process.env.HELPDESK_URL || 'http://localhost:8081'
const HELP_USER = process.env.HELPDESK_EMAIL || 'agent@example.com'
const HELP_PASS = process.env.HELPDESK_PASSWORD || 'password123'

const client = new HelpdeskClient(HELP_URL)

async function ensureAuth() {
  if (!client.accessToken) await client.login(HELP_USER, HELP_PASS)
}

app.post('/whatsapp/message', async (req, res) => {
  try {
    await ensureAuth()
    const { type, ticketId, text, numero, prioridade_id, agente_contato_id, proprietario_contato_id } = req.body || {}
    if (type === 'ticket.create') {
      const payload = {
        titulo: text?.slice(0, 200) || 'WhatsApp',
        descricao: text || '',
        prioridade_id: prioridade_id || null,
        status_id: await client.getStatusId('Aberto'),
        agente_contato_id: agente_contato_id || null,
        proprietario_contato_id: proprietario_contato_id || null
      }
      const created = await client.createTicket(payload)
      res.json({ ok: true, ticket: created })
      return
    }
    if (type === 'ticket.comment') {
      const result = await client.addComment(Number(ticketId), text || '')
      res.json({ ok: true, ticket: result })
      return
    }
    if (type === 'ticket.status') {
      const label = String(text || '').trim()
      const result = await client.setStatus(Number(ticketId), label)
      res.json({ ok: true, ticket: result })
      return
    }
    if (type === 'ticket.close') {
      const result = await client.setStatus(Number(ticketId), 'Concluído')
      res.json({ ok: true, ticket: result })
      return
    }
    res.status(400).json({ ok: false, detail: 'unsupported_type' })
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e?.message || e) })
  }
})

const PORT = process.env.PORT || 9000
app.listen(PORT, () => {})
```

### Example Mappings

```js
const statusMap = {
  aberto: 'Aberto',
  em_atendimento: 'Em Atendimento',
  pendente_cliente: 'Pendente Cliente',
  incidente: 'Incidente',
  concluido: 'Concluído',
  pausado: 'Atendimento pausado'
}
```

### Usage Examples

```bash
curl -X POST http://localhost:9000/whatsapp/message \
  -H "Content-Type: application/json" \
  -d '{"type":"ticket.create","text":"Cliente: impressora com erro","prioridade_id":2,"agente_contato_id":1,"proprietario_contato_id":10}'
```

```bash
curl -X POST http://localhost:9000/whatsapp/message \
  -H "Content-Type: application/json" \
  -d '{"type":"ticket.comment","ticketId":789,"text":"Cliente: teste realizado"}'
```

```bash
curl -X POST http://localhost:9000/whatsapp/message \
  -H "Content-Type: application/json" \
  -d '{"type":"ticket.status","ticketId":789,"text":"Em Atendimento"}'
```
