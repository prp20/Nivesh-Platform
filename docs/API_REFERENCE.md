# API Reference

This document covers the `nivesh-server` REST API. The server is deployed on Render.com and exposes all market data and analytics endpoints.

Base URL (local): `http://localhost:8000`
Base URL (production): `https://nivesh-server.onrender.com`

---

## Authentication

Auth is controlled by the `ENABLE_AUTH` env var (default `false` in development).

| `ENABLE_AUTH` | Behavior |
|--------------|----------|
| `false` | All endpoints open — dev/test only |
| `true` | Protected endpoints require `Authorization: Bearer <token>` |

### Token design

- **Access token** — short-lived JWT (default 15 min), returned in response body. Pass as `Authorization: Bearer <token>`.
- **Refresh token** — long-lived JWT (default 7 days), set as an `HttpOnly` cookie at path `/api/v1/auth`. Never readable by JavaScript.

### Get a token

```bash
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin", "password": "<ADMIN_PASSWORD>"}
```

Response:
```json
{"access_token": "<jwt>", "token_type": "bearer", "expires_in": 900}
```

The refresh token is set automatically as an `HttpOnly` cookie. Include cookies in subsequent calls to `/api/v1/auth/refresh`.

### Auth endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/login` | None | Issue access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh cookie | Renew access token (re-issues refresh cookie) |
| `POST` | `/api/v1/auth/logout` | Required | Revoke tokens, clear refresh cookie |
| `GET`  | `/api/v1/auth/me` | Required | Current user info |

---

## System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/health` | None | Lightweight health check (Render use) — always 200, degrades gracefully |
| `GET`  | `/api/health` | None | Full health check with DB latency |
| `GET`  | `/api/v1/sync/status` | Required | Recent ETL run records (optional `?pipeline_name=` filter) |

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
| `GET`  | `/api/v1/navs/{scheme_code}` | Fund NAV history (supports delta sync via `from_date`) |
| `POST` | `/api/v1/navs/{scheme_code}/bulk` | Bulk upload NAV records |
| `GET`  | `/api/v1/benchmark-navs/{benchmark_code}` | Benchmark NAV history |

### Query params — `GET /api/v1/navs/{scheme_code}`

| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Max records (default 100, max 5000) |
| `from_date` | date | Return only NAVs on or after this date — for delta sync (`YYYY-MM-DD`) |

Response is wrapped in the standard envelope:
```json
{"status": "ok", "data": [...], "meta": {"from_date": "2025-01-01", "count": 87}}
```

Bulk upload payload:
```json
{"data": {"2024-01-15": 123.45, "2024-01-16": 124.00}}
```

---

## Fund Metrics

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/metrics/{scheme_code}` | Risk/return metrics — triggers background refresh if stale (>24 h) |
| `GET`  | `/api/v1/metrics/{scheme_code}/status` | Latest ETL run status for a fund |
| `POST` | `/api/v1/metrics/{scheme_code}/compute` | Manually trigger background recomputation |

The `GET /metrics/{scheme_code}` response includes `sync_job_id`, `sync_status`, and `sync_message` alongside the metrics object so the client can poll for completion.

Metrics include: `absolute_return_1y/3y/5y/10y`, `sharpe_ratio`, `sortino_ratio`, `alpha`, `beta`, `standard_deviation`, `maximum_drawdown`, `tracking_error`, `information_ratio`, `upside_capture`, `downside_capture`.

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
| `POST` | `/api/v1/pipeline/prices/all` | Ingest last 5 days OHLCV for all active non-index stocks |
| `POST` | `/api/v1/pipeline/prices/indices` | Ingest last 5 days OHLCV for index stocks |
| `POST` | `/api/v1/pipeline/prices/backfill` | Full historical backfill — query param: `period` (default `5y`) |
| `POST` | `/api/v1/pipeline/prices/refresh/{symbol}` | Refresh single stock — query param: `period` (default `1mo`) |

### Metrics recompute

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/metrics/recompute` | Refresh PE/PB/PS ratios for all stocks from latest close |
| `POST` | `/api/v1/pipeline/metrics/recompute/{symbol}` | Refresh PE/PB/PS for a single stock |

### Fundamental scraper

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/screener/all` | Scrape overdue stocks (not updated in >90 days) — query param: `days_since_last` |
| `POST` | `/api/v1/pipeline/screener/{symbol}` | Scrape single stock — query param: `force` (default false, bypasses checksum) |

### Ratio engine

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/ratios/all` | Compute financial ratios for all stocks from their financial statements |
| `POST` | `/api/v1/pipeline/ratios/{symbol}` | Compute ratios for a single stock |

### Technical analysis

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/technical/all` | Compute TA-Lib indicators for all active stocks |
| `POST` | `/api/v1/pipeline/technical/{symbol}` | Compute TA indicators for a single stock |
| `GET`  | `/api/v1/pipeline/technical/status` | Per-stock TA status: last computed date + OK / STALE / MISSING flag |

### Rating engine

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/ratings/all` | Recompute composite ratings for all stocks |
| `POST` | `/api/v1/pipeline/ratings/{symbol}` | Recompute rating for a single stock |

### Fundamental scoring (LangGraph AI)

Requires `GROQ_API_KEY` env var for LLM reasoning (falls back to template text if unset).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/fundamentals/run/{symbol}` | Full pipeline: Fetch → Compute → Reason → Persist |
| `POST` | `/api/v1/pipeline/fundamentals/bulk-run` | Background scoring for multiple symbols (body: `{symbols, period_type, score_version}`) |
| `POST` | `/api/v1/pipeline/fundamentals/stage/fetch/{symbol}` | Stage 1 only — fetch statements, return state dict |
| `POST` | `/api/v1/pipeline/fundamentals/stage/compute` | Stage 2 only — compute scores from state dict (body: `ScoringStateSchema`) |
| `POST` | `/api/v1/pipeline/fundamentals/stage/reason` | Stage 3 only — AI reasoning from state dict |
| `POST` | `/api/v1/pipeline/fundamentals/stage/persist` | Stage 4 only — persist state dict to DB |

`ScoringStateSchema` response fields: `stock_id`, `symbol`, `period_type`, `score_version`, `statements_data`, `pl_results`, `bs_results`, `cf_results`, `composite_score`, `reasoning_label`, `reasoning_text`, `status`, `error`, `logs`.

### Fund scoring (LangGraph AI)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/funds/run/{scheme_code}` | Score a fund: quantitative metrics + Groq LLM verdict |

Response fields: `scheme_code`, `fund_name`, `quality_score` (0–10), `rating_label` (Excellent/Good/Average/Below Average/Poor), `reasoning_text`, `breakdown`.

### ETL status

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/pipeline/status` | Overall pipeline health — latest `etl_runs` rows per pipeline |

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

## Response Envelope

Most list and delta-sync endpoints wrap their response in a standard envelope:

```json
{
  "status": "ok",
  "data": [...],
  "meta": {}
}
```

Paginated responses include `total`, `page`, and `page_size` in `meta`.

---

## Shared Schemas

Request/response types are defined in `nivesh-shared/schemas/`. Import pattern:

```python
from schemas.funds import FundMasterRead, FundMetricsResponse
from schemas.stocks import StockListResponse, ScreenerResponse
from schemas.market import BenchmarkMasterRead
from schemas.auth import TokenResponse, LoginRequest
```

Server-internal schemas (e.g. `EtlRunRead`, `ScoringStateSchema`) remain in `app/schemas.py`.

Full schema definitions: see source files in `nivesh-shared/schemas/`.
