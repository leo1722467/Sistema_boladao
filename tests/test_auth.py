"""
Comprehensive tests for authentication system.
Tests registration, login, token validation, and security measures.
"""

import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthService
from app.core.exceptions import ValidationError, NotFoundError


@pytest.mark.unit
class TestAuthService:
    """Unit tests for AuthService."""
    
    async def test_register_user_success(self, db_session: AsyncSession):
        """Test successful user registration."""
        auth_service = AuthService()
        
        user_auth = await auth_service.register(
            session=db_session,
            nome="Test User",
            email="test@example.com",
            password="test123456",
            empresa_nome="Test Company"
        )
        
        assert user_auth is not None
        assert user_auth.contato.nome == "Test User"
        assert user_auth.contato.email == "test@example.com"
        assert user_auth.contato.empresa.nome == "Test Company"
    
    async def test_register_duplicate_email(self, db_session: AsyncSession):
        """Test registration with duplicate email."""
        auth_service = AuthService()
        
        # First registration
        await auth_service.register(
            session=db_session,
            nome="User 1",
            email="test@example.com",
            password="test123456",
            empresa_nome="Company 1"
        )
        await db_session.commit()
        
        # Second registration with same email should fail
        with pytest.raises(ValidationError):
            await auth_service.register(
                session=db_session,
                nome="User 2",
                email="test@example.com",
                password="test123456",
                empresa_nome="Company 2"
            )
    
    async def test_authenticate_success(self, db_session: AsyncSession):
        """Test successful authentication."""
        auth_service = AuthService()
        
        # Register user
        await auth_service.register(
            session=db_session,
            nome="Test User",
            email="test@example.com",
            password="test123456",
            empresa_nome="Test Company"
        )
        await db_session.commit()
        
        # Authenticate
        access_token, refresh_token, user_auth = await auth_service.authenticate(
            session=db_session,
            email="test@example.com",
            password="test123456"
        )
        
        assert access_token is not None
        assert refresh_token is not None
        assert user_auth is not None
        assert user_auth.contato.email == "test@example.com"
    
    async def test_authenticate_invalid_email(self, db_session: AsyncSession):
        """Test authentication with invalid email."""
        auth_service = AuthService()
        
        with pytest.raises(NotFoundError):
            await auth_service.authenticate(
                session=db_session,
                email="nonexistent@example.com",
                password="test123456"
            )
    
    async def test_authenticate_invalid_password(self, db_session: AsyncSession):
        """Test authentication with invalid password."""
        auth_service = AuthService()
        
        # Register user
        await auth_service.register(
            session=db_session,
            nome="Test User",
            email="test@example.com",
            password="test123456",
            empresa_nome="Test Company"
        )
        await db_session.commit()
        
        # Authenticate with wrong password
        with pytest.raises(ValidationError):
            await auth_service.authenticate(
                session=db_session,
                email="test@example.com",
                password="wrongpassword"
            )
    
    async def test_validate_token_success(self, db_session: AsyncSession):
        """Test successful token validation."""
        auth_service = AuthService()
        
        # Register and authenticate user
        await auth_service.register(
            session=db_session,
            nome="Test User",
            email="test@example.com",
            password="test123456",
            empresa_nome="Test Company"
        )
        await db_session.commit()
        
        access_token, _, _ = await auth_service.authenticate(
            session=db_session,
            email="test@example.com",
            password="test123456"
        )
        
        # Validate token
        user_auth = await auth_service.validate_token(session=db_session, token=access_token)
        
        assert user_auth is not None
        assert user_auth.contato.email == "test@example.com"
    
    async def test_validate_invalid_token(self, db_session: AsyncSession):
        """Test validation of invalid token."""
        auth_service = AuthService()
        
        with pytest.raises(ValidationError):
            await auth_service.validate_token(
                session=db_session,
                token="invalid.token.here"
            )


@pytest.mark.integration
class TestAuthAPI:
    """Integration tests for authentication API endpoints."""
    
    async def test_register_endpoint_success(self, client: AsyncClient):
        """Test successful registration via API."""
        response = await client.post("/auth/register", json={
            "nome": "Test User",
            "email": "test@example.com",
            "password": "test123456",
            "empresa_nome": "Test Company"
        })
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
    
    async def test_register_endpoint_invalid_data(self, client: AsyncClient):
        """Test registration with invalid data."""
        response = await client.post("/auth/register", json={
            "nome": "",  # Empty name
            "email": "invalid-email",  # Invalid email
            "password": "123",  # Too short password
            "empresa_nome": ""  # Empty company name
        })
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    async def test_login_endpoint_success(self, client: AsyncClient):
        """Test successful login via API."""
        # First register a user
        await client.post("/auth/register", json={
            "nome": "Test User",
            "email": "test@example.com",
            "password": "test123456",
            "empresa_nome": "Test Company"
        })
        
        # Then login
        response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "test123456"
        })
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "user" in data
    
    async def test_login_endpoint_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_me_endpoint_success(self, client: AsyncClient, authenticated_user: dict):
        """Test /auth/me endpoint with valid token."""
        response = await client.get("/auth/me", headers=authenticated_user["headers"])
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
    
    async def test_me_endpoint_no_token(self, client: AsyncClient):
        """Test /auth/me endpoint without token."""
        response = await client.get("/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_me_endpoint_invalid_token(self, client: AsyncClient):
        """Test /auth/me endpoint with invalid token."""
        response = await client.get("/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.security
class TestAuthSecurity:
    """Security tests for authentication system."""
    
    async def test_password_hashing(self, db_session: AsyncSession):
        """Test that passwords are properly hashed."""
        auth_service = AuthService()
        
        user_auth = await auth_service.register(
            session=db_session,
            nome="Test User",
            email="test@example.com",
            password="test123456",
            empresa_nome="Test Company"
        )
        
        # Password should be hashed, not stored in plain text
        assert user_auth.hashed_senha != "test123456"
        assert len(user_auth.hashed_senha) > 50  # bcrypt hashes are long
        assert user_auth.hashed_senha.startswith("$2b$")  # bcrypt prefix
    
    async def test_token_expiration(self, db_session: AsyncSession):
        """Test that tokens have proper expiration."""
        auth_service = AuthService()
        
        # Register user
        await auth_service.register(
            session=db_session,
            nome="Test User",
            email="test@example.com",
            password="test123456",
            empresa_nome="Test Company"
        )
        await db_session.commit()
        
        # Get token
        access_token, _, _ = await auth_service.authenticate(
            session=db_session,
            email="test@example.com",
            password="test123456"
        )
        
        # Decode token to check expiration
        import jwt
        from app.core.config import get_settings
        
        settings = get_settings()
        decoded = jwt.decode(access_token, settings.SECRET_KEY, algorithms=["HS256"])
        
        assert "exp" in decoded
        assert "sub" in decoded
        assert decoded["sub"] == "test@example.com"
    
    async def test_sql_injection_protection(self, client: AsyncClient):
        """Test protection against SQL injection in login."""
        response = await client.post("/auth/login", json={
            "email": "'; DROP TABLE user_auth; --",
            "password": "test123456"
        })
        
        # Should return 401, not crash the application
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_rate_limiting_simulation(self, client: AsyncClient):
        """Test multiple failed login attempts."""
        # Simulate multiple failed login attempts
        for _ in range(5):
            response = await client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Application should still be responsive
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.performance
class TestAuthPerformance:
    """Performance tests for authentication system."""
    
    async def test_login_performance(self, client: AsyncClient, performance_timer):
        """Test login endpoint performance."""
        # Register user first
        await client.post("/auth/register", json={
            "nome": "Test User",
            "email": "test@example.com",
            "password": "test123456",
            "empresa_nome": "Test Company"
        })
        
        # Measure login performance
        performance_timer.start()
        response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "test123456"
        })
        performance_timer.stop()
        
        assert response.status_code == status.HTTP_200_OK
        assert performance_timer.duration < 2.0  # Should complete within 2 seconds
    
    async def test_token_validation_performance(self, client: AsyncClient, authenticated_user: dict, performance_timer):
        """Test token validation performance."""
        performance_timer.start()
        response = await client.get("/auth/me", headers=authenticated_user["headers"])
        performance_timer.stop()
        
        assert response.status_code == status.HTTP_200_OK
        assert performance_timer.duration < 0.5  # Should complete within 500ms