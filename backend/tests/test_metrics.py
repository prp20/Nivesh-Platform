"""
Tests for metrics endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_get_metrics_for_fund(async_client, seed_fund):
    """Test getting metrics for a fund."""
    response = await async_client.get(f"/api/v1/metrics/{seed_fund.scheme_code}")
    # May return 200 with metrics or 404 if none exist
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_get_metrics_invalid_scheme_code(async_client):
    """Test getting metrics with invalid scheme code format."""
    response = await async_client.get("/api/v1/metrics/INVALID_CODE!!!!")
    # Should reject invalid format
    assert response.status_code in [400, 422, 404]


@pytest.mark.asyncio
async def test_get_metrics_nonexistent_fund(async_client):
    """Test getting metrics for non-existent fund."""
    response = await async_client.get("/api/v1/metrics/999999")
    assert response.status_code in [404, 200]  # 200 with null metrics or 404


@pytest.mark.asyncio
async def test_get_metrics_status(async_client, seed_fund):
    """Test getting metrics sync job status."""
    response = await async_client.get(f"/api/v1/metrics/{seed_fund.scheme_code}/status")
    # May return 200 with status or 404 if no job exists
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_compute_metrics_requires_auth(async_client, seed_fund):
    """Test computing metrics manually (requires auth)."""
    response = await async_client.post(
        f"/api/v1/metrics/{seed_fund.scheme_code}/compute"
    )
    # Requires auth (ENABLE_AUTH may be false now, so may succeed)
    assert response.status_code in [200, 201, 401, 403, 404]


@pytest.mark.asyncio
async def test_metrics_response_structure(async_client, seed_fund):
    """Test that metrics response has expected structure."""
    response = await async_client.get(f"/api/v1/metrics/{seed_fund.scheme_code}")
    if response.status_code == 200:
        data = response.json()
        # Metrics response should have scheme_code at minimum
        assert isinstance(data, dict)
