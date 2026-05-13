# API Reference

This document covers the `nivesh-server` REST API. The server is deployed on Render.com and exposes all market data and analytics endpoints.

> **Phase status:** The API implementation is planned for Phase 2. This document reflects the intended endpoint design based on the existing router files and shared schemas.

Base URL (local): `http://localhost:8000`
Base URL (production): `https://nivesh-server.onrender.com` *(Phase 2)*

---

## Authentication

Auth is controlled by the `ENABLE_AUTH` env var (default `false` in development).

| `ENABLE_AUTH` | Behavior |
|--------------|----------|
| `false` | All endpoints open — dev/test only |
| `true` | Protected endpoints require `Authorization: Bearer <token>` |

### Get a token

```bash
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=<ADMIN_PASSWORD>
```

Response:
```json
{"access_token": "<jwt>", "token_type": "bearer", "expires_in": 900}
```

### Auth endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/login` | None | Issue JWT |
| `POST` | `/api/v1/auth/refresh` | Refresh token | Renew access token |
| `GET`  | `/api/v1/auth/me` | Required | Current user info |

---

## System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/health` | None | DB connectivity + latency |

---

## Mutual Funds

All endpoints require JWT when `ENABLE_AUTH=true`.

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/funds/` | List funds — filtering, pagination |
| `GET`  | `/api/v1/funds/categories` | Distinct scheme categories |
| `GET`  | `/api/v1/funds/{scheme_code}` | Fund detail |
| `GET`  | `/api/v1/funds/{scheme_code}/similar` | Funds in same category |
| `GET`  | `/api/v1/funds/compare` | Compare 2–4 funds |

### Query params — `GET /api/v1/funds/`

| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Full-text search on scheme name |
| `category` | string | Filter by scheme_category |
| `amc` | string | Filter by AMC name |
| `plan_type` | string | `Direct` or `Regular` |
| `is_active` | bool | Default true |
| `skip` | int | Pagination offset (default 0) |
| `limit` | int | Page size (default 100, max 500) |

### Schema: `FundMasterRead`
```json
{
  "scheme_code": 120503,
  "scheme_name": "Axis Bluechip Fund - Direct Plan - Growth",
  "amc_name": "Axis Mutual Fund",
  "scheme_category": "Equity",
  "scheme_subcategory": "Large Cap Fund",
  "plan_type": "Direct",
  "benchmark_code": "NIFTY100",
  "inception_date": "2013-01-01",
  "is_active": true
}
```

---

## Benchmarks

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/benchmarks/` | List benchmarks |
| `GET`  | `/api/v1/benchmarks/{benchmark_code}` | Benchmark detail |

---

## NAV History

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/navs/{scheme_code}` | Fund NAV history |
| `POST` | `/api/v1/navs/{scheme_code}/bulk` | Bulk upload NAV records |
| `GET`  | `/api/v1/benchmark-navs/{benchmark_code}` | Benchmark NAV history |

Bulk upload payload:
```json
{"data": {"2024-01-15": 123.45, "2024-01-16": 124.00}}
```

---

## Fund Metrics

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/metrics/{scheme_code}` | Risk/return metrics (triggers background refresh if stale) |

Metrics include: `absolute_return_1y/3y/5y/10y`, `sharpe_ratio`, `sortino_ratio`, `alpha`, `beta`, `std_dev`, `max_drawdown`, `tracking_error`, `information_ratio`, `upside_capture`, `downside_capture`.

---

## Stocks

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/stocks` | List stocks — filter by sector, market cap |
| `GET`  | `/api/v1/stocks/search` | Search by symbol or company name |
| `GET`  | `/api/v1/stocks/{symbol}` | Full stock snapshot |
| `GET`  | `/api/v1/stocks/{symbol}/price` | OHLCV time-series |
| `GET`  | `/api/v1/stocks/{symbol}/fundamentals` | Financial statements |
| `GET`  | `/api/v1/stocks/{symbol}/ratios` | Financial ratio history |
| `GET`  | `/api/v1/stocks/{symbol}/shareholding` | Ownership pattern |

### Query params — `GET /api/v1/stocks`

| Param | Type | Description |
|-------|------|-------------|
| `sector` | string | Filter by sector |
| `market_cap_cat` | string | `Large` / `Mid` / `Small` |
| `is_index` | bool | Default false |
| `page` | int | Default 1 |
| `limit` | int | Default 25, max 100 |
| `sort_by` | string | `symbol` / `company_name` / `sector` |

### Query params — `GET /api/v1/stocks/{symbol}/price`

| Param | Type | Description |
|-------|------|-------------|
| `interval` | string | `1d` / `1w` / `1mo` |
| `from_date` | date | |
| `to_date` | date | |
| `limit` | int | Default 365, max 2000 |

---

## Screener

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/screener` | Filter stocks by 15+ fundamental ratios |
| `GET`  | `/api/v1/compare` | Side-by-side stock comparison (max 5) |

### Screener filter params

| Group | Params |
|-------|--------|
| Valuation | `min_pe`, `max_pe`, `min_pb`, `max_pb` |
| Profitability | `min_roe`, `min_roce`, `min_pat_margin`, `min_ebitda_margin` |
| Growth | `min_revenue_growth`, `min_pat_growth` |
| Leverage | `max_debt_equity`, `min_interest_cov` |
| Quality | `min_cfo_to_pat` |
| Universe | `sector`, `market_cap_cat`, `rating_label` |
| Pagination | `page`, `limit` (max 100), `sort_by`, `order` |

---

## Pipeline (Admin Only)

Requires JWT + admin role (`username == "admin"`).

### Price ingestion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/prices/all` | Ingest last 5 days OHLCV for all stocks |
| `POST` | `/api/v1/pipeline/prices/backfill` | Full historical backfill — param: `period` (e.g. `5y`) |
| `POST` | `/api/v1/pipeline/prices/refresh/{symbol}` | Refresh single stock |

### Fundamental scraper

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/screener/all` | Scrape overdue stocks (>90 days) |
| `POST` | `/api/v1/pipeline/screener/{symbol}` | Scrape single stock |

### Technical analysis

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/technical/all` | Run TA indicators for all stocks |
| `POST` | `/api/v1/pipeline/technical/{symbol}` | Run TA for single stock |

### Rating engine

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/ratings/all` | Recompute composite ratings |

### Fundamental scoring (LangGraph AI)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/fundamentals/run/{symbol}` | Full scoring pipeline (fetch → compute → AI reason → persist) |
| `POST` | `/api/v1/pipeline/fundamentals/bulk-run` | Background scoring for multiple symbols |

### ETL status

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/pipeline/status` | Overall pipeline health (reads from `etl_runs`) |

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `400` | Bad request (validation error) |
| `401` | Missing or invalid JWT |
| `403` | Valid token, insufficient role |
| `404` | Resource not found |
| `422` | Query/body parameter validation failed |
| `500` | Internal error — check server logs |

---

## Shared Schemas

Request/response types are defined in `nivesh-shared/schemas/`. Import pattern:

```python
from schemas.funds import FundMasterRead, FundMetricsResponse
from schemas.stocks import StockListResponse, ScreenerResponse
from schemas.market import BenchmarkMasterRead, SyncJobRead
from schemas.auth import TokenResponse, LoginRequest
```

Full schema definitions: see source files in `nivesh-shared/schemas/`.
