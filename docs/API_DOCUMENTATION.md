# Sistema Boladão - API Documentation

## Overview

Sistema Boladão is a comprehensive multi-tenant helpdesk management system built with FastAPI. It provides complete asset management, ticket tracking, service order management, and external integrations with modern security and performance features.

## Table of Contents

1. [Authentication](#authentication)
2. [Core Concepts](#core-concepts)
3. [API Endpoints](#api-endpoints)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Security](#security)
7. [Examples](#examples)

## Authentication

### JWT Token Authentication

All API endpoints require authentication using JWT tokens. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Login Endpoint

**POST** `/auth/login`

```json
{
  "email": "user@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "nome": "User Name",
    "empresa": {
      "id": 1,
      "nome": "Company Name"
    }
  }
}
```

### Registration Endpoint

**POST** `/auth/register`

```json
{
  "nome": "User Name",
  "email": "user@example.com",
  "password": "secure-password",
  "empresa_nome": "Company Name"
}
```

## Core Concepts

### Multi-Tenancy

The system is multi-tenant, meaning each company (empresa) has isolated data. Users can only access data from their own company.

### Roles and Permissions

- **Admin**: Full system access
- **Agent**: Can manage tickets and service orders
- **Requester**: Can create and view own tickets
- **Viewer**: Read-only access

### Asset Lifecycle

1. **Inventory Intake**: Items are added to inventory
2. **Asset Creation**: Inventory items become trackable assets
3. **Ticket Creation**: Issues are reported against assets
4. **Service Orders**: Work is performed to resolve issues

## API Endpoints

### Health Check

**GET** `/health`

Returns system health status.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-10-22T12:00:00Z",
  "version": "1.0.0"
}
```

### Assets

#### List Assets

**GET** `/api/helpdesk/assets`

**Parameters:**
- `page` (int): Page number (default: 1)
- `limit` (int): Items per page (default: 20)
- `search` (string): Search in tag, description, or serial
- `status` (string): Filter by status
- `tipo` (string): Filter by asset type

**Response:**
```json
{
  "assets": [
    {
      "id": 1,
      "tag": "LAPTOP-001",
      "descricao": "Dell Laptop",
      "serial_text": "DL123456789",
      "status": {
        "id": 1,
        "nome": "Ativo"
      },
      "tipo": {
        "id": 1,
        "nome": "Computador"
      },
      "local_instalacao": {
        "id": 1,
        "nome": "Escritório"
      },
      "criado_em": "2025-10-22T10:00:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "total_pages": 3
}
```

### Tickets

#### Create Ticket

**POST** `/api/helpdesk/tickets`

```json
{
  "titulo": "Computer not starting",
  "descricao": "The laptop won't turn on after the weekend",
  "ativo_id": 1,
  "prioridade": "high",
  "categoria": "hardware"
}
```

**Response:**
```json
{
  "id": 1,
  "numero": "TKT-1-2025-001",
  "titulo": "Computer not starting",
  "descricao": "The laptop won't turn on after the weekend",
  "status": "new",
  "prioridade": "high",
  "categoria": "hardware",
  "ativo": {
    "id": 1,
    "tag": "LAPTOP-001",
    "descricao": "Dell Laptop"
  },
  "sla_info": {
    "response_time_hours": 4,
    "resolution_time_hours": 24,
    "time_remaining_hours": 23.5,
    "status": "ok"
  },
  "criado_em": "2025-10-22T12:00:00Z"
}
```

#### List Tickets

**GET** `/api/helpdesk/tickets`

**Parameters:**
- `page` (int): Page number
- `limit` (int): Items per page
- `status` (string): Filter by status
- `prioridade` (string): Filter by priority
- `agente_id` (int): Filter by assigned agent
- `search` (string): Search in title or description

#### Get Ticket Details

**GET** `/api/helpdesk/tickets/{id}`

**Response:**
```json
{
  "id": 1,
  "numero": "TKT-1-2025-001",
  "titulo": "Computer not starting",
  "descricao": "The laptop won't turn on after the weekend",
  "status": "in_progress",
  "prioridade": "high",
  "categoria": "hardware",
  "ativo": {
    "id": 1,
    "tag": "LAPTOP-001",
    "descricao": "Dell Laptop"
  },
  "agente": {
    "id": 2,
    "nome": "Agent Name"
  },
  "sla_info": {
    "response_time_hours": 4,
    "resolution_time_hours": 24,
    "time_remaining_hours": 20.5,
    "status": "ok"
  },
  "atividades": [
    {
      "id": 1,
      "descricao": "Ticket assigned to agent",
      "usuario": "System",
      "criado_em": "2025-10-22T12:30:00Z"
    }
  ],
  "next_actions": [
    "Check power adapter",
    "Test with different power outlet",
    "Contact hardware support if issue persists"
  ],
  "criado_em": "2025-10-22T12:00:00Z",
  "atualizado_em": "2025-10-22T12:30:00Z"
}
```

#### Update Ticket

**PUT** `/api/helpdesk/tickets/{id}`

```json
{
  "status": "resolved",
  "resolucao": "Replaced faulty power adapter",
  "agente_id": 2
}
```

### Service Orders

#### Create Service Order

**POST** `/api/helpdesk/service-orders`

```json
{
  "chamado_id": 1,
  "tipo_os": "maintenance",
  "atividades_realizadas": "Replaced power adapter and tested system",
  "observacao": "Customer satisfied with resolution",
  "tempo_estimado": 120
}
```

**Response:**
```json
{
  "id": 1,
  "numero_os": "OS-1-2025-001",
  "chamado_id": 1,
  "status": "draft",
  "tipo_os": "maintenance",
  "atividades_realizadas": "Replaced power adapter and tested system",
  "observacao": "Customer satisfied with resolution",
  "tempo_estimado": 120,
  "tempo_gasto": 0,
  "criado_em": "2025-10-22T13:00:00Z"
}
```

#### Add Activity to Service Order

**POST** `/api/helpdesk/service-orders/{id}/activities`

```json
{
  "descricao": "Diagnosed power issue",
  "tempo_gasto": 30,
  "tipo_atividade": "diagnostic"
}
```

#### Get Service Order Analytics

**GET** `/api/helpdesk/service-orders/analytics`

**Response:**
```json
{
  "total_service_orders": 150,
  "completed_orders": 120,
  "completion_rate": 80.0,
  "average_completion_time_hours": 4.5,
  "total_billable_hours": 600,
  "status_distribution": {
    "completed": 120,
    "in_progress": 20,
    "draft": 10
  },
  "monthly_trends": [
    {
      "month": "2025-10",
      "orders": 45,
      "completion_rate": 85.0
    }
  ]
}
```

### Inventory

#### Inventory Intake

**POST** `/api/helpdesk/inventory/intake`

```json
{
  "nome": "Dell Laptop",
  "modelo": "Latitude 5520",
  "quantidade": 5,
  "preco_unitario": 1200.00,
  "fornecedor": "Dell Inc",
  "create_asset": true,
  "asset_tag_prefix": "LAPTOP"
}
```

### Analytics

#### Get Ticket Analytics

**GET** `/api/helpdesk/analytics`

**Response:**
```json
{
  "total_tickets": 500,
  "open_tickets": 45,
  "resolved_tickets": 400,
  "sla_breaches": 5,
  "average_resolution_time_hours": 18.5,
  "status_distribution": {
    "new": 10,
    "open": 15,
    "in_progress": 20,
    "resolved": 400,
    "closed": 55
  },
  "priority_distribution": {
    "low": 200,
    "normal": 250,
    "high": 40,
    "urgent": 10
  },
  "escalation_recommendations": [
    {
      "ticket_id": 123,
      "reason": "SLA breach imminent",
      "action": "Escalate to senior agent"
    }
  ]
}
```

### Integrations

#### Publish Event

**POST** `/api/integrations/events/publish` (Admin only)

```json
{
  "event_type": "ticket.created",
  "aggregate_type": "ticket",
  "aggregate_id": "123",
  "payload": {
    "ticket_id": 123,
    "titulo": "New ticket",
    "prioridade": "high"
  },
  "metadata": {
    "source": "web_ui",
    "user_id": 1
  }
}
```

#### Send WhatsApp Message

**POST** `/api/integrations/whatsapp/send`

```json
{
  "phone_number": "+5511999999999",
  "message": "Your ticket #TKT-1-2025-001 has been resolved.",
  "template_name": "ticket_resolved",
  "template_parameters": ["TKT-1-2025-001"]
}
```

#### AI Analysis

**POST** `/api/integrations/ai/analyze`

```json
{
  "text": "My computer is very slow and keeps freezing",
  "analysis_type": "ticket_classification"
}
```

**Response:**
```json
{
  "result": {
    "classification": {
      "category": "performance",
      "priority": "normal",
      "confidence": 0.85,
      "suggested_tags": ["slow", "freezing", "performance"]
    },
    "sentiment": {
      "sentiment": "negative",
      "confidence": 0.75,
      "score": -0.3
    },
    "suggested_actions": [
      "Check system resources",
      "Run disk cleanup",
      "Check for malware"
    ]
  }
}
```

## Error Handling

### Standard Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "field": "email",
      "issue": "Invalid email format"
    }
  },
  "timestamp": "2025-10-22T12:00:00Z",
  "request_id": "req_123456789"
}
```

### Common Error Codes

- `AUTHENTICATION_REQUIRED` (401): Missing or invalid authentication
- `AUTHORIZATION_DENIED` (403): Insufficient permissions
- `RESOURCE_NOT_FOUND` (404): Requested resource doesn't exist
- `VALIDATION_ERROR` (422): Invalid input data
- `RATE_LIMIT_EXCEEDED` (429): Too many requests
- `INTERNAL_ERROR` (500): Server error

## Rate Limiting

### Rate Limit Headers

All responses include rate limiting headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

### Rate Limit Rules

- **Default**: 100 requests per minute
- **Authentication**: 5 requests per minute
- **API**: 1000 requests per hour
- **Upload**: 10 requests per 5 minutes

## Security

### HTTPS Required

All API calls must use HTTPS in production.

### Input Validation

All inputs are validated for:
- SQL injection patterns
- XSS attempts
- Path traversal attacks
- Malformed data

### IP Blocking

Suspicious IPs are automatically blocked after repeated violations.

### Audit Logging

All API calls are logged for security monitoring and compliance.

## Examples

### Complete Ticket Workflow

```python
import requests

# 1. Login
login_response = requests.post('https://api.example.com/auth/login', json={
    'email': 'agent@company.com',
    'password': 'secure-password'
})
token = login_response.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 2. Create ticket
ticket_response = requests.post('https://api.example.com/api/helpdesk/tickets', 
    headers=headers,
    json={
        'titulo': 'Printer not working',
        'descricao': 'Office printer shows error message',
        'ativo_id': 5,
        'prioridade': 'normal'
    }
)
ticket_id = ticket_response.json()['id']

# 3. Update ticket status
requests.put(f'https://api.example.com/api/helpdesk/tickets/{ticket_id}',
    headers=headers,
    json={
        'status': 'in_progress',
        'agente_id': 2
    }
)

# 4. Create service order
so_response = requests.post('https://api.example.com/api/helpdesk/service-orders',
    headers=headers,
    json={
        'chamado_id': ticket_id,
        'atividades_realizadas': 'Replaced toner cartridge',
        'tempo_estimado': 30
    }
)

# 5. Resolve ticket
requests.put(f'https://api.example.com/api/helpdesk/tickets/{ticket_id}',
    headers=headers,
    json={
        'status': 'resolved',
        'resolucao': 'Printer working normally after toner replacement'
    }
)
```

### Bulk Asset Import

```python
import requests

headers = {'Authorization': f'Bearer {token}'}

# Import multiple assets
assets = [
    {
        'nome': 'Dell Laptop',
        'modelo': 'Latitude 5520',
        'quantidade': 1,
        'preco_unitario': 1200.00,
        'create_asset': True,
        'asset_tag_prefix': 'LAPTOP'
    },
    {
        'nome': 'HP Printer',
        'modelo': 'LaserJet Pro',
        'quantidade': 1,
        'preco_unitario': 300.00,
        'create_asset': True,
        'asset_tag_prefix': 'PRINTER'
    }
]

for asset in assets:
    response = requests.post('https://api.example.com/api/helpdesk/inventory/intake',
        headers=headers,
        json=asset
    )
    print(f"Created asset: {response.json()['asset']['tag']}")
```

## Support

For technical support or questions about the API:

- Email: support@sistemaboladao.com
- Documentation: https://docs.sistemaboladao.com
- Status Page: https://status.sistemaboladao.com

## Changelog

### Version 1.0.0 (2025-10-22)
- Initial API release
- Complete helpdesk functionality
- Multi-tenant support
- Integration capabilities
- Security enhancements