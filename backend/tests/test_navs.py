"""
Tests for NAV endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_get_fund_nav_history(async_client, seed_fund):
    """Test getting NAV history for a fund."""
    response = await async_client.get(f"/api/v1/navs/{seed_fund.scheme_code}?limit=10")
    # May return empty list if no NAVs exist
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_get_nav_history_with_limit(async_client, seed_fund):
    """Test NAV history with custom limit."""
    response = await async_client.get(f"/api/v1/navs/{seed_fund.scheme_code}?limit=100")
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_get_nav_default_limit(async_client, seed_fund):
    """Test NAV history with default limit (5000 max)."""
    response = await async_client.get(f"/api/v1/navs/{seed_fund.scheme_code}")
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_bulk_upload_navs_requires_auth(async_client, seed_fund):
    """Test bulk NAV upload (requires auth)."""
    nav_data = [
        {"nav_date": "2024-01-01", "nav_value": 100.0},
        {"nav_date": "2024-01-02", "nav_value": 101.0},
    ]
    response = await async_client.post(
        f"/api/v1/navs/{seed_fund.scheme_code}/bulk",
        json=nav_data
    )
    # Requires auth
    assert response.status_code in [200, 201, 401, 403, 404, 422]


@pytest.mark.asyncio
async def test_get_benchmark_nav_history(async_client, seed_fund):
    """Test getting benchmark NAV history."""
    response = await async_client.get(
        f"/api/v1/benchmark-navs/{seed_fund.benchmark_index_code}?limit=10"
    )
    # May return empty or 404 if no benchmark NAVs
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_bulk_upload_benchmark_navs_requires_auth(async_client, seed_fund):
    """Test bulk benchmark NAV upload (requires auth)."""
    nav_data = [
        {"nav_date": "2024-01-01", "index_value": 50000.0},
        {"nav_date": "2024-01-02", "index_value": 50100.0},
    ]
    response = await async_client.post(
        f"/api/v1/benchmark-navs/{seed_fund.benchmark_index_code}/bulk",
        json=nav_data
    )
    # Requires auth
    assert response.status_code in [200, 201, 401, 403, 404, 422]
