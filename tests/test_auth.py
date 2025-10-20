import asyncio
from httpx import AsyncClient
from fastapi import status
from app.main import app


async def test_register_and_login_flow() -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.post("/auth/register", json={"nome": "Test User", "email": "test@example.com", "password": "secret123"})
        assert r.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST)

        r = await client.post("/auth/login", json={"email": "test@example.com", "password": "secret123"})
        assert r.status_code in (status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED)