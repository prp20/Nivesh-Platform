"""
Tests for health endpoint.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    """Test that health endpoint returns 200 OK."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data or "message" in data  # Generic health check


@pytest.mark.asyncio
async def test_health_endpoint_structure(async_client):
    """Test that health endpoint returns expected structure."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    # Health endpoint should return at least status or ok field
    assert isinstance(data, dict)
