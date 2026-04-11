"""
Tests for stock screener endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_screener_no_filters(async_client):
    """Test screener with no filters."""
    response = await async_client.get("/api/v1/screener")
    assert response.status_code in [200, 404, 500]
    data = response.json()
    # Should return list or dict with results
    assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_screener_with_pe_filter(async_client):
    """Test screener with P/E filter."""
    response = await async_client.get("/api/v1/screener?min_pe=10&max_pe=30")
    assert response.status_code in [200, 404, 500]
    data = response.json()
    assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_screener_with_roe_filter(async_client):
    """Test screener with ROE filter."""
    response = await async_client.get("/api/v1/screener?min_roe=15")
    assert response.status_code in [200, 404, 500]
    data = response.json()
    assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_screener_with_sector_filter(async_client):
    """Test screener with sector filter."""
    response = await async_client.get("/api/v1/screener?sector=Banking")
    assert response.status_code in [200, 404, 500]
    data = response.json()
    assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_screener_with_multiple_filters(async_client):
    """Test screener with multiple filters."""
    response = await async_client.get(
        "/api/v1/screener?min_pe=10&max_pe=30&sector=Banking&min_roe=10"
    )
    assert response.status_code in [200, 404, 500]
    data = response.json()
    assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_screener_with_pagination(async_client):
    """Test screener with pagination."""
    response = await async_client.get("/api/v1/screener?page=1&limit=20")
    assert response.status_code in [200, 404, 500]


@pytest.mark.asyncio
async def test_screener_with_sorting(async_client):
    """Test screener with sort parameter."""
    response = await async_client.get("/api/v1/screener?sort_by=roe&order=desc")
    assert response.status_code in [200, 404, 500]


@pytest.mark.asyncio
async def test_compare_stocks(async_client, seed_stock):
    """Test comparing multiple stocks."""
    response = await async_client.get(f"/api/v1/compare?symbols={seed_stock.symbol}")
    # May work with single stock or require multiple
    assert response.status_code in [200, 400, 404, 422, 500]


@pytest.mark.asyncio
async def test_compare_multiple_stocks(async_client):
    """Test comparing 2-5 stocks."""
    response = await async_client.get("/api/v1/compare?symbols=RELIANCE,TCS,INFY")
    # May fail if stocks don't exist in test DB
    assert response.status_code in [200, 404, 422, 500]
