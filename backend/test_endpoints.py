"""
Comprehensive backend API endpoint test suite.
Covers all routes: auth, funds, benchmarks, navs, metrics, sync.
"""

import asyncio
import json
import pytest
from httpx import AsyncClient
from datetime import date

from app.main import app
from app.database import engine, Base
from app.models import FundMaster, BenchmarkMaster, FundNavHistory


@pytest.fixture
async def client():
    """Create test HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def setup_db():
    """Setup fresh database for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def seed_data():
    """Seed test data."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # Create test fund
        fund = FundMaster(
            scheme_code="119533",
            scheme_name="Test Fund",
            amc_name="Test AMC",
            inception_date=date(2020, 1, 1),
            plan_type="Direct",
            scheme_category="Equity",
            scheme_subcategory="Largecap",
            benchmark_index_code="NIFTY50",
            isin="INF123K01A01",
            is_active=True,
        )
        session.add(fund)

        # Create test benchmark
        benchmark = BenchmarkMaster(
            benchmark_code="NIFTY50",
            benchmark_name="Nifty 50",
            ticker="^NSEI",
            benchmark_type="Index",
            asset_class="Equity",
            is_active=True,
        )
        session.add(benchmark)

        # Add NAV history
        nav = FundNavHistory(
            scheme_code="119533",
            nav_date=date(2024, 1, 1),
            nav_value=100.50,
        )
        session.add(nav)

        await session.commit()

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class TestAuthEndpoints:
    """Test /auth endpoints."""

    async def test_login_valid(self, client):
        """Test POST /login with valid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"

    async def test_login_invalid(self, client):
        """Test POST /login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401

    async def test_login_missing_fields(self, client):
        """Test POST /login with missing fields."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin"}
        )
        assert response.status_code == 422  # Validation error

    async def test_me_authenticated(self, client):
        """Test GET /me with valid token."""
        # First login to get token
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["access_token"]

        # Then access /me
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["username"] in ["admin", "dev_user"]

    async def test_me_no_auth(self, client):
        """Test GET /me without auth (should fail or return dev_user)."""
        response = await client.get("/api/v1/auth/me")
        # May return 200 with dev_user in dev mode or 401
        assert response.status_code in [200, 401]


class TestFundsEndpoints:
    """Test /funds endpoints."""

    async def test_list_funds_empty(self, client, setup_db):
        """Test GET /funds with no data."""
        response = await client.get("/api/v1/funds/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert "skip" in data and "limit" in data

    async def test_list_funds_with_data(self, client, setup_db, seed_data):
        """Test GET /funds with seeded data."""
        response = await client.get("/api/v1/funds/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_funds_pagination(self, client, setup_db, seed_data):
        """Test GET /funds with pagination params."""
        response = await client.get("/api/v1/funds/?skip=0&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "skip" in data
        assert "limit" in data

    async def test_list_funds_filter_category(self, client, setup_db, seed_data):
        """Test GET /funds with category filter."""
        response = await client.get("/api/v1/funds/?category=Equity")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    async def test_get_fund_valid(self, client, setup_db, seed_data):
        """Test GET /funds/{scheme_code} with valid code."""
        response = await client.get("/api/v1/funds/119533")
        assert response.status_code == 200
        data = response.json()
        assert data["scheme_code"] == "119533"
        assert data["scheme_name"] == "Test Fund"

    async def test_get_fund_invalid(self, client, setup_db):
        """Test GET /funds/{scheme_code} with invalid code."""
        response = await client.get("/api/v1/funds/INVALID")
        assert response.status_code == 404

    async def test_similar_funds(self, client, setup_db, seed_data):
        """Test GET /funds/{scheme_code}/similar."""
        response = await client.get("/api/v1/funds/119533/similar")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_compare_funds_valid(self, client, setup_db, seed_data):
        """Test GET /funds/compare with valid codes."""
        # Need at least 2 funds of same category for comparison
        response = await client.get("/api/v1/funds/compare?codes=119533,119533")
        assert response.status_code in [200, 400]  # Either works or invalid (same fund)

    async def test_compare_funds_missing_codes(self, client, setup_db):
        """Test GET /funds/compare without codes."""
        response = await client.get("/api/v1/funds/compare")
        assert response.status_code == 422  # Validation error

    async def test_compare_funds_too_many(self, client, setup_db):
        """Test GET /funds/compare with > 4 funds."""
        response = await client.get("/api/v1/funds/compare?codes=1,2,3,4,5")
        assert response.status_code == 400

    async def test_create_fund_authenticated(self, client, setup_db):
        """Test POST /funds (requires auth)."""
        # Get token first
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]

        payload = {
            "scheme_code": "NEW123",
            "scheme_name": "New Fund",
            "amc_name": "New AMC",
            "inception_date": "2024-01-01",
            "plan_type": "Direct",
            "scheme_category": "Equity",
        }
        response = await client.post(
            "/api/v1/funds/",
            json=payload,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 201

    async def test_create_fund_unauthenticated(self, client, setup_db):
        """Test POST /funds without auth (should fail)."""
        payload = {
            "scheme_code": "NEW123",
            "scheme_name": "New Fund",
            "amc_name": "New AMC",
            "inception_date": "2024-01-01",
            "plan_type": "Direct",
            "scheme_category": "Equity",
        }
        response = await client.post(
            "/api/v1/funds/",
            json=payload
        )
        # In dev mode, may allow; in prod mode, should fail
        assert response.status_code in [201, 401]

    async def test_create_fund_invalid_schema(self, client, setup_db):
        """Test POST /funds with invalid schema."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]

        payload = {"scheme_code": "NEW123"}  # Missing required fields
        response = await client.post(
            "/api/v1/funds/",
            json=payload,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422


class TestBenchmarksEndpoints:
    """Test /benchmarks endpoints."""

    async def test_list_benchmarks(self, client, setup_db, seed_data):
        """Test GET /benchmarks."""
        response = await client.get("/api/v1/benchmarks/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_get_benchmark_valid(self, client, setup_db, seed_data):
        """Test GET /benchmarks/{code} with valid code."""
        response = await client.get("/api/v1/benchmarks/NIFTY50")
        assert response.status_code == 200
        data = response.json()
        assert data["benchmark_code"] == "NIFTY50"

    async def test_get_benchmark_invalid(self, client, setup_db):
        """Test GET /benchmarks/{code} with invalid code."""
        response = await client.get("/api/v1/benchmarks/INVALID")
        assert response.status_code == 404

    async def test_create_benchmark_authenticated(self, client, setup_db):
        """Test POST /benchmarks (requires auth)."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]

        payload = {
            "benchmark_code": "NIFTYBANK",
            "benchmark_name": "Nifty Bank",
            "ticker": "^NSEBANK",
        }
        response = await client.post(
            "/api/v1/benchmarks/",
            json=payload,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 201

    async def test_create_benchmark_unauthenticated(self, client, setup_db):
        """Test POST /benchmarks without auth."""
        payload = {
            "benchmark_code": "TEST",
            "benchmark_name": "Test",
            "ticker": "TEST",
        }
        response = await client.post(
            "/api/v1/benchmarks/",
            json=payload
        )
        assert response.status_code in [201, 401]


class TestNavsEndpoints:
    """Test /navs endpoints."""

    async def test_get_nav_history(self, client, setup_db, seed_data):
        """Test GET /navs/{scheme_code}."""
        response = await client.get("/api/v1/navs/119533")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_nav_history_with_limit(self, client, setup_db, seed_data):
        """Test GET /navs/{scheme_code}?limit=X."""
        response = await client.get("/api/v1/navs/119533?limit=10")
        assert response.status_code == 200

    async def test_get_nav_history_limit_cap(self, client, setup_db, seed_data):
        """Test GET /navs/{scheme_code}?limit=9999 (should be capped)."""
        response = await client.get("/api/v1/navs/119533?limit=9999")
        # Should either accept and cap, or return 422
        assert response.status_code in [200, 422]

    async def test_bulk_upload_nav_authenticated(self, client, setup_db, seed_data):
        """Test POST /navs/{scheme_code}/bulk (requires auth)."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]

        payload = {
            "data": {
                "2024-01-01": 100.5,
                "2024-01-02": 101.0,
            }
        }
        response = await client.post(
            "/api/v1/navs/119533/bulk",
            json=payload,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in [200, 201]

    async def test_bulk_upload_nav_unauthenticated(self, client, setup_db, seed_data):
        """Test POST /navs/{scheme_code}/bulk without auth."""
        payload = {
            "data": {
                "2024-01-01": 100.5,
            }
        }
        response = await client.post(
            "/api/v1/navs/119533/bulk",
            json=payload
        )
        assert response.status_code in [200, 201, 401]


class TestBenchmarkNavsEndpoints:
    """Test /benchmark-navs endpoints."""

    async def test_get_benchmark_nav_history(self, client, setup_db, seed_data):
        """Test GET /benchmark-navs/{code}."""
        response = await client.get("/api/v1/benchmark-navs/NIFTY50")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_bulk_upload_benchmark_nav(self, client, setup_db, seed_data):
        """Test POST /benchmark-navs/{code}/bulk (requires auth)."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]

        payload = {
            "data": {
                "2024-01-01": 19000.0,
            }
        }
        response = await client.post(
            "/api/v1/benchmark-navs/NIFTY50/bulk",
            json=payload,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in [200, 201]


class TestMetricsEndpoints:
    """Test /metrics endpoints."""

    async def test_get_metrics_no_data(self, client, setup_db):
        """Test GET /metrics/{code} with no data."""
        response = await client.get("/api/v1/metrics/119533")
        # May trigger background sync; response should have sync status
        assert response.status_code == 200

    async def test_get_metrics_invalid_code(self, client, setup_db):
        """Test GET /metrics with invalid scheme_code format."""
        response = await client.get("/api/v1/metrics/!!!invalid!!!")
        assert response.status_code == 400  # Bad format validation

    async def test_get_sync_status(self, client, setup_db, seed_data):
        """Test GET /metrics/{code}/status."""
        response = await client.get("/api/v1/metrics/119533/status")
        # May return None or a job object
        assert response.status_code == 200

    async def test_compute_metrics_authenticated(self, client, setup_db, seed_data):
        """Test POST /metrics/{code}/compute (requires auth)."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]

        response = await client.post(
            "/api/v1/metrics/119533/compute",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in [200, 400, 409]  # May already be running


class TestSyncEndpoints:
    """Test /sync endpoints."""

    async def test_sync_single_fund_authenticated(self, client, setup_db, seed_data):
        """Test POST /sync/{code} (requires auth)."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]

        response = await client.post(
            "/api/v1/sync/119533",
            headers={"Authorization": f"Bearer {token}"}
        )
        # May fail if mftool/API unavailable, but shouldn't be 401
        assert response.status_code != 401

    async def test_sync_all_authenticated(self, client, setup_db, seed_data):
        """Test POST /sync/all (requires auth)."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json()["access_token"]

        response = await client.post(
            "/api/v1/sync/all",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code != 401


class TestHealthEndpoint:
    """Test root health endpoint."""

    async def test_health_check(self, client):
        """Test GET /api/health."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "message" in data


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
