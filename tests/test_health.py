"""Tests for the health check endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_health_returns_ok(async_client: AsyncClient) -> None:
    """GET /api/v1/health returns 200 with status, version, and database fields."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200

    body = response.json()
    assert "status" in body
    assert "version" in body
    assert "database" in body
    assert body["status"] == "healthy"
    assert body["database"] == "connected"


async def test_health_has_version(async_client: AsyncClient) -> None:
    """GET /api/v1/health returns a version matching the application version."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200

    body = response.json()
    assert body["version"] == "2.0.0"
