"""Tests for /healthz and /readyz endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_healthz_returns_200() -> None:
    """GET /healthz returns 200 OK and status 'ok'."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz_returns_200_when_db_is_reachable() -> None:
    """GET /readyz returns 200 OK and connected status when DB check succeeds."""
    transport = ASGITransport(app=app)
    with patch("app.api.health.check_database_health", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = True
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/readyz")
            assert response.status_code == 200
            assert response.json() == {"status": "ready", "database": "connected"}


@pytest.mark.asyncio
async def test_readyz_returns_503_when_db_is_down() -> None:
    """GET /readyz returns 503 Service Unavailable when DB check fails."""
    transport = ASGITransport(app=app)
    with patch("app.api.health.check_database_health", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = False
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/readyz")
            assert response.status_code == 503
            assert response.json() == {"status": "not_ready", "database": "unreachable"}


@pytest.mark.asyncio
async def test_readyz_returns_503_with_unreachable_real_database() -> None:
    """GET /readyz returns 503 without mocking when real database is not running."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready", "database": "unreachable"}
