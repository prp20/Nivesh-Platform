# API Reference & Data Sync

Nivesh Elite provides a robust set of RESTful endpoints for financial data management, authentication, and synchronization.

## 🔑 Authentication
- **Base Endpoint**: `/api/v1/auth`
- **Login**: `POST /login` (Returns JWT)
- **Me**: `GET /me` (Requires JWT)

---

## 📊 Mutual Funds
- **Listing**: `GET /api/v1/funds/`
    - **Params**: `is_active` (bool), `category` (str), `amc` (str), `skip` (int), `limit` (int)
    - **Response**: List of `FundMasterRead` objects (includes `isin`).
- **Detail**: `GET /api/v1/funds/{scheme_code}`
    - **Response**: `FundMasterRead` including `isin` and nested `metrics`.
- **Compare**: `GET /api/v1/funds/compare`
    - **Params**: `fund_a`, `fund_b`, `fund_c`, `fund_d` (up to 4 scheme codes).
    - **Response**: `ComparisonResponse` with aligned NAV history and metrics.
- **NAV History**: `GET /api/v1/navs/{scheme_code}`
    - **Response**: Chronological list of NAV points.
- **Bulk NAV Upload**: `POST /api/v1/navs/{scheme_code}/bulk`
    - **Payload**: `{"data": {"YYYY-MM-DD": value, ...}}`
- **Metrics**: `GET /api/v1/metrics/{scheme_code}`
    - **Response**: Comprehensive risk/return metrics:
        - **Absolute Returns**: `absolute_return_1y`, `3y`, `5y`, `10y`, `short_term_return_6m`.
        - **Capture Ratios**: `upside_capture`, `downside_capture`.
        - **Stats**: `sharpe_ratio`, `sortino_ratio`, `alpha`, `beta`, `std_dev`, `max_drawdown`, `tracking_error`, `information_ratio`.
- **Expense Ratio**: `GET /api/v1/funds/{scheme_code}/expense-ratio`
    - **Response**: List of `FundExpenseRatioRead` objects (historical TER).
- **Sync Status**: `GET /api/v1/metrics/{scheme_code}/status`
- **Compute**: `POST /api/v1/metrics/{scheme_code}/compute` (Manual re-calculation)

---

## 📈 Benchmarks (Indices)
- **Listing**: `GET /api/v1/benchmarks/` (Supports `q`, `is_active`, `skip`, `limit`)
- **History**: `GET /api/v1/benchmark-navs/{benchmark_code}`
- **CSV Data Ingestion**: `POST /api/v1/benchmark-navs/{benchmark_code}/upload` (Upload a CSV file)
- **Bulk Data Ingestion**: `POST /api/v1/benchmark-navs/{benchmark_code}/bulk`

---

## 🔄 Data Synchronization
- **Sync Fund**: `POST /api/v1/sync/{scheme_code}` (Force sync 1 fund)
- **Sync All**: `POST /api/v1/sync/all` (Trigger global background sync)

---

## 🛠️ Administrative CRUD
These endpoints require a valid JWT with administrative privileges:
- **Create**: `POST /api/v1/funds/`
- **Update**: `PUT /api/v1/funds/{scheme_code}`
- **Delete**: `DELETE /api/v1/funds/{scheme_code}`
