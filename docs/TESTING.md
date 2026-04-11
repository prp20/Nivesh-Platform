# Testing Guide

## Overview

The backend includes a comprehensive test suite with 45+ test cases covering all API endpoints. Tests use in-memory SQLite for fast, isolated execution without requiring a running PostgreSQL instance.

## Quick Start

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

## Test Architecture

### Fixtures (conftest.py)

| Fixture | Purpose |
|---------|---------|
| `test_db` | In-memory SQLite engine with all tables |
| `async_client` | AsyncClient for making HTTP requests |
| `seed_fund` | Pre-populated test fund (NIFTY50 benchmark) |
| `seed_stock` | Pre-populated test stock (RELIANCE) |

### Test Files

| File | Endpoints | Cases |
|------|-----------|-------|
| `test_health.py` | GET /api/health | 2 |
| `test_funds.py` | Fund CRUD, list, compare, similar | 11 |
| `test_benchmarks.py` | Benchmark CRUD, list | 8 |
| `test_navs.py` | NAV history, bulk upload | 6 |
| `test_metrics.py` | Metrics fetch, status, compute | 6 |
| `test_stocks.py` | Stock list, search, detail, fundamentals | 10 |
| `test_screener.py` | Screener filters, compare | 9 |
| `test_auth.py` | Login, /auth/me | 3 |
| `test_pipeline.py` | Admin job triggers | 10 |

## Running Tests

### All tests
```bash
pytest tests/ -v
```

### Specific test file
```bash
pytest tests/test_funds.py -v
```

### Single test
```bash
pytest tests/test_funds.py::test_list_funds_empty -v
```

### With coverage
```bash
pytest tests/ --cov=app --cov=pipeline
```

### Watch mode (requires pytest-watch)
```bash
ptw tests/
```

## Test Patterns

### Happy Path
```python
response = await async_client.get("/api/v1/funds/")
assert response.status_code == 200
```

### Error Handling
```python
response = await async_client.get("/api/v1/funds/999999")
assert response.status_code == 404
```

### Pagination
```python
response = await async_client.get("/api/v1/funds/?skip=0&limit=10")
assert response.status_code == 200
```

### Fixtures
```python
async def test_with_seed_data(async_client, seed_fund):
    response = await async_client.get(f"/api/v1/funds/{seed_fund.scheme_code}")
    assert response.status_code == 200
```

## Notes

- Tests use **in-memory SQLite**, not PostgreSQL (fast, isolated, no setup)
- Auth endpoints may pass or fail depending on `ENABLE_AUTH` setting
- Pipeline endpoints accept 200/201/401/403/404 (background jobs may not execute)
- Add `@pytest.mark.asyncio` to async test functions (configured in pytest.ini)

## Adding New Tests

1. Create test in appropriate file or new file under `tests/`
2. Use `async_client` fixture for HTTP requests
3. Use `seed_fund`/`seed_stock` for pre-populated data
4. Assert on `response.status_code` and `response.json()` as needed

Example:
```python
@pytest.mark.asyncio
async def test_my_endpoint(async_client):
    response = await async_client.get("/api/v1/my-endpoint")
    assert response.status_code == 200
    data = response.json()
    assert "field" in data
```
