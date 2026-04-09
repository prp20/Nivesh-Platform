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

---

## 📊 Stock Market Data (Phase 1–4)

### Stock Master & Listing (Phase 1–2)
- **List Stocks**: `GET /api/v1/stocks`
    - **Params**: `sector` (str), `market_cap_cat` (str), `page` (int, default 1), `limit` (int, default 25, max 100), `sort_by` (symbol|company_name|sector), `order` (asc|desc)
    - **Response**: Paginated array of stocks with latest price, rating, total_score
    - **Example**: `GET /stocks?sector=Banking&limit=10&page=1`

- **Search Stocks**: `GET /api/v1/stocks/search`
    - **Params**: `q` (1-50 chars, searches symbol + company_name with tsvector)
    - **Response**: Array of matching stocks (max 20)
    - **Example**: `GET /stocks/search?q=reliance`

- **Stock Detail**: `GET /api/v1/stocks/{symbol}`
    - **Response**: Full snapshot with OHLCV, 1-day change %, rating, technical indicators (RSI, MACD, SMA)
    - **Example**: `GET /stocks/RELIANCE`

### Price History (Phase 2)
- **OHLCV Time-Series**: `GET /api/v1/stocks/{symbol}/price`
    - **Params**: `interval` (1d|1w|1mo), `from_date` (optional), `to_date` (optional), `limit` (365, max 2000)
    - **Response**: Chronological OHLCV data (weekly/monthly aggregated via date_trunc + ARRAY_AGG)
    - **Example**: `GET /stocks/RELIANCE/price?interval=1d&limit=90`

### Fundamentals & Shareholding (Phase 3)
- **Financial Statements**: `GET /api/v1/stocks/{symbol}/fundamentals`
    - **Params**: `statement_type` (PL|BS|CF), `period_type` (annual|quarterly), `limit` (5, max 20)
    - **Response**: Normalized financial data as JSON (revenue, net_profit, borrowings, etc.)
    - **Example**: `GET /stocks/BHARTIARTL/fundamentals?statement_type=PL&limit=5`

- **Shareholding Pattern**: `GET /api/v1/stocks/{symbol}/shareholding`
    - **Params**: `limit` (8, max 20)
    - **Response**: Ownership percentages by period (promoter%, FII%, DII%, public%, pledged%)
    - **Example**: `GET /stocks/BHARTIARTL/shareholding?limit=8`

### Stock Screener & Ratios (Phase 4)
- **Dynamic Stock Screener**: `GET /api/v1/screener`
    - **Valuation Filters**: `min_pe`, `max_pe`, `min_pb`, `max_pb`
    - **Profitability Filters**: `min_roe`, `min_roce`, `min_pat_margin`, `min_ebitda_margin`
    - **Growth Filters**: `min_revenue_growth`, `min_pat_growth`
    - **Leverage Filters**: `max_debt_equity`, `min_interest_cov`
    - **Quality Filters**: `min_cfo_to_pat`
    - **Stock Filters**: `sector`, `market_cap_cat`, `rating_label`
    - **Pagination**: `page` (1), `limit` (25, max 100), `sort_by` (total_score|roe|pe_ratio|revenue_growth|pat_margin|symbol), `order` (asc|desc)
    - **Response**: Paginated results with latest price, ratios, rating, total count, filters_applied
    - **Example**: `GET /screener?min_roe=15&max_pe=25&sector=Banking&limit=10`
    - **Key Feature**: Dynamic WHERE clause with parametrized queries (:key) prevents SQL injection; LATERAL JOINs for efficiency

- **Ratio History**: `GET /api/v1/stocks/{symbol}/ratios`
    - **Params**: `period_type` (annual|ttm, default annual), `limit` (5, max 20)
    - **Response**: Time-series of 17 financial ratios (PE, PB, PS, ROE, ROCE, ROA, margins, growth rates, leverage, quality)
    - **Example**: `GET /stocks/RELIANCE/ratios?period_type=annual&limit=5`

- **Compare Stocks**: `GET /api/v1/compare`
    - **Params**: `symbols` (comma-separated, max 5)
    - **Response**: Side-by-side comparison with latest price, ratios, fundamental/technical scores
    - **Example**: `GET /compare?symbols=RELIANCE,INFY,TCS,WIPRO,HCLTECH`

---

## 📊 Financial Ratio Engine (Phase 4)

### 17 Ratios Computed Per Stock

| Category | Ratio | Formula |
|---|---|---|
| **Valuation** | PE Ratio | `price / EPS` |
| | PB Ratio | `price / (equity / shares_outstanding)` |
| | PS Ratio | `price / (revenue / shares_outstanding)` |
| **Profitability** | ROE | `net_profit / equity` |
| | ROCE | `EBIT / (equity + debt - cash)` |
| | ROA | `net_profit / total_assets` |
| **Margins** | PAT Margin | `net_profit / revenue` |
| | EBITDA Margin | `EBITDA / revenue` |
| | Operating Margin | `operating_profit / revenue` |
| **Growth** | Revenue Growth | `(rev_curr - rev_prev) / abs(rev_prev) * 100` |
| | PAT Growth | `(pat_curr - pat_prev) / abs(pat_prev) * 100` |
| | EPS Growth | `(eps_curr - eps_prev) / abs(eps_prev) * 100` |
| **Leverage** | Debt/Equity | `total_debt / equity` |
| | Current Ratio | `current_assets / current_liabilities` |
| | Interest Coverage | `EBIT / interest_expense` |
| **Quality** | CFO-to-PAT | `operating_cash_flow / net_profit` |
| | Book Value per Share | `equity / shares_outstanding` |

### Safe Division Pattern
- All ratios use `safe_div()` helper: returns `None` if denominator is 0 or None
- Prevents division-by-zero crashes; invalid ratios omitted from results
- Handles alternative column names: "sales" vs "revenue", "net_worth" vs "equity"

### YoY Growth Calculation
- `(current_period - previous_period) / abs(previous_period) * 100`
- Handles negative-to-positive transitions (e.g., loss to profit)
- Returns None if previous_period is missing or zero

### Storage & Compute
- `financial_ratios` table: upserted after every fundamental scrape
- One row per stock per period (annual only)
- Ratios recomputed on-demand via `/stocks/{symbol}/ratios` endpoint
- Cache via latest period query: `ORDER BY period_end DESC LIMIT 1`

---

## 🔍 Screener Implementation Details

### Dynamic WHERE Clause Builder

```python
filters = ["s.is_active = TRUE", "s.is_index = FALSE"]
params = {"limit": limit, "offset": offset}

def add_filter(col, op, val, key):
    if val is not None:
        filters.append(f"{col} {op} :{key}")
        params[key] = val

add_filter("r.pe_ratio", ">=", min_pe, "min_pe")
add_filter("r.roe", ">=", min_roe, "min_roe")
# ... etc ...

where = " AND ".join(filters)
sql = f"... WHERE {where} ..."
```

**Key properties:**
- No string concatenation of user input → SQL injection safe
- Parametrized queries (`:key` placeholders)
- Optional filters: only added to WHERE if value is not None
- Clear audit trail: `filters_applied` in response shows which filters were active

### LATERAL JOIN Optimization

```sql
LEFT JOIN LATERAL (
    SELECT roe, roce, pat_margin, pe_ratio, ...
    FROM financial_ratios
    WHERE stock_id = s.id AND period_type = 'annual'
    ORDER BY period_end DESC LIMIT 1
) r ON TRUE
```

- Avoids N+1 queries (single query gets latest ratio per stock)
- PostgreSQL materializes subquery only for matching stocks
- Fallback to NULL for stocks with no ratio data (LEFT JOIN)
