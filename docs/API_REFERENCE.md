# API Reference

Complete REST endpoint reference for the Nivesh Elite platform.

---

## 🔑 Authentication

All endpoints (except `/auth/login`) require a valid **JWT Bearer token**.

### Getting a Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin&password=admin123"
# → {"access_token": "<jwt>", "token_type": "bearer"}
```

### Using a Token

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/funds/
```

### Auth Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/login` | None | Issue JWT token |
| `GET`  | `/api/v1/auth/me`    | Required | Return current username |

### Auth Behavior

- **`ENABLE_AUTH=true`** (default) — all protected endpoints return `401` without a valid token; pipeline endpoints return `403` for non-admin users.
- **`ENABLE_AUTH=false`** — bypasses token validation (dev/test only). Set in `.env`.
- Token expiry: 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

### Two Auth Tiers

| Dependency | Used by | Behavior |
|-----------|---------|---------|
| `get_current_user` | All data endpoints | Any valid JWT → `200`; missing/invalid → `401` |
| `require_admin` | Pipeline endpoints | Valid JWT + `username == "admin"` → `200`; otherwise `403` |

---

## 📊 Mutual Funds

**All endpoints require JWT.**

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/funds/` | List funds with filtering & pagination |
| `GET`  | `/api/v1/funds/categories` | Distinct scheme categories |
| `GET`  | `/api/v1/funds/categories/{category}/subcategories` | Subcategories for a category |
| `GET`  | `/api/v1/funds/compare` | Compare 2–4 funds |
| `GET`  | `/api/v1/funds/{scheme_code}` | Fund detail |
| `GET`  | `/api/v1/funds/{scheme_code}/similar` | Funds in same category/subcategory |
| `POST` | `/api/v1/funds/` | Create fund |
| `PUT`  | `/api/v1/funds/{scheme_code}` | Update fund |
| `DELETE` | `/api/v1/funds/{scheme_code}` | Deactivate fund |

### `GET /api/v1/funds/`

**Query params:** `is_active` (bool), `category`, `subcategory`, `amc`, `plan_type`, `benchmark_code`, `q` (search), `order_by`, `skip` (default 0), `limit` (default 100, max 500)

### `GET /api/v1/funds/compare`

**Query params:** `codes` — comma-separated scheme codes (2–4). All funds must share the same `scheme_category`.

**Response:** `ComparisonResponse` with aligned NAV history, metrics, ranking, optional subcategory warning.

---

## 📈 Benchmarks

**All endpoints require JWT.**

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/benchmarks/` | List benchmarks |
| `GET`  | `/api/v1/benchmarks/{benchmark_code}` | Benchmark detail |
| `POST` | `/api/v1/benchmarks/` | Create benchmark |
| `PUT`  | `/api/v1/benchmarks/{benchmark_code}` | Update benchmark |
| `DELETE` | `/api/v1/benchmarks/{benchmark_code}` | Delete benchmark |

**Query params (list):** `q` (search), `is_active`, `skip`, `limit` (max 100)

---

## 📉 NAV History

**All endpoints require JWT.**

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/navs/{scheme_code}` | Fund NAV history |
| `POST` | `/api/v1/navs/{scheme_code}/bulk` | Bulk upload NAV records |
| `GET`  | `/api/v1/benchmark-navs/{benchmark_code}` | Benchmark NAV history |
| `POST` | `/api/v1/benchmark-navs/{benchmark_code}/bulk` | Bulk upload benchmark NAV records |
| `POST` | `/api/v1/benchmark-navs/{benchmark_code}/upload` | Upload benchmark CSV (Date + Close columns) |

**Query params (GET NAV history):** `limit` (default 100, max 5000)

**Bulk upload payload:**
```json
{"data": {"YYYY-MM-DD": 123.45, "YYYY-MM-DD": 124.00}}
```

---

## 📊 Fund Metrics

**All endpoints require JWT.**

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/metrics/{scheme_code}` | Get metrics; triggers background sync if stale (>24h) |
| `GET`  | `/api/v1/metrics/{scheme_code}/status` | Latest sync job status |
| `POST` | `/api/v1/metrics/{scheme_code}/compute` | Manually trigger metrics recomputation |

**Metrics returned:** `absolute_return_1y/3y/5y/10y`, `sharpe_ratio`, `sortino_ratio`, `alpha`, `beta`, `std_dev`, `max_drawdown`, `tracking_error`, `information_ratio`, `upside_capture`, `downside_capture`

---

## 🔄 Sync

**All endpoints require JWT.**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sync/{scheme_code}` | Force sync one fund (NAV + metrics) |
| `POST` | `/api/v1/sync/all` | Background sync all funds |

---

## 📈 Stocks

**All endpoints require JWT.**

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/stocks` | List stocks with filters & pagination |
| `GET`  | `/api/v1/stocks/search` | Search by symbol or company name |
| `GET`  | `/api/v1/stocks/{symbol}` | Full stock snapshot |
| `GET`  | `/api/v1/stocks/{symbol}/price` | OHLCV time-series |
| `GET`  | `/api/v1/stocks/{symbol}/fundamentals` | Financial statements (P&L / BS / CF) |
| `GET`  | `/api/v1/stocks/{symbol}/shareholding` | Ownership pattern history |

### `GET /api/v1/stocks`

**Params:** `sector`, `market_cap_cat`, `is_index` (bool, default false), `page` (default 1), `limit` (default 25, max 100), `sort_by` (symbol\|company_name\|sector), `order` (asc\|desc)

### `GET /api/v1/stocks/search`

**Params:** `q` (1–50 chars) — matches symbol prefix and full-text company name  
**Response:** Array of up to 20 matching stocks

### `GET /api/v1/stocks/{symbol}/price`

**Params:** `interval` (1d\|1w\|1mo), `from_date`, `to_date`, `limit` (default 365, max 2000)

### `GET /api/v1/stocks/{symbol}/fundamentals`

**Params:** `statement_type` (PL\|BS\|CF), `period_type` (annual\|quarterly), `limit` (default 5, max 20)

---

## 🔍 Screener & Ratios

**All endpoints require JWT.**

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/screener` | Dynamic stock screener with 15+ filters |
| `GET`  | `/api/v1/stocks/{symbol}/ratios` | Financial ratio history |
| `GET`  | `/api/v1/compare` | Side-by-side stock comparison (max 5) |

### `GET /api/v1/screener`

| Filter Group | Parameters |
|---|---|
| **Valuation** | `min_pe`, `max_pe`, `min_pb`, `max_pb` |
| **Profitability** | `min_roe`, `min_roce`, `min_pat_margin`, `min_ebitda_margin` |
| **Growth** | `min_revenue_growth`, `min_pat_growth` |
| **Leverage** | `max_debt_equity`, `min_interest_cov` |
| **Quality** | `min_cfo_to_pat` |
| **Stock** | `sector`, `market_cap_cat`, `rating_label` |
| **Pagination** | `page`, `limit` (max 100), `sort_by`, `order` |

**`sort_by` values:** `total_score`, `roe`, `pe_ratio`, `revenue_growth`, `pat_margin`, `symbol`

**Response:** `{results, total, page, limit, filters_applied}`

### `GET /api/v1/stocks/{symbol}/ratios`

**Params:** `period_type` (annual\|ttm), `limit` (default 5, max 20)

**17 ratios returned:** PE, PB, PS, ROE, ROCE, ROA, PAT margin, EBITDA margin, operating margin, revenue growth, PAT growth, EPS growth, debt/equity, current ratio, interest coverage, CFO-to-PAT, book value per share

### `GET /api/v1/compare`

**Params:** `symbols` — comma-separated (max 5)

**Response:** Side-by-side with latest price, ratios, and fundamental/technical/valuation scores

---

## ⚙️ Pipeline (Admin Only)

**All endpoints require JWT + admin role (`username == "admin"`).**  
Non-admin requests return `403 Forbidden`.

### Schedule (IST, Mon–Fri)

| Time | Job | Endpoint |
|------|-----|----------|
| 18:30 | Price ingestion | `POST /pipeline/prices/all` |
| 18:40 | Index ingestion | `POST /pipeline/prices/indices` |
| 19:00 | Metric refresh | `POST /pipeline/metrics/price-refresh/all` |
| 19:30 | Technical analysis | `POST /pipeline/technical/all` |
| 20:15 | Rating compute | `POST /pipeline/ratings/all` |

| Time | Job (Weekly, Sunday) | Endpoint |
|------|-----|----------|
| 02:00 | Fundamental scrape | `POST /pipeline/screener/all` |
| 09:00 | Ratio compute | `POST /pipeline/screener/all` |

### Price Ingestion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/prices/all` | Ingest last 5 days OHLCV for all stocks |
| `POST` | `/api/v1/pipeline/prices/indices` | Ingest indices only |
| `POST` | `/api/v1/pipeline/prices/backfill` | Full historical backfill — param: `period` (default `5y`) |
| `POST` | `/api/v1/pipeline/prices/refresh/{symbol}` | Refresh single stock — param: `period` |

### Metrics Recompute

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/metrics/price-refresh/all` | Recompute PE/PB/PS for all stocks |
| `POST` | `/api/v1/pipeline/metrics/price-refresh/{symbol}` | Recompute for single stock |

### Fundamental Scraper (screener.in)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/screener/all` | Scrape all stocks overdue >90 days |
| `POST` | `/api/v1/pipeline/screener/{symbol}` | Scrape single stock — param: `force` (bool) |
| `GET`  | `/api/v1/pipeline/screener/status` | Last scrape date and overdue stock count |

### Technical Analysis

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/technical/all` | Run TA indicators for all stocks |
| `POST` | `/api/v1/pipeline/technical/{symbol}` | Run TA for single stock |
| `GET`  | `/api/v1/pipeline/technical/status` | TA status (MISSING / STALE flags) |

### Rating Engine

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/pipeline/ratings/all` | Recompute composite ratings for all stocks |
| `POST` | `/api/v1/pipeline/ratings/{symbol}` | Recompute for single stock |

### Pipeline Health

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/pipeline/status` | Overall pipeline health and job progress |

---

## 🚦 HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `204` | Deleted (no body) |
| `400` | Bad request (validation error, e.g. category mismatch) |
| `401` | Missing or invalid JWT token |
| `403` | Valid token but insufficient role (admin required) |
| `404` | Resource not found |
| `422` | Request body or query parameter validation failed |
| `500` | Internal server error |

---

## 📝 Notes

- **Stock endpoints** (`/stocks`, `/screener`, `/compare`) target PostgreSQL with JSONB and LATERAL JOINs. They return `500` in SQLite test environments.
- **TTM ratios** are stored as `period_type=ttm` and available via `/stocks/{symbol}/ratios?period_type=ttm`.
- **Screener queries** are SQL-injection safe: all user input is parameterized (`:key` placeholders); `ORDER BY` uses an allow-list (`SortColumnMap`).
- **Metrics sync** is JIT: requesting `/metrics/{scheme_code}` automatically triggers a background sync if data is older than 24 hours.
