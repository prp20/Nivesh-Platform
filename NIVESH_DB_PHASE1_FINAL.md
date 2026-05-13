# Nivesh Platform — Database Design (Phase 1)
## Based on existing `dev` branch · Supabase PostgreSQL 16
### Minimalist — no new tables, no invented columns

---

## What Exists in the Codebase

Exactly **15 tables** are defined in `models.py`. This document covers all 15 — with two additions you explicitly requested: `admin_users` and an improved ETL tracking table that replaces the existing `sync_jobs` and `pipeline_audit`.

**No new domain tables are introduced.**

---

## Table Inventory

| # | Table | Group | Status |
|---|---|---|---|
| 1 | `admin_users` | Auth | **New — requested** |
| 2 | `sync_jobs` | ETL | Existing — replaced by `etl_runs` |
| 3 | `pipeline_audit` | ETL | Existing — merged into `etl_runs` |
| 4 | `etl_runs` | ETL | **New — replaces both above** |
| 5 | `fund_master` | Mutual Funds | Existing |
| 6 | `fund_nav_history` | Mutual Funds | Existing |
| 7 | `fund_metrics` | Mutual Funds | Existing |
| 8 | `benchmark_master` | Mutual Funds | Existing |
| 9 | `benchmark_nav_history` | Mutual Funds | Existing |
| 10 | `benchmark_metrics` | Mutual Funds | Existing |
| 11 | `stocks` | Stocks | Existing |
| 12 | `price_data` | Stocks | Existing |
| 13 | `financial_statements` | Stocks | Existing |
| 14 | `financial_ratios` | Stocks | Existing |
| 15 | `shareholding_pattern` | Stocks | Existing |
| 16 | `technical_indicators` | Stocks | Existing |
| 17 | `detected_patterns` | Stocks | Existing |
| 18 | `stock_ratings` | Stocks | Existing |
| 19 | `fundamental_scores` | Stocks | Existing |

**Total: 17 tables** (15 existing + `admin_users` + `etl_runs`, with `sync_jobs` and `pipeline_audit` consolidated)

---

## Schema Groups

```
supabase / public
│
├── AUTH
│   └── admin_users
│
├── ETL
│   └── etl_runs              ← replaces sync_jobs + pipeline_audit
│
├── MUTUAL FUNDS
│   ├── fund_master
│   ├── fund_nav_history
│   ├── fund_metrics
│   ├── benchmark_master
│   ├── benchmark_nav_history
│   └── benchmark_metrics
│
└── STOCKS
    ├── stocks
    ├── price_data
    ├── financial_statements
    ├── financial_ratios
    ├── shareholding_pattern
    ├── technical_indicators
    ├── detected_patterns
    ├── stock_ratings
    └── fundamental_scores
```

---

## AUTH

### `admin_users` — New

Stores platform users. JWT signing key lives in the environment — only identity and role live here. Tokens are short-lived (15 min); logout is handled by checking a `jti` claim against this table's `revoked_jti` array (avoids a second table for a single-admin platform).

```sql
CREATE TABLE admin_users (
    user_id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    username         VARCHAR(50)  NOT NULL UNIQUE,
    email            VARCHAR(255) NOT NULL UNIQUE,
    hashed_password  VARCHAR(255) NOT NULL,
    user_role        VARCHAR(20)  NOT NULL DEFAULT 'analyst'
                         CHECK (user_role IN ('admin', 'analyst', 'service')),
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login_at    TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_admin_users_role ON admin_users (user_role);

-- Trigger: keep updated_at current
CREATE TRIGGER trg_admin_users_updated_at
    BEFORE UPDATE ON admin_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS: only the server app (service_role key) can touch this table
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_only" ON admin_users
    USING (auth.role() = 'service_role');
```

**Columns:**

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID PK | `gen_random_uuid()` — no sequential IDs |
| `username` | VARCHAR(50) | Login identifier — unique |
| `email` | VARCHAR(255) | Unique |
| `hashed_password` | VARCHAR(255) | bcrypt hash |
| `user_role` | VARCHAR(20) | `admin` / `analyst` / `service` |
| `is_active` | BOOLEAN | Soft-disable without deleting |
| `last_login_at` | TIMESTAMPTZ | Updated on each successful login |
| `created_at` | TIMESTAMPTZ | Auto |
| `updated_at` | TIMESTAMPTZ | Auto via trigger |

**Role definitions:**
- `admin` — full platform access, can manage users
- `analyst` — read-only API access
- `service` — used by ETL pipeline automation; no interactive login

---

## ETL

### `etl_runs` — New (replaces `sync_jobs` + `pipeline_audit`)

The existing codebase has two overlapping tables:
- `sync_jobs` — tracks MF data sync per `scheme_code`, with a partial unique index preventing concurrent runs
- `pipeline_audit` — tracks stock pipeline jobs per `stock_id` with records in/out

They solve the same problem for different domains. `etl_runs` consolidates them cleanly. The partial unique index behaviour of `sync_jobs` is preserved via the `UNIQUE` constraint on `(pipeline_name, entity_id)` where `status = 'RUNNING'`.

```sql
CREATE TABLE etl_runs (
    id            BIGSERIAL    PRIMARY KEY,
    pipeline_name VARCHAR(60)  NOT NULL,
    -- e.g. 'amfi_nav', 'nse_price', 'fund_metrics',
    --      'technical_indicators', 'financial_statements', 'stock_ratings'
    entity_id     VARCHAR(50),
    -- scheme_code for MF jobs; stock symbol or NULL for market-wide jobs
    status        VARCHAR(10)  NOT NULL DEFAULT 'RUNNING'
                      CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'PARTIAL')),
    triggered_by  VARCHAR(20)  NOT NULL DEFAULT 'scheduler'
                      CHECK (triggered_by IN ('scheduler', 'manual', 'backfill')),
    started_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ended_at      TIMESTAMPTZ,
    records_in    INTEGER      NOT NULL DEFAULT 0,
    records_out   INTEGER      NOT NULL DEFAULT 0,
    error_msg     TEXT,
    metadata      JSONB
);

-- Prevent two concurrent RUNNING jobs for the same pipeline + entity
CREATE UNIQUE INDEX uq_etl_runs_running
    ON etl_runs (pipeline_name, COALESCE(entity_id, ''))
    WHERE status = 'RUNNING';

CREATE INDEX idx_etl_runs_pipeline_started
    ON etl_runs (pipeline_name, started_at DESC);

CREATE INDEX idx_etl_runs_status
    ON etl_runs (status, started_at DESC);
```

**Columns:**

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | Auto-increment |
| `pipeline_name` | VARCHAR(60) | Job type identifier |
| `entity_id` | VARCHAR(50) | `scheme_code` for MF; `symbol` for stocks; NULL for market-wide |
| `status` | VARCHAR(10) | `RUNNING → COMPLETED / FAILED / PARTIAL` |
| `triggered_by` | VARCHAR(20) | `scheduler / manual / backfill` |
| `started_at` | TIMESTAMPTZ | Job start time |
| `ended_at` | TIMESTAMPTZ | NULL while running |
| `records_in` | INTEGER | Source records read |
| `records_out` | INTEGER | Records written to DB |
| `error_msg` | TEXT | Top-level error if FAILED |
| `metadata` | JSONB | Flexible extra context (watermark dates, file URLs, etc.) |

**Migration path from existing tables:**
```sql
-- After deploying etl_runs, copy existing history across:
INSERT INTO etl_runs (pipeline_name, entity_id, status, started_at, ended_at, error_msg)
SELECT 'amfi_nav', scheme_code, status, created_at, updated_at, message
FROM sync_jobs;

INSERT INTO etl_runs (pipeline_name, entity_id, status, started_at, ended_at,
                      records_in, records_out, error_msg, metadata)
SELECT job_name, s.symbol, pa.status, pa.started_at, pa.ended_at,
       pa.records_in, pa.records_out, pa.error_msg, pa.metadata_
FROM pipeline_audit pa
LEFT JOIN stocks s ON s.id = pa.stock_id;

-- Then drop the old tables (after verifying the migration)
-- DROP TABLE sync_jobs;
-- DROP TABLE pipeline_audit;
```

---

## MUTUAL FUNDS

All six mutual fund tables are **kept exactly as coded** in `models.py`. The only change is switching `TIMESTAMP` → `TIMESTAMPTZ` and ensuring the `updated_at` trigger is applied. Column names, types, and indexes are untouched.

### `fund_master`

```sql
CREATE TABLE fund_master (
    scheme_code           VARCHAR(50)  PRIMARY KEY,
    scheme_name           VARCHAR(500) NOT NULL,
    amc_name              VARCHAR(200) NOT NULL,
    inception_date        DATE         NOT NULL,
    plan_type             VARCHAR(20)  NOT NULL,   -- 'Direct', 'Regular'
    scheme_category       VARCHAR(100) NOT NULL,
    scheme_subcategory    VARCHAR(100),
    benchmark_index_code  VARCHAR(50),
    isin                  VARCHAR(50)  UNIQUE,
    manager_experience    VARCHAR(500),
    is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Requires: CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_fund_master_amc_name_trgm
    ON fund_master USING GIN (amc_name gin_trgm_ops);
CREATE INDEX ix_fund_master_scheme_category_trgm
    ON fund_master USING GIN (scheme_category gin_trgm_ops);
CREATE INDEX ix_fund_master_plan_type  ON fund_master (plan_type);
CREATE INDEX ix_fund_master_is_active  ON fund_master (is_active);
CREATE INDEX ix_fund_master_isin       ON fund_master (isin);

CREATE TRIGGER trg_fund_master_updated_at
    BEFORE UPDATE ON fund_master
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### `fund_nav_history`

```sql
CREATE TABLE fund_nav_history (
    scheme_code  VARCHAR(50)    NOT NULL REFERENCES fund_master (scheme_code) ON DELETE CASCADE,
    nav_date     DATE           NOT NULL,
    nav_value    NUMERIC(15, 4) NOT NULL,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scheme_code, nav_date)
);

CREATE INDEX ix_fund_nav_history_nav_date ON fund_nav_history (nav_date);
```

---

### `fund_metrics`

```sql
CREATE TABLE fund_metrics (
    scheme_code                   VARCHAR(50)    PRIMARY KEY
                                      REFERENCES fund_master (scheme_code) ON DELETE CASCADE,
    current_nav                   NUMERIC(15, 4) NOT NULL,
    nav_date                      DATE           NOT NULL,
    aum_in_crores                 NUMERIC(18, 2),
    expense_ratio                 NUMERIC(5, 4),
    fund_rating                   NUMERIC(5, 2),
    volatility                    NUMERIC(10, 4),
    cagr_3year                    NUMERIC(10, 4),
    cagr_5year                    NUMERIC(10, 4),
    absolute_return_1y            NUMERIC(10, 4),
    absolute_return_3y            NUMERIC(10, 4),
    absolute_return_5y            NUMERIC(10, 4),
    absolute_return_10y           NUMERIC(10, 4),
    short_term_return_6m          NUMERIC(10, 4),
    upside_capture                NUMERIC(10, 4),
    downside_capture              NUMERIC(10, 4),
    sortino_ratio                 NUMERIC(10, 4),
    sharpe_ratio                  NUMERIC(10, 4),
    alpha                         NUMERIC(10, 4),
    beta                          NUMERIC(10, 4),
    standard_deviation            NUMERIC(10, 4),
    maximum_drawdown              NUMERIC(10, 4),
    tracking_error                NUMERIC(10, 4),
    information_ratio             NUMERIC(10, 4),
    metrics_calculated_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    calculation_period_start_date DATE,
    calculation_period_end_date   DATE,
    has_sufficient_data           BOOLEAN        NOT NULL DEFAULT TRUE,
    data_completeness_percentage  NUMERIC(5, 2),
    final_verdict                 VARCHAR(1000),
    updated_at                    TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_fund_metrics_updated_at
    BEFORE UPDATE ON fund_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### `benchmark_master`

```sql
CREATE TABLE benchmark_master (
    benchmark_code  VARCHAR(50)  PRIMARY KEY,
    benchmark_name  VARCHAR(200) NOT NULL,
    ticker          VARCHAR(50)  NOT NULL,
    benchmark_type  VARCHAR(100),
    asset_class     VARCHAR(50),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_benchmark_master_updated_at
    BEFORE UPDATE ON benchmark_master
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### `benchmark_nav_history`

```sql
CREATE TABLE benchmark_nav_history (
    benchmark_code  VARCHAR(50)    NOT NULL
                        REFERENCES benchmark_master (benchmark_code) ON DELETE CASCADE,
    nav_date        DATE           NOT NULL,
    index_value     NUMERIC(15, 4) NOT NULL,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (benchmark_code, nav_date)
);

CREATE INDEX ix_benchmark_nav_history_nav_date ON benchmark_nav_history (nav_date);
```

---

### `benchmark_metrics`

```sql
CREATE TABLE benchmark_metrics (
    benchmark_code       VARCHAR(50)    PRIMARY KEY
                             REFERENCES benchmark_master (benchmark_code) ON DELETE CASCADE,
    current_nav          NUMERIC(15, 4) NOT NULL,
    nav_date             DATE           NOT NULL,
    cagr_3year           NUMERIC(10, 4),
    cagr_5year           NUMERIC(10, 4),
    sortino_ratio        NUMERIC(10, 4),
    sharpe_ratio         NUMERIC(10, 4),
    standard_deviation   NUMERIC(10, 4),
    maximum_drawdown     NUMERIC(10, 4),
    metrics_calculated_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_benchmark_metrics_updated_at
    BEFORE UPDATE ON benchmark_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## STOCKS

All nine stock tables are kept exactly as coded. Same principle — no columns added or removed.

### `stocks`

```sql
CREATE TABLE stocks (
    id             SERIAL        PRIMARY KEY,
    symbol         VARCHAR(20)   NOT NULL UNIQUE,
    nse_symbol     VARCHAR(20),
    bse_code       VARCHAR(10),
    yf_symbol      VARCHAR(30)   NOT NULL,
    screener_slug  VARCHAR(50),
    company_name   VARCHAR(255)  NOT NULL,
    sector         VARCHAR(100),
    industry       VARCHAR(100),
    summary        VARCHAR(5000),
    market_cap_cat VARCHAR(50),
    is_index       BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    data_quality   VARCHAR(10)   NOT NULL DEFAULT 'OK',
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stocks_sector       ON stocks (sector);
CREATE INDEX idx_stocks_is_active    ON stocks (is_active);
CREATE INDEX idx_stocks_market_cap   ON stocks (market_cap_cat);

CREATE TRIGGER trg_stocks_updated_at
    BEFORE UPDATE ON stocks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

### `price_data`

```sql
CREATE TABLE price_data (
    id          BIGSERIAL      PRIMARY KEY,
    stock_id    INTEGER        NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    price_date  DATE           NOT NULL,
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4) NOT NULL,
    adj_close   NUMERIC(12, 4),
    volume      BIGINT,
    UNIQUE (stock_id, price_date)
);

CREATE INDEX ix_price_data_stock_date_desc ON price_data (stock_id, price_date DESC);
```

---

### `financial_statements`

```sql
CREATE TABLE financial_statements (
    id             SERIAL       PRIMARY KEY,
    stock_id       INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    statement_type VARCHAR(5)   NOT NULL,   -- 'PL' | 'BS' | 'CF'
    period_type    VARCHAR(10)  NOT NULL,   -- 'annual' | 'quarterly'
    period_end     DATE         NOT NULL,
    currency       VARCHAR(5)   NOT NULL DEFAULT 'INR',
    data           JSONB        NOT NULL,
    raw_data       JSONB,
    scraped_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    raw_checksum   VARCHAR(64),
    UNIQUE (stock_id, statement_type, period_type, period_end)
);

CREATE INDEX ix_financial_stmt_stock_period ON financial_statements (stock_id, period_end DESC);
```

---

### `financial_ratios`

```sql
CREATE TABLE financial_ratios (
    id               SERIAL        PRIMARY KEY,
    stock_id         INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    period_end       DATE          NOT NULL,
    period_type      VARCHAR(10)   NOT NULL,
    pe_ratio         NUMERIC(10, 3),
    pb_ratio         NUMERIC(10, 3),
    ps_ratio         NUMERIC(10, 3),
    ev_ebitda        NUMERIC(10, 3),
    peg_ratio        NUMERIC(10, 3),
    roe              NUMERIC(10, 3),
    roce             NUMERIC(10, 3),
    roa              NUMERIC(10, 3),
    gross_margin     NUMERIC(10, 3),
    ebitda_margin    NUMERIC(10, 3),
    operating_margin NUMERIC(10, 3),
    pat_margin       NUMERIC(10, 3),
    debt_equity      NUMERIC(10, 3),
    interest_cov     NUMERIC(10, 3),
    current_ratio    NUMERIC(10, 3),
    quick_ratio      NUMERIC(10, 3),
    revenue_growth   NUMERIC(10, 3),
    pat_growth       NUMERIC(10, 3),
    eps_growth       NUMERIC(10, 3),
    eps              NUMERIC(12, 4),
    book_value_ps    NUMERIC(12, 4),
    dividend_yield   NUMERIC(8, 4),
    dividend_per_share      NUMERIC(12, 4),
    dividend_payout_ratio   NUMERIC(10, 3),
    market_cap       NUMERIC(18, 4),
    ev_sales         NUMERIC(10, 3),
    net_debt         NUMERIC(18, 4),
    net_debt_ebitda  NUMERIC(10, 3),
    asset_turnover   NUMERIC(10, 3),
    inventory_turnover NUMERIC(10, 3),
    receivables_days NUMERIC(10, 3),
    payable_days     NUMERIC(10, 3),
    cash_conv_cycle  NUMERIC(10, 3),
    fcf              NUMERIC(18, 4),
    fcf_margin       NUMERIC(10, 3),
    fcf_yield        NUMERIC(10, 3),
    capex_to_revenue       NUMERIC(10, 3),
    capex_to_depreciation  NUMERIC(10, 3),
    piotroski_f_score      INTEGER,
    altman_z_score   NUMERIC(10, 3),
    roic             NUMERIC(10, 3),
    low_52w          NUMERIC(12, 4),
    high_52w         NUMERIC(12, 4),
    revenue_per_share NUMERIC(12, 4),
    cfo_to_pat       NUMERIC(10, 3),
    computed_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, period_end, period_type)
);
```

---

### `shareholding_pattern`

```sql
CREATE TABLE shareholding_pattern (
    id              SERIAL       PRIMARY KEY,
    stock_id        INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    period_end      DATE         NOT NULL,
    promoter_pct    NUMERIC(6, 3),
    fii_pct         NUMERIC(6, 3),
    dii_pct         NUMERIC(6, 3),
    public_pct      NUMERIC(6, 3),
    pledged_pct     NUMERIC(6, 3),
    promoter_change NUMERIC(6, 3),
    fii_change      NUMERIC(6, 3),
    scraped_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, period_end)
);

CREATE INDEX ix_shareholding_pattern_stock_period ON shareholding_pattern (stock_id, period_end DESC);
```

---

### `technical_indicators`

```sql
CREATE TABLE technical_indicators (
    id             BIGSERIAL     PRIMARY KEY,
    stock_id       INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    ind_date       DATE          NOT NULL,
    timeframe      VARCHAR(5)    NOT NULL,   -- '1d', '1w'
    sma_20         NUMERIC(12, 4),
    sma_50         NUMERIC(12, 4),
    sma_200        NUMERIC(12, 4),
    ema_9          NUMERIC(12, 4),
    ema_21         NUMERIC(12, 4),
    ema_50         NUMERIC(12, 4),
    rsi_14         NUMERIC(8, 4),
    macd_line      NUMERIC(12, 4),
    macd_signal    NUMERIC(12, 4),
    macd_hist      NUMERIC(12, 4),
    bb_upper       NUMERIC(12, 4),
    bb_middle      NUMERIC(12, 4),
    bb_lower       NUMERIC(12, 4),
    atr_14         NUMERIC(12, 4),
    adx_14         NUMERIC(8, 4),
    stoch_k        NUMERIC(8, 4),
    stoch_d        NUMERIC(8, 4),
    volume_sma_20  BIGINT,
    volume_sma_50  BIGINT,
    volume_ratio   NUMERIC(10, 3),
    obv            BIGINT,
    vwap_20        NUMERIC(12, 4),
    cci_20         NUMERIC(10, 3),
    williams_r     NUMERIC(10, 3),
    roc_14         NUMERIC(10, 3),
    beta_1y        NUMERIC(10, 4),
    rs_6m_vs_nifty    NUMERIC(10, 3),
    pct_from_52w_high NUMERIC(10, 3),
    pct_from_52w_low  NUMERIC(10, 3),
    UNIQUE (stock_id, ind_date, timeframe)
);

CREATE INDEX ix_technical_indicator_stock_date ON technical_indicators (stock_id, ind_date DESC);
```

---

### `detected_patterns`

```sql
CREATE TABLE detected_patterns (
    id             SERIAL       PRIMARY KEY,
    stock_id       INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    pattern_type   VARCHAR(30)  NOT NULL,
    timeframe      VARCHAR(5)   NOT NULL,
    detected_on    DATE         NOT NULL,
    pattern_start  DATE         NOT NULL,
    pattern_end    DATE         NOT NULL,
    breakout_level NUMERIC(12, 4),
    direction      VARCHAR(10),
    confidence     NUMERIC(4, 3),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    metadata       JSONB,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_detected_patterns_stock_active
    ON detected_patterns (stock_id, is_active, detected_on DESC);
```

---

### `stock_ratings`

```sql
CREATE TABLE stock_ratings (
    id                 SERIAL        PRIMARY KEY,
    stock_id           INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    rated_on           DATE          NOT NULL,
    total_score        NUMERIC(6, 3),
    rating_label       VARCHAR(15),
    fundamental_score  NUMERIC(6, 3),
    valuation_score    NUMERIC(6, 3),
    technical_score    NUMERIC(6, 3),
    momentum_score     NUMERIC(6, 3),
    quality_score      NUMERIC(6, 3),
    shareholding_score NUMERIC(6, 3),
    score_breakdown    JSONB,
    UNIQUE (stock_id, rated_on)
);

CREATE INDEX idx_stock_ratings_stock_date ON stock_ratings (stock_id, rated_on DESC);
```

---

### `fundamental_scores`

```sql
CREATE TABLE fundamental_scores (
    id                          SERIAL       PRIMARY KEY,
    stock_id                    INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    period_end                  DATE         NOT NULL,
    period_type                 VARCHAR(10)  NOT NULL,
    score_version               VARCHAR(10)  NOT NULL DEFAULT 'v1.0',
    pl_score                    NUMERIC(6, 3),
    bs_score                    NUMERIC(6, 3),
    cf_score                    NUMERIC(6, 3),
    pl_growth_score             NUMERIC(6, 3),
    pl_margin_score             NUMERIC(6, 3),
    pl_eps_score                NUMERIC(6, 3),
    pl_consistency_score        NUMERIC(6, 3),
    bs_leverage_score           NUMERIC(6, 3),
    bs_liquidity_score          NUMERIC(6, 3),
    bs_asset_score              NUMERIC(6, 3),
    bs_networth_score           NUMERIC(6, 3),
    cf_operating_score          NUMERIC(6, 3),
    cf_capex_score              NUMERIC(6, 3),
    cf_financing_score          NUMERIC(6, 3),
    composite_fundamental_score NUMERIC(6, 3),
    reasoning_label             VARCHAR(50),
    reasoning_text              TEXT,
    computed_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, period_end, score_version)
);

CREATE INDEX ix_fundamental_scores_stock_id ON fundamental_scores (stock_id);
```

---

## Full Setup SQL

Run this in Supabase's SQL editor in order.

```sql
-- ─────────────────────────────────────────────────────────────
-- STEP 0: Extensions and shared trigger function
-- ─────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ─────────────────────────────────────────────────────────────
-- STEP 1: Auth
-- ─────────────────────────────────────────────────────────────

CREATE TABLE admin_users (
    user_id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    username         VARCHAR(50)  NOT NULL UNIQUE,
    email            VARCHAR(255) NOT NULL UNIQUE,
    hashed_password  VARCHAR(255) NOT NULL,
    user_role        VARCHAR(20)  NOT NULL DEFAULT 'analyst'
                         CHECK (user_role IN ('admin', 'analyst', 'service')),
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login_at    TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_admin_users_role ON admin_users (user_role);
CREATE TRIGGER trg_admin_users_updated_at BEFORE UPDATE ON admin_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_only" ON admin_users USING (auth.role() = 'service_role');


-- ─────────────────────────────────────────────────────────────
-- STEP 2: ETL
-- ─────────────────────────────────────────────────────────────

CREATE TABLE etl_runs (
    id            BIGSERIAL    PRIMARY KEY,
    pipeline_name VARCHAR(60)  NOT NULL,
    entity_id     VARCHAR(50),
    status        VARCHAR(10)  NOT NULL DEFAULT 'RUNNING'
                      CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'PARTIAL')),
    triggered_by  VARCHAR(20)  NOT NULL DEFAULT 'scheduler'
                      CHECK (triggered_by IN ('scheduler', 'manual', 'backfill')),
    started_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ended_at      TIMESTAMPTZ,
    records_in    INTEGER      NOT NULL DEFAULT 0,
    records_out   INTEGER      NOT NULL DEFAULT 0,
    error_msg     TEXT,
    metadata      JSONB
);
CREATE UNIQUE INDEX uq_etl_runs_running
    ON etl_runs (pipeline_name, COALESCE(entity_id, '')) WHERE status = 'RUNNING';
CREATE INDEX idx_etl_runs_pipeline_started ON etl_runs (pipeline_name, started_at DESC);
CREATE INDEX idx_etl_runs_status           ON etl_runs (status, started_at DESC);


-- ─────────────────────────────────────────────────────────────
-- STEP 3: Mutual Funds
-- ─────────────────────────────────────────────────────────────

CREATE TABLE fund_master (
    scheme_code           VARCHAR(50)  PRIMARY KEY,
    scheme_name           VARCHAR(500) NOT NULL,
    amc_name              VARCHAR(200) NOT NULL,
    inception_date        DATE         NOT NULL,
    plan_type             VARCHAR(20)  NOT NULL,
    scheme_category       VARCHAR(100) NOT NULL,
    scheme_subcategory    VARCHAR(100),
    benchmark_index_code  VARCHAR(50),
    isin                  VARCHAR(50)  UNIQUE,
    manager_experience    VARCHAR(500),
    is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_fund_master_amc_name_trgm ON fund_master
    USING GIN (amc_name gin_trgm_ops);
CREATE INDEX ix_fund_master_scheme_category_trgm ON fund_master
    USING GIN (scheme_category gin_trgm_ops);
CREATE INDEX ix_fund_master_plan_type ON fund_master (plan_type);
CREATE INDEX ix_fund_master_is_active ON fund_master (is_active);
CREATE TRIGGER trg_fund_master_updated_at BEFORE UPDATE ON fund_master
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE fund_nav_history (
    scheme_code  VARCHAR(50)    NOT NULL REFERENCES fund_master (scheme_code) ON DELETE CASCADE,
    nav_date     DATE           NOT NULL,
    nav_value    NUMERIC(15, 4) NOT NULL,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scheme_code, nav_date)
);
CREATE INDEX ix_fund_nav_history_nav_date ON fund_nav_history (nav_date);

CREATE TABLE fund_metrics (
    scheme_code                   VARCHAR(50)    PRIMARY KEY
                                      REFERENCES fund_master (scheme_code) ON DELETE CASCADE,
    current_nav                   NUMERIC(15, 4) NOT NULL,
    nav_date                      DATE           NOT NULL,
    aum_in_crores                 NUMERIC(18, 2),
    expense_ratio                 NUMERIC(5, 4),
    fund_rating                   NUMERIC(5, 2),
    volatility                    NUMERIC(10, 4),
    cagr_3year                    NUMERIC(10, 4),
    cagr_5year                    NUMERIC(10, 4),
    absolute_return_1y            NUMERIC(10, 4),
    absolute_return_3y            NUMERIC(10, 4),
    absolute_return_5y            NUMERIC(10, 4),
    absolute_return_10y           NUMERIC(10, 4),
    short_term_return_6m          NUMERIC(10, 4),
    upside_capture                NUMERIC(10, 4),
    downside_capture              NUMERIC(10, 4),
    sortino_ratio                 NUMERIC(10, 4),
    sharpe_ratio                  NUMERIC(10, 4),
    alpha                         NUMERIC(10, 4),
    beta                          NUMERIC(10, 4),
    standard_deviation            NUMERIC(10, 4),
    maximum_drawdown              NUMERIC(10, 4),
    tracking_error                NUMERIC(10, 4),
    information_ratio             NUMERIC(10, 4),
    metrics_calculated_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    calculation_period_start_date DATE,
    calculation_period_end_date   DATE,
    has_sufficient_data           BOOLEAN        NOT NULL DEFAULT TRUE,
    data_completeness_percentage  NUMERIC(5, 2),
    final_verdict                 VARCHAR(1000),
    updated_at                    TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_fund_metrics_updated_at BEFORE UPDATE ON fund_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE benchmark_master (
    benchmark_code  VARCHAR(50)  PRIMARY KEY,
    benchmark_name  VARCHAR(200) NOT NULL,
    ticker          VARCHAR(50)  NOT NULL,
    benchmark_type  VARCHAR(100),
    asset_class     VARCHAR(50),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_benchmark_master_updated_at BEFORE UPDATE ON benchmark_master
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE benchmark_nav_history (
    benchmark_code  VARCHAR(50)    NOT NULL
                        REFERENCES benchmark_master (benchmark_code) ON DELETE CASCADE,
    nav_date        DATE           NOT NULL,
    index_value     NUMERIC(15, 4) NOT NULL,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (benchmark_code, nav_date)
);
CREATE INDEX ix_benchmark_nav_history_nav_date ON benchmark_nav_history (nav_date);

CREATE TABLE benchmark_metrics (
    benchmark_code        VARCHAR(50)    PRIMARY KEY
                              REFERENCES benchmark_master (benchmark_code) ON DELETE CASCADE,
    current_nav           NUMERIC(15, 4) NOT NULL,
    nav_date              DATE           NOT NULL,
    cagr_3year            NUMERIC(10, 4),
    cagr_5year            NUMERIC(10, 4),
    sortino_ratio         NUMERIC(10, 4),
    sharpe_ratio          NUMERIC(10, 4),
    standard_deviation    NUMERIC(10, 4),
    maximum_drawdown      NUMERIC(10, 4),
    metrics_calculated_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_benchmark_metrics_updated_at BEFORE UPDATE ON benchmark_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ─────────────────────────────────────────────────────────────
-- STEP 4: Stocks
-- ─────────────────────────────────────────────────────────────

CREATE TABLE stocks (
    id             SERIAL        PRIMARY KEY,
    symbol         VARCHAR(20)   NOT NULL UNIQUE,
    nse_symbol     VARCHAR(20),
    bse_code       VARCHAR(10),
    yf_symbol      VARCHAR(30)   NOT NULL,
    screener_slug  VARCHAR(50),
    company_name   VARCHAR(255)  NOT NULL,
    sector         VARCHAR(100),
    industry       VARCHAR(100),
    summary        VARCHAR(5000),
    market_cap_cat VARCHAR(50),
    is_index       BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    data_quality   VARCHAR(10)   NOT NULL DEFAULT 'OK',
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_stocks_sector     ON stocks (sector);
CREATE INDEX idx_stocks_is_active  ON stocks (is_active);
CREATE TRIGGER trg_stocks_updated_at BEFORE UPDATE ON stocks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE price_data (
    id          BIGSERIAL      PRIMARY KEY,
    stock_id    INTEGER        NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    price_date  DATE           NOT NULL,
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4) NOT NULL,
    adj_close   NUMERIC(12, 4),
    volume      BIGINT,
    UNIQUE (stock_id, price_date)
);
CREATE INDEX ix_price_data_stock_date_desc ON price_data (stock_id, price_date DESC);

CREATE TABLE financial_statements (
    id             SERIAL       PRIMARY KEY,
    stock_id       INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    statement_type VARCHAR(5)   NOT NULL,
    period_type    VARCHAR(10)  NOT NULL,
    period_end     DATE         NOT NULL,
    currency       VARCHAR(5)   NOT NULL DEFAULT 'INR',
    data           JSONB        NOT NULL,
    raw_data       JSONB,
    scraped_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    raw_checksum   VARCHAR(64),
    UNIQUE (stock_id, statement_type, period_type, period_end)
);
CREATE INDEX ix_financial_stmt_stock_period ON financial_statements (stock_id, period_end DESC);

CREATE TABLE financial_ratios (
    id                     SERIAL        PRIMARY KEY,
    stock_id               INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    period_end             DATE          NOT NULL,
    period_type            VARCHAR(10)   NOT NULL,
    pe_ratio               NUMERIC(10, 3),
    pb_ratio               NUMERIC(10, 3),
    ps_ratio               NUMERIC(10, 3),
    ev_ebitda              NUMERIC(10, 3),
    peg_ratio              NUMERIC(10, 3),
    roe                    NUMERIC(10, 3),
    roce                   NUMERIC(10, 3),
    roa                    NUMERIC(10, 3),
    gross_margin           NUMERIC(10, 3),
    ebitda_margin          NUMERIC(10, 3),
    operating_margin       NUMERIC(10, 3),
    pat_margin             NUMERIC(10, 3),
    debt_equity            NUMERIC(10, 3),
    interest_cov           NUMERIC(10, 3),
    current_ratio          NUMERIC(10, 3),
    quick_ratio            NUMERIC(10, 3),
    revenue_growth         NUMERIC(10, 3),
    pat_growth             NUMERIC(10, 3),
    eps_growth             NUMERIC(10, 3),
    eps                    NUMERIC(12, 4),
    book_value_ps          NUMERIC(12, 4),
    dividend_yield         NUMERIC(8, 4),
    dividend_per_share     NUMERIC(12, 4),
    dividend_payout_ratio  NUMERIC(10, 3),
    market_cap             NUMERIC(18, 4),
    ev_sales               NUMERIC(10, 3),
    net_debt               NUMERIC(18, 4),
    net_debt_ebitda        NUMERIC(10, 3),
    asset_turnover         NUMERIC(10, 3),
    inventory_turnover     NUMERIC(10, 3),
    receivables_days       NUMERIC(10, 3),
    payable_days           NUMERIC(10, 3),
    cash_conv_cycle        NUMERIC(10, 3),
    fcf                    NUMERIC(18, 4),
    fcf_margin             NUMERIC(10, 3),
    fcf_yield              NUMERIC(10, 3),
    capex_to_revenue       NUMERIC(10, 3),
    capex_to_depreciation  NUMERIC(10, 3),
    piotroski_f_score      INTEGER,
    altman_z_score         NUMERIC(10, 3),
    roic                   NUMERIC(10, 3),
    low_52w                NUMERIC(12, 4),
    high_52w               NUMERIC(12, 4),
    revenue_per_share      NUMERIC(12, 4),
    cfo_to_pat             NUMERIC(10, 3),
    computed_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, period_end, period_type)
);

CREATE TABLE shareholding_pattern (
    id              SERIAL       PRIMARY KEY,
    stock_id        INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    period_end      DATE         NOT NULL,
    promoter_pct    NUMERIC(6, 3),
    fii_pct         NUMERIC(6, 3),
    dii_pct         NUMERIC(6, 3),
    public_pct      NUMERIC(6, 3),
    pledged_pct     NUMERIC(6, 3),
    promoter_change NUMERIC(6, 3),
    fii_change      NUMERIC(6, 3),
    scraped_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, period_end)
);
CREATE INDEX ix_shareholding_pattern_stock_period
    ON shareholding_pattern (stock_id, period_end DESC);

CREATE TABLE technical_indicators (
    id                BIGSERIAL     PRIMARY KEY,
    stock_id          INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    ind_date          DATE          NOT NULL,
    timeframe         VARCHAR(5)    NOT NULL,
    sma_20            NUMERIC(12, 4),
    sma_50            NUMERIC(12, 4),
    sma_200           NUMERIC(12, 4),
    ema_9             NUMERIC(12, 4),
    ema_21            NUMERIC(12, 4),
    ema_50            NUMERIC(12, 4),
    rsi_14            NUMERIC(8, 4),
    macd_line         NUMERIC(12, 4),
    macd_signal       NUMERIC(12, 4),
    macd_hist         NUMERIC(12, 4),
    bb_upper          NUMERIC(12, 4),
    bb_middle         NUMERIC(12, 4),
    bb_lower          NUMERIC(12, 4),
    atr_14            NUMERIC(12, 4),
    adx_14            NUMERIC(8, 4),
    stoch_k           NUMERIC(8, 4),
    stoch_d           NUMERIC(8, 4),
    volume_sma_20     BIGINT,
    volume_sma_50     BIGINT,
    volume_ratio      NUMERIC(10, 3),
    obv               BIGINT,
    vwap_20           NUMERIC(12, 4),
    cci_20            NUMERIC(10, 3),
    williams_r        NUMERIC(10, 3),
    roc_14            NUMERIC(10, 3),
    beta_1y           NUMERIC(10, 4),
    rs_6m_vs_nifty    NUMERIC(10, 3),
    pct_from_52w_high NUMERIC(10, 3),
    pct_from_52w_low  NUMERIC(10, 3),
    UNIQUE (stock_id, ind_date, timeframe)
);
CREATE INDEX ix_technical_indicator_stock_date
    ON technical_indicators (stock_id, ind_date DESC);

CREATE TABLE detected_patterns (
    id             SERIAL       PRIMARY KEY,
    stock_id       INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    pattern_type   VARCHAR(30)  NOT NULL,
    timeframe      VARCHAR(5)   NOT NULL,
    detected_on    DATE         NOT NULL,
    pattern_start  DATE         NOT NULL,
    pattern_end    DATE         NOT NULL,
    breakout_level NUMERIC(12, 4),
    direction      VARCHAR(10),
    confidence     NUMERIC(4, 3),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    metadata       JSONB,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, pattern_type, detected_on)
);
CREATE INDEX idx_detected_patterns_active
    ON detected_patterns (stock_id, is_active, detected_on DESC);

CREATE TABLE stock_ratings (
    id                 SERIAL        PRIMARY KEY,
    stock_id           INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    rated_on           DATE          NOT NULL,
    total_score        NUMERIC(6, 3),
    rating_label       VARCHAR(15),
    fundamental_score  NUMERIC(6, 3),
    valuation_score    NUMERIC(6, 3),
    technical_score    NUMERIC(6, 3),
    momentum_score     NUMERIC(6, 3),
    quality_score      NUMERIC(6, 3),
    shareholding_score NUMERIC(6, 3),
    score_breakdown    JSONB,
    UNIQUE (stock_id, rated_on)
);
CREATE INDEX idx_stock_ratings_stock_date ON stock_ratings (stock_id, rated_on DESC);

CREATE TABLE fundamental_scores (
    id                          SERIAL       PRIMARY KEY,
    stock_id                    INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
    period_end                  DATE         NOT NULL,
    period_type                 VARCHAR(10)  NOT NULL,
    score_version               VARCHAR(10)  NOT NULL DEFAULT 'v1.0',
    pl_score                    NUMERIC(6, 3),
    bs_score                    NUMERIC(6, 3),
    cf_score                    NUMERIC(6, 3),
    pl_growth_score             NUMERIC(6, 3),
    pl_margin_score             NUMERIC(6, 3),
    pl_eps_score                NUMERIC(6, 3),
    pl_consistency_score        NUMERIC(6, 3),
    bs_leverage_score           NUMERIC(6, 3),
    bs_liquidity_score          NUMERIC(6, 3),
    bs_asset_score              NUMERIC(6, 3),
    bs_networth_score           NUMERIC(6, 3),
    cf_operating_score          NUMERIC(6, 3),
    cf_capex_score              NUMERIC(6, 3),
    cf_financing_score          NUMERIC(6, 3),
    composite_fundamental_score NUMERIC(6, 3),
    reasoning_label             VARCHAR(50),
    reasoning_text              TEXT,
    computed_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, period_end, score_version)
);
CREATE INDEX ix_fundamental_scores_stock_id ON fundamental_scores (stock_id);
```

---

## Alembic Migration Order

```
001_base_extensions_trigger.py     -- extensions + update_updated_at_column()
002_admin_users.py                 -- admin_users
003_etl_runs.py                    -- etl_runs
004_fund_master.py                 -- fund_master
005_fund_nav_history.py            -- fund_nav_history
006_fund_metrics.py                -- fund_metrics
007_benchmark_master.py            -- benchmark_master
008_benchmark_nav_history.py       -- benchmark_nav_history
009_benchmark_metrics.py           -- benchmark_metrics
010_stocks.py                      -- stocks
011_price_data.py                  -- price_data
012_financial_statements.py        -- financial_statements
013_financial_ratios.py            -- financial_ratios
014_shareholding_pattern.py        -- shareholding_pattern
015_technical_indicators.py        -- technical_indicators
016_detected_patterns.py           -- detected_patterns
017_stock_ratings.py               -- stock_ratings
018_fundamental_scores.py          -- fundamental_scores
019_migrate_sync_jobs.py           -- copy sync_jobs → etl_runs, then drop sync_jobs
020_migrate_pipeline_audit.py      -- copy pipeline_audit → etl_runs, then drop pipeline_audit
```

---

## What Changed vs the Existing Code — Summary

| Existing | Change | Reason |
|---|---|---|
| `TIMESTAMP` everywhere | → `TIMESTAMPTZ` | Supabase stores in UTC; IST-scheduled jobs need timezone-aware timestamps |
| `sync_jobs` | Consolidated into `etl_runs` | Avoid two tables solving the same problem for two domains |
| `pipeline_audit` | Consolidated into `etl_runs` | Same reason — unified view of all job runs |
| Column names | **Unchanged** | Your `crud.py` and routers reference these directly |
| All indexes | **Preserved** | Existing indexes are correct — nothing removed |
| `metadata_` column alias | Normalised to `metadata` | SQLAlchemy alias was working around a reserved word; in raw SQL `metadata` is fine |

---

*Phase 1 Database Design · dev branch baseline · May 2026*
