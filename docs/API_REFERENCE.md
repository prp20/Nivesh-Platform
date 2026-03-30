# API Reference & Data Sync Guide

This document provides a comprehensive guide and reference to the RESTful endpoints for mutual fund data management, analytics, and synchronization in the Nivesh Elite platform.

## 🔑 Authentication
- **Base Endpoint**: `/api/v1/auth`
- **Login**: `POST /login` (Returns JWT)
- **Me**: `GET /me` (Requires JWT)

---

## 📊 Mutual Funds & Analytics

The backend provides full lifecycle management for fund master data:
- **Listing**: `GET /api/v1/funds/`
    - **Params**: `is_active` (bool), `category` (str), `amc` (str), `skip` (int), `limit` (int)
    - **Response**: List of `FundMasterRead` objects (includes `isin`).
- **Detail**: `GET /api/v1/funds/{scheme_code}`
    - **Response**: `FundMasterRead` including `isin` and nested `metrics`.
- **Compare**: `GET /api/v1/funds/compare`
    - **Params**: `codes` (comma-separated list of 2-4 scheme codes).
    - **Response**: `ComparisonResponse` with aligned NAV history and metrics.
- **Expense Ratio**: `GET /api/v1/funds/{scheme_code}/expense-ratio`
    - **Response**: List of `FundExpenseRatioRead` objects (historical TER).
- **Admin Create**: `POST /api/v1/funds/` (Requires JWT)
- **Admin Update**: `PUT /api/v1/funds/{scheme_code}` (Requires JWT)
- **Admin Delete**: `DELETE /api/v1/funds/{scheme_code}` (Requires JWT)

### Metrics Engine
- **View Metrics**: `GET /api/v1/metrics/{scheme_code}`
    - **Response**: Comprehensive risk/return metrics:
        - **Absolute Returns**: `absolute_return_1y`, `3y`, `5y`, `10y`, `short_term_return_6m`.
        - **Capture Ratios**: `upside_capture`, `downside_capture`.
        - **Stats**: `sharpe_ratio`, `sortino_ratio`, `alpha`, `beta`, `std_dev`, `max_drawdown`, `tracking_error`, `information_ratio`.
- **Sync Status**: `GET /api/v1/metrics/{scheme_code}/status`
- **Compute**: `POST /api/v1/metrics/{scheme_code}/compute` (Manual re-calculation)

---

## 🔄 Data Synchronization (NAVs)

### Latest NAVs Integration
The system implements **Just-In-Time** fetching. If you request metrics for a fund that hasn't been synced:
1. The backend automatically fetches 3+ years of history from `mftool`.
2. Populates the `fund_nav_history` table.
3. Computes risk metrics and saves to `fund_metrics`.

**Endpoints:**
- **NAV History**: `GET /api/v1/navs/{scheme_code}` (Chronological list of NAV points)
- **Sync Fund**: `POST /api/v1/sync/{scheme_code}` (Force sync 1 fund)
- **Sync All**: `POST /api/v1/sync/all` (Trigger global background sync)
- **Bulk NAV Upload**: `POST /api/v1/navs/{scheme_code}/bulk`
    - **Payload**: `{"data": {"YYYY-MM-DD": value, ...}}`

---

## 📈 Benchmarks (Indices)

The system provides robust CSV injection for integrating index historical data (e.g., Nifty indices).

- **Listing**: `GET /api/v1/benchmarks/` (Supports `q`, `is_active`, `skip`, `limit`)
- **History**: `GET /api/v1/benchmark-navs/{benchmark_code}`
- **CSV Data Ingestion**: `POST /api/v1/benchmark-navs/{benchmark_code}/upload`
  - Upload a CSV file directly (expecting "Date" and "Close" columns).
  - *(This is seamlessly integrated into the Frontend's Index Detail page.)*
- **Bulk Target Ingestion**: `POST /api/v1/benchmark-navs/{benchmark_code}/bulk`
