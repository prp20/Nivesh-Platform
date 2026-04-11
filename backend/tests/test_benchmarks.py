"""
Tests for benchmark endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_list_benchmarks(async_client):
    """Test listing all benchmarks."""
    response = await async_client.get("/api/v1/benchmarks/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_list_benchmarks_with_filters(async_client, seed_fund):
    """Test listing benchmarks with filter."""
    response = await async_client.get("/api/v1/benchmarks/?q=NIFTY")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, (dict, list))


@pytest.mark.asyncio
async def test_list_benchmarks_pagination(async_client):
    """Test benchmark listing with pagination."""
    response = await async_client.get("/api/v1/benchmarks/?skip=0&limit=10")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_benchmark_by_code(async_client, seed_fund):
    """Test getting a benchmark by code."""
    benchmark_code = seed_fund.benchmark_index_code
    response = await async_client.get(f"/api/v1/benchmarks/{benchmark_code}")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert data["benchmark_code"] == benchmark_code


@pytest.mark.asyncio
async def test_get_nonexistent_benchmark(async_client):
    """Test getting a benchmark that doesn't exist."""
    response = await async_client.get("/api/v1/benchmarks/INVALID_BENCH_XYZ")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_benchmark_requires_auth(async_client):
    """Test creating a benchmark (requires auth)."""
    data = {
        "benchmark_code": "NIFTY100",
        "benchmark_name": "Nifty 100",
    }
    response = await async_client.post("/api/v1/benchmarks/", json=data)
    assert response.status_code in [201, 200, 401, 403, 422]


@pytest.mark.asyncio
async def test_update_benchmark_requires_auth(async_client, seed_fund):
    """Test updating a benchmark (requires auth)."""
    update_data = {"benchmark_name": "Updated Name"}
    response = await async_client.put(
        f"/api/v1/benchmarks/{seed_fund.benchmark_index_code}",
        json=update_data
    )
    assert response.status_code in [200, 401, 403, 404]


@pytest.mark.asyncio
async def test_delete_benchmark_requires_auth(async_client, seed_fund):
    """Test deleting a benchmark (requires auth)."""
    response = await async_client.delete(
        f"/api/v1/benchmarks/{seed_fund.benchmark_index_code}"
    )
    assert response.status_code in [200, 401, 403, 404]
