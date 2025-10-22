"""
Comprehensive tests for helpdesk API endpoints.
Tests tickets, assets, service orders, and inventory management.
"""

import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ticket import TicketService
from app.services.asset import AssetService
from app.services.ordem_servico import ServiceOrderService


@pytest.mark.integration
class TestTicketAPI:
    """Integration tests for ticket API endpoints."""
    
    async def test_create_ticket_success(self, client: AsyncClient, authenticated_user: dict, test_factory):
        """Test successful ticket creation."""
        # Create an asset first
        asset = await test_factory.create_ativo(
            session=authenticated_user["user"].contato.empresa_id,
            empresa_id=authenticated_user["user"].contato.empresa_id
        )
        
        response = await client.post("/api/helpdesk/tickets", 
            headers=authenticated_user["headers"],
            json={
                "titulo": "Test Ticket",
                "descricao": "Test ticket description",
                "ativo_id": asset.id,
                "prioridade": "normal"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["titulo"] == "Test Ticket"
        assert data["descricao"] == "Test ticket description"
        assert "numero" in data
    
    async def test_create_ticket_invalid_asset(self, client: AsyncClient, authenticated_user: dict):
        """Test ticket creation with invalid asset."""
        response = await client.post("/api/helpdesk/tickets",
            headers=authenticated_user["headers"],
            json={
                "titulo": "Test Ticket",
                "descricao": "Test ticket description",
                "ativo_id": 99999,  # Non-existent asset
                "prioridade": "normal"
            }
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    async def test_list_tickets_success(self, client: AsyncClient, authenticated_user: dict, test_factory):
        """Test listing tickets with pagination."""
        # Create some test tickets
        for i in range(3):
            await test_factory.create_chamado(
                session=authenticated_user["user"].contato.empresa_id,
                empresa_id=authenticated_user["user"].contato.empresa_id,
                titulo=f"Test Ticket {i+1}"
            )
        
        response = await client.get("/api/helpdesk/tickets",
            headers=authenticated_user["headers"],
            params={"limit": 10, "page": 1}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tickets" in data
        assert "total" in data
        assert "page" in data
        assert len(data["tickets"]) >= 3
    
    async def test_get_ticket_by_id_success(self, client: AsyncClient, authenticated_user: dict, test_factory):
        """Test getting ticket by ID."""
        # Create a test ticket
        ticket = await test_factory.create_chamado(
            session=authenticated_user["user"].contato.empresa_id,
            empresa_id=authenticated_user["user"].contato.empresa_id
        )
        
        response = await client.get(f"/api/helpdesk/tickets/{ticket.id}",
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == ticket.id
        assert data["titulo"] == ticket.titulo
    
    async def test_update_ticket_success(self, client: AsyncClient, authenticated_user: dict, test_factory):
        """Test updating ticket."""
        # Create a test ticket
        ticket = await test_factory.create_chamado(
            session=authenticated_user["user"].contato.empresa_id,
            empresa_id=authenticated_user["user"].contato.empresa_id
        )
        
        response = await client.put(f"/api/helpdesk/tickets/{ticket.id}",
            headers=authenticated_user["headers"],
            json={
                "titulo": "Updated Ticket Title",
                "descricao": "Updated description",
                "status": "in_progress"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["titulo"] == "Updated Ticket Title"
        assert data["descricao"] == "Updated description"
    
    async def test_ticket_analytics_success(self, client: AsyncClient, authenticated_user: dict):
        """Test ticket analytics endpoint."""
        response = await client.get("/api/helpdesk/analytics",
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_tickets" in data
        assert "sla_breaches" in data
        assert "status_distribution" in data


@pytest.mark.integration
class TestAssetAPI:
    """Integration tests for asset API endpoints."""
    
    async def test_list_assets_success(self, client: AsyncClient, authenticated_user: dict, test_factory):
        """Test listing assets."""
        # Create some test assets
        for i in range(3):
            await test_factory.create_ativo(
                session=authenticated_user["user"].contato.empresa_id,
                empresa_id=authenticated_user["user"].contato.empresa_id,
                tag=f"TEST-{i+1:03d}"
            )
        
        response = await client.get("/api/helpdesk/assets",
            headers=authenticated_user["headers"],
            params={"limit": 10, "page": 1}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "assets" in data
        assert "total" in data
        assert len(data["assets"]) >= 3
    
    async def test_list_assets_with_search(self, client: AsyncClient, authenticated_user: dict, test_factory):
        """Test listing assets with search filter."""
        # Create test assets
        await test_factory.create_ativo(
            session=authenticated_user["user"].contato.empresa_id,
            empresa_id=authenticated_user["user"].contato.empresa_id,
            tag="LAPTOP-001"
        )
        await test_factory.create_ativo(
            session=authenticated_user["user"].contato.empresa_id,
            empresa_id=authenticated_user["user"].contato.empresa_id,
            tag="DESKTOP-001"
        )
        
        response = await client.get("/api/helpdesk/assets",
            headers=authenticated_user["headers"],
            params={"search": "LAPTOP"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["assets"]) >= 1
        assert any("LAPTOP" in asset["tag"] for asset in data["assets"])


@pytest.mark.integration
class TestServiceOrderAPI:
    """Integration tests for service order API endpoints."""
    
    async def test_create_service_order_success(self, client: AsyncClient, authenticated_user: dict, test_factory):
        """Test successful service order creation."""
        # Create a test ticket
        ticket = await test_factory.create_chamado(
            session=authenticated_user["user"].contato.empresa_id,
            empresa_id=authenticated_user["user"].contato.empresa_id
        )
        
        response = await client.post("/api/helpdesk/service-orders",
            headers=authenticated_user["headers"],
            json={
                "chamado_id": ticket.id,
                "atividades_realizadas": "Test activities",
                "observacao": "Test observation"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["chamado_id"] == ticket.id
        assert data["atividades_realizadas"] == "Test activities"
        assert "numero_os" in data
    
    async def test_list_service_orders_success(self, client: AsyncClient, authenticated_user: dict):
        """Test listing service orders."""
        response = await client.get("/api/helpdesk/service-orders",
            headers=authenticated_user["headers"],
            params={"limit": 10, "page": 1}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "service_orders" in data
        assert "total" in data
        assert "page" in data
    
    async def test_service_order_analytics_success(self, client: AsyncClient, authenticated_user: dict):
        """Test service order analytics endpoint."""
        response = await client.get("/api/helpdesk/service-orders/analytics",
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_service_orders" in data
        assert "completion_rate" in data


@pytest.mark.integration
class TestInventoryAPI:
    """Integration tests for inventory API endpoints."""
    
    async def test_inventory_intake_success(self, client: AsyncClient, authenticated_user: dict):
        """Test inventory intake endpoint."""
        response = await client.post("/api/helpdesk/inventory/intake",
            headers=authenticated_user["headers"],
            json={
                "nome": "Test Item",
                "modelo": "Test Model",
                "quantidade": 5,
                "preco_unitario": 100.0,
                "create_asset": True
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "inventory_item" in data
        assert "asset" in data
        assert data["inventory_item"]["quantidade"] == 5


@pytest.mark.unit
class TestTicketService:
    """Unit tests for TicketService."""
    
    async def test_create_ticket_with_asset(self, db_session: AsyncSession, test_factory):
        """Test creating ticket with asset."""
        # Create test data
        empresa = await test_factory.create_empresa(db_session)
        asset = await test_factory.create_ativo(db_session, empresa.id)
        await db_session.commit()
        
        ticket_service = TicketService()
        
        ticket = await ticket_service.create_with_asset(
            session=db_session,
            empresa_id=empresa.id,
            ativo_id=asset.id,
            titulo="Test Ticket",
            descricao="Test description"
        )
        
        assert ticket is not None
        assert ticket.titulo == "Test Ticket"
        assert ticket.ativo_id == asset.id
        assert ticket.empresa_id == empresa.id
    
    async def test_ticket_number_generation(self, db_session: AsyncSession, test_factory):
        """Test ticket number generation."""
        empresa = await test_factory.create_empresa(db_session)
        await db_session.commit()
        
        ticket_service = TicketService()
        
        # Generate multiple ticket numbers
        numbers = []
        for _ in range(3):
            number = await ticket_service._gen_number(db_session, empresa.id)
            numbers.append(number)
        
        # All numbers should be unique
        assert len(set(numbers)) == 3
        
        # Numbers should follow expected format
        for number in numbers:
            assert number.startswith("TKT-")
            assert len(number) > 10


@pytest.mark.unit
class TestAssetService:
    """Unit tests for AssetService."""
    
    async def test_create_asset_from_inventory(self, db_session: AsyncSession, test_factory):
        """Test creating asset from inventory item."""
        empresa = await test_factory.create_empresa(db_session)
        await db_session.commit()
        
        asset_service = AssetService()
        
        asset = await asset_service.create_from_inventory(
            session=db_session,
            empresa_id=empresa.id,
            stock_unit_id=1,
            tag="TEST-001",
            descricao="Test Asset"
        )
        
        assert asset is not None
        assert asset.tag == "TEST-001"
        assert asset.empresa_id == empresa.id
        assert asset.stock_unit_id == 1


@pytest.mark.performance
class TestHelpdeskPerformance:
    """Performance tests for helpdesk endpoints."""
    
    async def test_ticket_list_performance(self, client: AsyncClient, authenticated_user: dict, performance_timer):
        """Test ticket listing performance."""
        performance_timer.start()
        response = await client.get("/api/helpdesk/tickets",
            headers=authenticated_user["headers"],
            params={"limit": 50}
        )
        performance_timer.stop()
        
        assert response.status_code == status.HTTP_200_OK
        assert performance_timer.duration < 1.0  # Should complete within 1 second
    
    async def test_asset_list_performance(self, client: AsyncClient, authenticated_user: dict, performance_timer):
        """Test asset listing performance."""
        performance_timer.start()
        response = await client.get("/api/helpdesk/assets",
            headers=authenticated_user["headers"],
            params={"limit": 50}
        )
        performance_timer.stop()
        
        assert response.status_code == status.HTTP_200_OK
        assert performance_timer.duration < 1.0  # Should complete within 1 second


@pytest.mark.security
class TestHelpdeskSecurity:
    """Security tests for helpdesk endpoints."""
    
    async def test_unauthorized_access(self, client: AsyncClient):
        """Test that endpoints require authentication."""
        endpoints = [
            "/api/helpdesk/tickets",
            "/api/helpdesk/assets",
            "/api/helpdesk/service-orders",
            "/api/helpdesk/analytics"
        ]
        
        for endpoint in endpoints:
            response = await client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_tenant_isolation(self, client: AsyncClient, authenticated_user: dict, admin_user: dict, test_factory):
        """Test that users can only access their own company's data."""
        # Create ticket for authenticated user's company
        ticket = await test_factory.create_chamado(
            session=authenticated_user["user"].contato.empresa_id,
            empresa_id=authenticated_user["user"].contato.empresa_id
        )
        
        # Admin user from different company should not see this ticket
        response = await client.get(f"/api/helpdesk/tickets/{ticket.id}",
            headers=admin_user["headers"]
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    async def test_sql_injection_protection(self, client: AsyncClient, authenticated_user: dict):
        """Test protection against SQL injection in search parameters."""
        response = await client.get("/api/helpdesk/tickets",
            headers=authenticated_user["headers"],
            params={"search": "'; DROP TABLE chamado; --"}
        )
        
        # Should return normal response, not crash
        assert response.status_code == status.HTTP_200_OK
    
    async def test_input_validation(self, client: AsyncClient, authenticated_user: dict):
        """Test input validation on ticket creation."""
        response = await client.post("/api/helpdesk/tickets",
            headers=authenticated_user["headers"],
            json={
                "titulo": "",  # Empty title
                "descricao": "x" * 10000,  # Very long description
                "ativo_id": "invalid",  # Invalid asset ID type
                "prioridade": "invalid_priority"  # Invalid priority
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY