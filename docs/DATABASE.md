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

## ⚙️ Coding Conventions

### Mutual Funds & Benchmarks
- All blocking I/O inside async functions must use `asyncio.to_thread()` — mftool and `requests` are synchronous.
- `session_factory()` (not `get_db`) is used when opening a session outside of a request context (background tasks, `sync_all_funds`).
- `metrics_calculated_at` is always stored with `datetime.now(timezone.utc)` — never naive.
- NAV values ≤ 0 are rejected at the CRUD layer before insert.
- `_apply_fund_filters()` in `crud.py` is the single source of truth for FundMaster filter predicates — always use it in both count and list queries.
- GIN trigram indexes on `amc_name` and `scheme_category` require `CREATE EXTENSION IF NOT EXISTS pg_trgm` to be run once on the PostgreSQL instance.

### Stock Market Data
- OHLCV price data sourced via yfinance; batch processing in chunks of 50 to avoid API timeouts.
- Price ingestion jobs use `asyncio.to_thread()` for yfinance calls (synchronous blocking I/O).
- `price_data` upserted with `ON CONFLICT DO NOTHING` to allow safe re-runs of backfill.
- LATERAL JOINs used in stock queries for latest price/rating to avoid N+1 queries.
- Full-text search on `company_name` uses PostgreSQL tsvector + `plainto_tsquery` (GIN trigram index).
- Stock master registry has no foreign keys to MF tables (complete schema separation).

---

## 🔢 Fundamental Scraper — Storage Patterns

### Indian Number Parsing (`pipeline/normalizer.py`)
- Handles: `"87,939"`, `"(12,345)"` (negative), `"1,23,456"` (lakh format), `"12.34%"`, empty strings, `"N/A"`
- Converts to typed Python `float` or `None`
- Test coverage: 15 unit tests, 100% pass

### Financial Statement Storage
- Period-wise P&L, Balance Sheet, Cash Flow stored in `financial_statements` table
- Normalized JSON in `data` column: `{"revenue": 87939.0, "net_profit": 5048.0, ...}`
- `raw_checksum` (MD5 of raw scraped data) prevents duplicate writes on re-run
- Raw ScreenerScraper output preserved in `raw_data` column for audit trail

### Shareholding Tracking
- `shareholding_pattern` table: promoter/FII/DII/public/pledged percentages by period
- One record per quarter/month extracted from screener.in
- Upserted with `ON CONFLICT` to handle re-runs safely

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
