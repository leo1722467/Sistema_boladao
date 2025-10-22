"""
Test configuration and fixtures for the Sistema Boladão test suite.
Provides database setup, authentication, and common test utilities.
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.services.auth import AuthService
from app.repositories.user_auth import UserAuthRepository
from app.repositories.contato import ContatoRepository
from app.core.config import get_settings

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)

# Create test session maker
TestSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    class_=AsyncSession
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database session override."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user_data():
    """Test user data for authentication tests."""
    return {
        "nome": "Test User",
        "email": "test@example.com",
        "password": "test123456",
        "empresa_nome": "Test Company"
    }


@pytest_asyncio.fixture
async def authenticated_user(db_session: AsyncSession, test_user_data: dict):
    """Create an authenticated test user."""
    auth_service = AuthService()
    
    # Create user
    user_auth = await auth_service.register(
        session=db_session,
        nome=test_user_data["nome"],
        email=test_user_data["email"],
        password=test_user_data["password"],
        empresa_nome=test_user_data["empresa_nome"]
    )
    
    await db_session.commit()
    
    # Generate token
    access_token, _, _ = await auth_service.authenticate(
        session=db_session,
        email=test_user_data["email"],
        password=test_user_data["password"]
    )
    
    return {
        "user": user_auth,
        "token": access_token,
        "headers": {"Authorization": f"Bearer {access_token}"}
    }


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """Create an admin test user."""
    auth_service = AuthService()
    
    # Create admin user
    user_auth = await auth_service.register(
        session=db_session,
        nome="Admin User",
        email="admin@example.com",
        password="admin123456",
        empresa_nome="Admin Company"
    )
    
    await db_session.commit()
    
    # Generate token
    access_token, _, _ = await auth_service.authenticate(
        session=db_session,
        email="admin@example.com",
        password="admin123456"
    )
    
    return {
        "user": user_auth,
        "token": access_token,
        "headers": {"Authorization": f"Bearer {access_token}"}
    }


@pytest.fixture
def sample_asset_data():
    """Sample asset data for testing."""
    return {
        "tag": "TEST-001",
        "descricao": "Test Asset Description",
        "tipo_ativo_id": 1,
        "status_ativo_id": 1,
        "interno": True
    }


@pytest.fixture
def sample_ticket_data():
    """Sample ticket data for testing."""
    return {
        "titulo": "Test Ticket",
        "descricao": "Test ticket description",
        "prioridade_id": 1,
        "categoria_id": 1,
        "ativo_id": 1
    }


@pytest.fixture
def sample_service_order_data():
    """Sample service order data for testing."""
    return {
        "chamado_id": 1,
        "tipo_os_id": 1,
        "atividades_realizadas": "Test activities",
        "observacao": "Test observation"
    }


@pytest.fixture
def sample_inventory_data():
    """Sample inventory data for testing."""
    return {
        "catalogo_peca_id": 1,
        "quantidade": 10,
        "preco_unitario": 100.0,
        "observacao": "Test inventory item"
    }


class TestDataFactory:
    """Factory class for creating test data."""
    
    @staticmethod
    async def create_empresa(session: AsyncSession, nome: str = "Test Company"):
        """Create a test company."""
        from app.db.models import Empresa
        
        empresa = Empresa(nome=nome)
        session.add(empresa)
        await session.flush()
        return empresa
    
    @staticmethod
    async def create_contato(session: AsyncSession, empresa_id: int, nome: str = "Test Contact"):
        """Create a test contact."""
        from app.db.models import Contato
        
        contato = Contato(nome=nome, empresa_id=empresa_id)
        session.add(contato)
        await session.flush()
        return contato
    
    @staticmethod
    async def create_ativo(session: AsyncSession, empresa_id: int, tag: str = "TEST-001"):
        """Create a test asset."""
        from app.db.models import Ativo
        from app.services.serial import SerialService
        
        serial_service = SerialService()
        serial = await serial_service.generate_serial(session, empresa_id)
        
        ativo = Ativo(
            empresa_id=empresa_id,
            tag=tag,
            descricao="Test Asset",
            serial_text=serial
        )
        session.add(ativo)
        await session.flush()
        return ativo
    
    @staticmethod
    async def create_chamado(session: AsyncSession, empresa_id: int, titulo: str = "Test Ticket"):
        """Create a test ticket."""
        from app.db.models import Chamado
        from app.services.ticket import TicketService
        
        ticket_service = TicketService()
        numero = await ticket_service._gen_number(session, empresa_id)
        
        chamado = Chamado(
            numero=numero,
            empresa_id=empresa_id,
            titulo=titulo,
            descricao="Test ticket description"
        )
        session.add(chamado)
        await session.flush()
        return chamado


@pytest.fixture
def test_factory():
    """Provide access to test data factory."""
    return TestDataFactory


# Performance testing utilities
class PerformanceTimer:
    """Utility class for measuring performance in tests."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        import time
        self.start_time = time.time()
    
    def stop(self):
        import time
        self.end_time = time.time()
    
    @property
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


@pytest.fixture
def performance_timer():
    """Provide performance timer for tests."""
    return PerformanceTimer()


# Mock data for external integrations
@pytest.fixture
def mock_whatsapp_response():
    """Mock WhatsApp API response."""
    return {
        "messaging_product": "whatsapp",
        "contacts": [{"input": "+5511999999999", "wa_id": "5511999999999"}],
        "messages": [{"id": "wamid.test123"}]
    }


@pytest.fixture
def mock_ai_response():
    """Mock AI gateway response."""
    return {
        "classification": {
            "category": "hardware",
            "priority": "high",
            "confidence": 0.85
        },
        "sentiment": {
            "sentiment": "negative",
            "confidence": 0.75,
            "score": -0.3
        }
    }


# Database utilities
async def cleanup_database(session: AsyncSession):
    """Clean up database after tests."""
    # Delete all data in reverse order of dependencies
    from app.db.models import (
        ChamadoLog, ChamadoComentario, OrdemServico, Chamado,
        Ativo, Estoque, UserAuth, Contato, Empresa
    )
    
    for model in [ChamadoLog, ChamadoComentario, OrdemServico, Chamado, 
                  Ativo, Estoque, UserAuth, Contato, Empresa]:
        await session.execute(f"DELETE FROM {model.__tablename__}")
    
    await session.commit()


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
pytest.mark.security = pytest.mark.security