# Database — Phase 1 Schema

Nivesh uses **Supabase PostgreSQL 16** via Alembic raw-SQL migrations (no SQLAlchemy autogenerate). All 18 tables are created by running `alembic upgrade head`.

For setup instructions see [GETTING_STARTED.md](./GETTING_STARTED.md).

---

## Migration Files

All migrations live in `nivesh-server/alembic/versions/`. They use `op.execute()` with raw DDL — no model autogeneration.

| File | Creates | Notes |
|------|---------|-------|
| `001_base_extensions_trigger.py` | Extensions + `set_updated_at` trigger | `pg_trgm`, `uuid-ossp` |
| `002_admin_users.py` | `admin_users` | RLS enabled |
| `003_etl_runs.py` | `etl_runs` | Unified ETL tracking, partial unique index |
| `004_fund_master.py` | `fund_master` | GIN trgm index for fuzzy search |
| `005_fund_nav_history.py` | `fund_nav_history` | Composite PK `(scheme_code, nav_date)` |
| `006_fund_metrics.py` | `fund_metrics` | Risk/return metrics per fund |
| `007_benchmark_master.py` | `benchmark_master` | Index → yfinance ticker mapping |
| `008_benchmark_nav_history.py` | `benchmark_nav_history` | Composite PK `(benchmark_code, nav_date)` |
| `009_benchmark_metrics.py` | `benchmark_metrics` | Benchmark-level metrics |
| `010_stocks.py` | `stocks` | NSE/BSE symbol master, GIN trgm on company_name |
| `011_price_data.py` | `price_data` | OHLCV time-series, FK → stocks |
| `012_financial_statements.py` | `financial_statements` | P&L/BS/CF as JSONB |
| `013_financial_ratios.py` | `financial_ratios` | 17 computed ratios per stock |
| `014_shareholding_pattern.py` | `shareholding_pattern` | Promoter/FII/DII/public pct |
| `015_technical_indicators.py` | `technical_indicators` | SMA, EMA, RSI, MACD, Bollinger, ATR, ADX |
| `016_detected_patterns.py` | `detected_patterns` | Chart pattern detection |
| `017_stock_ratings.py` | `stock_ratings` | Composite fundamental/valuation/technical score |
| `018_fundamental_scores.py` | `fundamental_scores` | AI-assisted deterministic scoring |

---

## Table Reference

### Infrastructure

#### `admin_users`
User accounts for the admin panel. RLS is enabled — only authenticated Supabase users can read.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `username` | VARCHAR(50) | UNIQUE |
| `password_hash` | TEXT | bcrypt |
| `is_active` | BOOLEAN | default true |
| `created_at` / `updated_at` | TIMESTAMPTZ | auto-managed |

#### `etl_runs`
Unified ETL job tracking. Replaces the old `sync_jobs` (MF) and `pipeline_audit` (stocks) tables.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `pipeline_name` | VARCHAR(60) | e.g. `amfi_nav`, `price_ingest` |
| `entity_id` | VARCHAR(50) | scheme_code or stock symbol (nullable) |
| `status` | VARCHAR(10) | `RUNNING` / `COMPLETED` / `FAILED` / `PARTIAL` |
| `triggered_by` | VARCHAR(20) | `scheduler` / `manual` / `backfill` |
| `started_at` | TIMESTAMPTZ | |
| `ended_at` | TIMESTAMPTZ | |
| `records_in` | INTEGER | default 0 |
| `records_out` | INTEGER | default 0 |
| `error_msg` | TEXT | |
| `metadata` | JSONB | |

Partial unique index prevents duplicate `RUNNING` jobs for the same `(pipeline_name, entity_id)`.

---

### Mutual Funds

#### `fund_master`
AMFI mutual fund registry.

| Column | Type | Notes |
|--------|------|-------|
| `scheme_code` | INTEGER PK | AMFI code |
| `scheme_name` | TEXT | GIN trgm index for fuzzy search |
| `amc_name` | VARCHAR(100) | |
| `scheme_category` | VARCHAR(60) | e.g. `Equity`, `Debt` |
| `scheme_subcategory` | VARCHAR(100) | |
| `plan_type` | VARCHAR(20) | `Direct` / `Regular` |
| `option_type` | VARCHAR(20) | `Growth` / `IDCW` |
| `benchmark_code` | VARCHAR(30) | FK → `benchmark_master` |
| `inception_date` | DATE | |
| `is_active` | BOOLEAN | default true |

#### `fund_nav_history`
Daily NAV time-series per fund.

| Column | Type | Notes |
|--------|------|-------|
| `scheme_code` | INTEGER | FK → `fund_master` |
| `nav_date` | DATE | |
| `nav` | NUMERIC(14,4) | |

Primary key: `(scheme_code, nav_date)`.

#### `fund_metrics`
Pre-computed risk/return metrics per fund.

Key columns: `absolute_return_1y/3y/5y/10y`, `sharpe_ratio`, `sortino_ratio`, `alpha`, `beta`, `std_dev`, `max_drawdown`, `tracking_error`, `information_ratio`, `upside_capture`, `downside_capture`.

---

### Benchmarks

#### `benchmark_master`
Index master — maps benchmark codes to yfinance tickers.

| Column | Type | Notes |
|--------|------|-------|
| `benchmark_code` | VARCHAR(30) PK | e.g. `NIFTY50` |
| `benchmark_name` | TEXT | |
| `ticker` | VARCHAR(30) | yfinance symbol, e.g. `^NSEI` |
| `benchmark_type` | VARCHAR(30) | `Equity Index` |
| `asset_class` | VARCHAR(30) | |

#### `benchmark_nav_history` / `benchmark_metrics`
Same structure as fund equivalents, keyed on `benchmark_code`.

---

### Stocks

#### `stocks`
NSE/BSE equity + index master.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `symbol` | VARCHAR(30) | UNIQUE, e.g. `RELIANCE` |
| `company_name` | TEXT | GIN trgm index |
| `isin` | VARCHAR(15) | |
| `exchange` | VARCHAR(10) | `NSE` / `BSE` |
| `sector` | VARCHAR(60) | |
| `industry` | VARCHAR(60) | |
| `market_cap_cat` | VARCHAR(20) | `Large` / `Mid` / `Small` |
| `yf_symbol` | VARCHAR(30) | Yahoo Finance symbol |
| `screener_slug` | VARCHAR(60) | screener.in URL slug |
| `is_index` | BOOLEAN | default false |
| `is_active` | BOOLEAN | default true |

#### `price_data`
Daily OHLCV from Yahoo Finance.

Primary key: `(stock_id, price_date)`. Columns: `open`, `high`, `low`, `close`, `adj_close`, `volume`.

#### `financial_statements`
P&L, Balance Sheet, Cash Flow stored as JSONB.

Primary key: `(stock_id, statement_type, period_type, period_end)`.
`statement_type`: `PL` / `BS` / `CF`. `period_type`: `annual` / `quarterly`.
`raw_checksum` (MD5) prevents duplicate writes on re-scrape.

#### `financial_ratios`
17 computed fundamental ratios per stock per period.

Ratios: `pe_ratio`, `pb_ratio`, `ps_ratio`, `roe`, `roce`, `roa`, `pat_margin`, `ebitda_margin`, `operating_margin`, `revenue_growth`, `pat_growth`, `eps_growth`, `debt_equity`, `current_ratio`, `interest_cov`, `cfo_to_pat`, `book_value_ps`.

Primary key: `(stock_id, period_type, period_end)`.

#### `shareholding_pattern`
Promoter/FII/DII/public ownership by quarter.

Primary key: `(stock_id, period_end)`.

#### `technical_indicators`
SMA(20/50/200), EMA(9/21), RSI(14), MACD, Bollinger Bands, ATR, ADX, Stochastic.

Primary key: `(stock_id, ind_date)`.

#### `detected_patterns`
Chart patterns (Head & Shoulders, Breakout, etc.) with confidence score and JSONB details.

#### `stock_ratings`
Composite score (0–100) broken into `fundamental_score`, `valuation_score`, `technical_score`, and `total_score` with a `rating_label` (`BUY` / `HOLD` / `SELL`).

Primary key: `(stock_id, rated_on)`.

#### `fundamental_scores`
AI-assisted deterministic fundamental scoring. See `fundamental_scoring_design.md`.

---

## Design Patterns

**TIMESTAMPTZ everywhere** — all datetime columns use `TIMESTAMPTZ` (timezone-aware). Supabase stores in UTC.

**Composite primary keys** — time-series tables use `(entity_id, date)` as PK instead of a surrogate ID, enabling efficient range queries without extra index lookups.

**GIN trigram indexes** — `fund_master.scheme_name` and `stocks.company_name` use `GIN (col gin_trgm_ops)` for `ILIKE '%query%'` searches without full table scans.

**JSONB for flexible schemas** — financial statements vary in structure across companies; JSONB allows storing heterogeneous keys without schema migrations.

**`set_updated_at` trigger** — a single trigger function (created in migration 001) is reused across all tables with an `updated_at` column.

**Idempotent upserts** — all seed scripts and ingestion jobs use `ON CONFLICT ... DO UPDATE` so re-runs are safe.
