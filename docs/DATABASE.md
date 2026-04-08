# Database Schema & Design

Nivesh Elite uses **PostgreSQL** to manage master data and historical NAV data points.

## 🐘 Relational Schema

### 💎 Master Data
- `fund_master`: Stores AMFI codes, scheme names, categories, ISIN, and fund house details.
- `benchmark_master`: Maps market indices (e.g., NIFTY 50) to their respective exchange tickers.

### 📈 Computed Metrics
- `fund_metrics`: Stores daily risk/return metrics:
    - **Performance**: 1Y/3Y/5Y/10Y absolute returns, 3Y/5Y rolling returns, 6M short-term return.
    - **Risk**: Sharpe, Sortino, Std Dev, Max Drawdown.
    - **Relative**: Alpha, Beta, Tracking Error, Information Ratio.
    - **Capture**: Upside/Downside capture ratios.
    - **Metadata**: Data completeness percentage and calculation period.

---

## ⚡ Time-Series Tables
Historical values are stored in standard PostgreSQL tables with composite primary keys and B-Tree indexes on `nav_date`.

### `fund_nav_history`
- **Primary Keys**: `(scheme_code, nav_date)`
- **Indexes**: `ix_fund_nav_history_nav_date` on `nav_date`

### `benchmark_nav_history`
- **Primary Keys**: `(benchmark_code, nav_date)`
- **Indexes**: `ix_benchmark_nav_history_nav_date` on `nav_date`

---

## 🔄 Sync Tracking
- `sync_jobs`: Manages asynchronous data fetches.
    - **Statuses**: `RUNNING`, `COMPLETED`, `FAILED`.
    - **Concurrency**: Prevent overlapping jobs for the same `scheme_code` using a partial unique index.

---

## 🛠️ Migrations
We currently use a script-based migration for simplicity:
1. `seed_benchmarks.py`: Populates core market indices.
2. `migrate_data.py`: Imports legacy mutual fund metadata.

---

## 📈 Stock Market Data Schema (Phase 1–4)

The stock market module maintains a separate schema for NSE/BSE equities and indices, isolated from mutual fund tables.

### Master Data (Phase 1)
- `stocks`: NSE/BSE symbol master with metadata
    - **Columns**: `id`, `symbol`, `company_name`, `sector`, `market_cap_cat`, `screener_slug`, `is_active`, `is_index`, `created_at`
    - **Indexes**: Unique on `symbol`; GIN trigram on `company_name` for full-text search
    - **Data**: 18 large-cap stocks + 3 indices seeded

### Time-Series Data (Phase 2)
- `price_data`: OHLCV time-series from yfinance
    - **Primary Keys**: `(stock_id, price_date)` composite
    - **Columns**: `open`, `high`, `low`, `close`, `adj_close`, `volume`
    - **Indexes**: B-Tree on `price_date` for range queries
    - **Data**: ~4500 mock records (18 stocks × ~250 trading days)

### Financial Statements (Phase 3)
- `financial_statements`: P&L, Balance Sheet, Cash Flow with period tracking
    - **Columns**: `stock_id`, `statement_type` (PL|BS|CF), `period_type` (annual|quarterly), `period_end`, `data` (JSONB), `raw_data` (JSONB), `raw_checksum`, `scraped_at`
    - **Composite Key**: `(stock_id, statement_type, period_type, period_end)`
    - **Data Format**: Normalized JSON with keys like `revenue`, `net_profit`, `borrowings`, `equity`, etc.
    - **Checksum Dedup**: `raw_checksum` prevents duplicate writes on re-run

- `shareholding_pattern`: Ownership by investor category (quarterly/monthly)
    - **Columns**: `stock_id`, `period_end`, `promoter_pct`, `fii_pct`, `dii_pct`, `public_pct`, `pledged_pct`, `promoter_change`, `fii_change`, `scraped_at`
    - **Composite Key**: `(stock_id, period_end)`

### Financial Metrics (Phase 4)
- `financial_ratios`: 17 computed ratios per stock per period
    - **Columns**: `stock_id`, `period_end`, `period_type` (annual|ttm), 17 ratio columns (pe_ratio, pb_ratio, ps_ratio, roe, roce, roa, pat_margin, ebitda_margin, operating_margin, revenue_growth, pat_growth, eps_growth, debt_equity, current_ratio, interest_cov, cfo_to_pat, eps, book_value_ps), `computed_at`
    - **Composite Key**: `(stock_id, period_type, period_end)` with index on `period_end DESC` for latest query
    - **Data**: Upserted after every fundamental scrape; NULL for invalid ratios (safe_div pattern)

### Technical & Rating Data (Phase 1)
- `technical_indicators`: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, ADX, Stochastic
    - **Columns**: `stock_id`, `ind_date`, `timeframe` (1d|4h|1h), Technical indicator columns, `computed_at`
    - **Index**: On `(stock_id, ind_date)` for time-series queries

- `detected_patterns`: Chart patterns (Head & Shoulders, Breakout, Reversal, etc.)
    - **Columns**: `stock_id`, `pattern_type`, `detected_date`, `confidence`, `details` (JSONB)

- `stock_ratings`: Composite scoring (fundamental, valuation, technical components)
    - **Columns**: `stock_id`, `rated_on`, `fundamental_score`, `valuation_score`, `technical_score`, `total_score`, `rating_label` (BUY|HOLD|SELL)
    - **Indexes**: On `(stock_id, rated_on DESC)` for latest rating query

### Pipeline Tracking (Phase 1)
- `pipeline_audit`: Job tracking for stock data ingestion (separate from MF sync_jobs)
    - **Columns**: `id`, `job_name`, `stock_id` (nullable), `status` (RUNNING|COMPLETED|FAILED), `records_in`, `records_out`, `error_msg`, `started_at`, `ended_at`
    - **Purpose**: Audit trail for fundamental scrapes, price ingestions, ratio computations

### Key Design Patterns

**Composite Keys & Indexes:**
- Time-series tables use composite keys `(stock_id, period_end/price_date)` for efficient range queries
- Indexes on date columns enable fast time-range filtering
- GIN trigram index on `stocks.company_name` supports full-text search without separate tsvector table

**JSON Storage:**
- Financial statement data stored as JSONB for schema flexibility (handles variations in P&L/BS across companies)
- Raw scraped data preserved in `raw_data` column for audit trail
- `raw_checksum` deduplication: MD5 hash of raw data prevents duplicate inserts on re-run

**NULL Handling:**
- Ratios use `None/NULL` for invalid calculations (e.g., division by zero)
- LEFT JOIN fallback in queries: stocks without ratios/ratings still appear with NULL columns
- Avoids sentinel values (0, -1) that could be confused with valid metrics

**LATERAL JOIN Optimization:**
- Screener queries use PostgreSQL LATERAL JOINs to fetch latest ratio/price/rating per stock in single query
- Materializes subquery only for matching stocks → efficient for large result sets
- Example: `LEFT JOIN LATERAL (...) ON TRUE` pattern avoids N+1 round-trips

---

## 📊 Complete Table Summary

| Table | Purpose | Phase | Rows |
|---|---|---|---|
| `stocks` | NSE/BSE symbol master | 1 | 21 (18 stocks + 3 indices) |
| `price_data` | OHLCV time-series | 2 | ~4500 |
| `financial_statements` | P&L, BS, CF with periods | 3 | ~100+ |
| `shareholding_pattern` | Ownership by investor type | 3 | ~50+ |
| `financial_ratios` | 17 computed ratios | 4 | ~100+ |
| `technical_indicators` | SMA, RSI, MACD, etc. | 1 | ~200+ |
| `detected_patterns` | Chart pattern detection | 1 | ~50+ |
| `stock_ratings` | Composite scoring | 1 | ~50+ |
| `pipeline_audit` | Job tracking | 1 | Job history |
