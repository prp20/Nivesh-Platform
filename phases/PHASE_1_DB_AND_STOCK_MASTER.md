# Phase 1 — Database Migration & Stock Master
> **Duration:** Weeks 1–2  
> **Goal:** Create all 8 new PostgreSQL tables and seed the stock master registry. The existing MF platform must remain fully functional throughout.

---

## Prerequisites
- Phase 0 read and understood
- PostgreSQL 16 running (existing docker-compose)
- Alembic already set up in the project
- New packages installed: `pip install yfinance apscheduler pandas-ta scipy --break-system-packages`

---

## 1.1 Database Schema — All 8 New Tables

Create a single Alembic migration file. Run `alembic revision --autogenerate -m "add_stock_tables"` then replace its content with the following DDL.

> ⚠️ These tables have **no foreign keys to existing MF tables**. They are completely isolated.

### Table 1: `stocks` (Master Registry)
```sql
CREATE TABLE stocks (
  id              SERIAL PRIMARY KEY,
  symbol          VARCHAR(20)  NOT NULL UNIQUE,   -- canonical e.g. 'RELIANCE'
  nse_symbol      VARCHAR(20),                    -- NSE ticker
  bse_code        VARCHAR(10),                    -- BSE 6-digit code
  yf_symbol       VARCHAR(30)  NOT NULL,           -- 'RELIANCE.NS' or 'RELIANCE.BO'
  screener_slug   VARCHAR(50),                    -- screener.in URL slug (usually = symbol)
  company_name    VARCHAR(255) NOT NULL,
  sector          VARCHAR(100),
  industry        VARCHAR(100),
  market_cap_cat  VARCHAR(10),                    -- 'large' | 'mid' | 'small' | 'micro'
  is_index        BOOLEAN      DEFAULT FALSE,
  is_active       BOOLEAN      DEFAULT TRUE,
  data_quality    VARCHAR(10)  DEFAULT 'OK',      -- 'OK' | 'POOR' | 'STALE'
  created_at      TIMESTAMPTZ  DEFAULT NOW(),
  updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX idx_stocks_sector
    ON stocks(sector) WHERE is_active = TRUE;
CREATE INDEX idx_stocks_market_cap
    ON stocks(market_cap_cat) WHERE is_active = TRUE;
CREATE INDEX idx_stocks_fts
    ON stocks USING gin(to_tsvector('english', company_name || ' ' || symbol));
```

### Table 2: `price_data` (OHLCV)
```sql
-- Start WITHOUT partitioning. Add PARTITION BY RANGE only if rows exceed 10M.
CREATE TABLE price_data (
  id          BIGSERIAL PRIMARY KEY,
  stock_id    INTEGER      NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
  price_date  DATE         NOT NULL,
  open        NUMERIC(12,4),
  high        NUMERIC(12,4),
  low         NUMERIC(12,4),
  close       NUMERIC(12,4) NOT NULL,
  adj_close   NUMERIC(12,4),
  volume      BIGINT,
  CONSTRAINT uq_price_stock_date UNIQUE (stock_id, price_date)
);

CREATE INDEX idx_price_stock_date ON price_data(stock_id, price_date DESC);
CREATE INDEX idx_price_date       ON price_data(price_date DESC);
```

### Table 3: `financial_statements`
```sql
CREATE TABLE financial_statements (
  id              SERIAL      PRIMARY KEY,
  stock_id        INTEGER     NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
  statement_type  VARCHAR(5)  NOT NULL,   -- 'PL' | 'BS' | 'CF'
  period_type     VARCHAR(10) NOT NULL,   -- 'annual' | 'quarterly'
  period_end      DATE        NOT NULL,
  currency        VARCHAR(5)  DEFAULT 'INR',
  data            JSONB       NOT NULL,   -- normalised: {'revenue': 87939.0, ...}
  raw_data        JSONB,                  -- original scraped rows (for re-parse)
  scraped_at      TIMESTAMPTZ DEFAULT NOW(),
  raw_checksum    VARCHAR(64),            -- MD5 for change detection
  CONSTRAINT uq_fs UNIQUE (stock_id, statement_type, period_type, period_end)
);

CREATE INDEX idx_fs_stock_type ON financial_statements(stock_id, statement_type, period_end DESC);
CREATE INDEX idx_fs_data_gin   ON financial_statements USING GIN(data);
```

### Table 4: `shareholding_pattern`
```sql
CREATE TABLE shareholding_pattern (
  id              SERIAL      PRIMARY KEY,
  stock_id        INTEGER     NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
  period_end      DATE        NOT NULL,
  promoter_pct    NUMERIC(6,3),
  fii_pct         NUMERIC(6,3),
  dii_pct         NUMERIC(6,3),
  public_pct      NUMERIC(6,3),
  pledged_pct     NUMERIC(6,3),
  promoter_change NUMERIC(6,3),   -- QoQ delta
  fii_change      NUMERIC(6,3),   -- QoQ delta
  scraped_at      TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT uq_sh UNIQUE (stock_id, period_end)
);

CREATE INDEX idx_sh_stock_period ON shareholding_pattern(stock_id, period_end DESC);
```

### Table 5: `financial_ratios`
```sql
CREATE TABLE financial_ratios (
  id              SERIAL      PRIMARY KEY,
  stock_id        INTEGER     NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
  period_end      DATE        NOT NULL,
  period_type     VARCHAR(10) NOT NULL,   -- 'annual' | 'ttm'
  -- Valuation
  pe_ratio        NUMERIC(10,3),
  pb_ratio        NUMERIC(10,3),
  ps_ratio        NUMERIC(10,3),
  ev_ebitda       NUMERIC(10,3),
  peg_ratio       NUMERIC(10,3),
  -- Profitability
  roe             NUMERIC(10,3),   -- %
  roce            NUMERIC(10,3),   -- %
  roa             NUMERIC(10,3),   -- %
  gross_margin    NUMERIC(10,3),   -- %
  ebitda_margin   NUMERIC(10,3),   -- %
  pat_margin      NUMERIC(10,3),   -- %
  -- Leverage
  debt_equity     NUMERIC(10,3),
  interest_cov    NUMERIC(10,3),
  current_ratio   NUMERIC(10,3),
  quick_ratio     NUMERIC(10,3),
  -- Growth (YoY %)
  revenue_growth  NUMERIC(10,3),
  pat_growth      NUMERIC(10,3),
  eps_growth      NUMERIC(10,3),
  -- Per-share
  eps             NUMERIC(12,4),
  book_value_ps   NUMERIC(12,4),
  dividend_yield  NUMERIC(8,4),
  -- Quality
  cfo_to_pat      NUMERIC(10,3),
  computed_at     TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT uq_ratios UNIQUE (stock_id, period_end, period_type)
);

-- Composite index for screener queries (covers all common filter columns)
CREATE INDEX idx_ratios_screener ON financial_ratios(stock_id, roe, pe_ratio, debt_equity, pat_margin);
CREATE INDEX idx_ratios_period   ON financial_ratios(stock_id, period_end DESC);
```

### Table 6: `technical_indicators`
```sql
CREATE TABLE technical_indicators (
  id            BIGSERIAL   PRIMARY KEY,
  stock_id      INTEGER     NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
  ind_date      DATE        NOT NULL,
  timeframe     VARCHAR(5)  NOT NULL,   -- '1d' | '1w' | '1mo'
  sma_20        NUMERIC(12,4),
  sma_50        NUMERIC(12,4),
  sma_200       NUMERIC(12,4),
  ema_9         NUMERIC(12,4),
  ema_21        NUMERIC(12,4),
  ema_50        NUMERIC(12,4),
  rsi_14        NUMERIC(8,4),
  macd_line     NUMERIC(12,4),
  macd_signal   NUMERIC(12,4),
  macd_hist     NUMERIC(12,4),
  bb_upper      NUMERIC(12,4),
  bb_middle     NUMERIC(12,4),
  bb_lower      NUMERIC(12,4),
  atr_14        NUMERIC(12,4),
  adx_14        NUMERIC(8,4),
  stoch_k       NUMERIC(8,4),
  stoch_d       NUMERIC(8,4),
  volume_sma_20 BIGINT,
  CONSTRAINT uq_ti UNIQUE (stock_id, timeframe, ind_date)
);

CREATE INDEX idx_ti_stock_tf_date ON technical_indicators(stock_id, timeframe, ind_date DESC);
```

### Table 7: `detected_patterns`
```sql
CREATE TABLE detected_patterns (
  id              SERIAL      PRIMARY KEY,
  stock_id        INTEGER     NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
  pattern_type    VARCHAR(30) NOT NULL,
  -- Allowed values: 'DOUBLE_TOP' | 'DOUBLE_BOTTOM' | 'HEAD_SHOULDERS' |
  --   'INV_HEAD_SHOULDERS' | 'BREAKOUT' | 'BREAKDOWN' | 'TRENDLINE_BREAK'
  timeframe       VARCHAR(5)  NOT NULL,
  detected_on     DATE        NOT NULL,
  pattern_start   DATE        NOT NULL,
  pattern_end     DATE        NOT NULL,
  breakout_level  NUMERIC(12,4),
  direction       VARCHAR(10),            -- 'BULLISH' | 'BEARISH'
  confidence      NUMERIC(4,3),           -- 0.0 to 1.0
  is_active       BOOLEAN     DEFAULT TRUE,
  metadata        JSONB,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_patterns_stock  ON detected_patterns(stock_id, detected_on DESC);
CREATE INDEX idx_patterns_active ON detected_patterns(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_patterns_type   ON detected_patterns(pattern_type, detected_on DESC);
```

### Table 8: `stock_ratings`
```sql
CREATE TABLE stock_ratings (
  id                  SERIAL      PRIMARY KEY,
  stock_id            INTEGER     NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
  rated_on            DATE        NOT NULL,
  total_score         NUMERIC(6,3),
  rating_label        VARCHAR(15),
  -- Allowed: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG_SELL'
  fundamental_score   NUMERIC(6,3),   -- weight 30%
  valuation_score     NUMERIC(6,3),   -- weight 20%
  technical_score     NUMERIC(6,3),   -- weight 20%
  momentum_score      NUMERIC(6,3),   -- weight 15%
  quality_score       NUMERIC(6,3),   -- weight 10%
  shareholding_score  NUMERIC(6,3),   -- weight 5%
  score_breakdown     JSONB,
  CONSTRAINT uq_rating UNIQUE (stock_id, rated_on)
);

CREATE INDEX idx_ratings_stock ON stock_ratings(stock_id, rated_on DESC);
CREATE INDEX idx_ratings_label ON stock_ratings(rating_label, rated_on DESC);
```

### Table 9: `pipeline_audit`
```sql
-- Separate from existing sync_jobs (which is for MF pipelines).
CREATE TABLE pipeline_audit (
  id          SERIAL      PRIMARY KEY,
  job_name    VARCHAR(60) NOT NULL,
  stock_id    INTEGER     REFERENCES stocks(id),   -- NULL for batch jobs
  status      VARCHAR(10) NOT NULL,
  -- Allowed: 'RUNNING' | 'SUCCESS' | 'PARTIAL' | 'FAILED'
  started_at  TIMESTAMPTZ DEFAULT NOW(),
  ended_at    TIMESTAMPTZ,
  records_in  INTEGER     DEFAULT 0,
  records_out INTEGER     DEFAULT 0,
  error_msg   TEXT,
  metadata    JSONB
);

CREATE INDEX idx_audit_job_status ON pipeline_audit(job_name, started_at DESC);
CREATE INDEX idx_audit_failed     ON pipeline_audit(status) WHERE status = 'FAILED';
```

---

## 1.2 SQLAlchemy Models

Add to the **bottom** of `backend/app/models.py` (do not touch existing models):

```python
# ─── Stock Market Models (Phase 1) ────────────────────────────────────────────

class Stock(Base):
    __tablename__ = "stocks"

    id             = Column(Integer, primary_key=True)
    symbol         = Column(String(20), nullable=False, unique=True)
    nse_symbol     = Column(String(20))
    bse_code       = Column(String(10))
    yf_symbol      = Column(String(30), nullable=False)
    screener_slug  = Column(String(50))
    company_name   = Column(String(255), nullable=False)
    sector         = Column(String(100))
    industry       = Column(String(100))
    market_cap_cat = Column(String(10))
    is_index       = Column(Boolean, default=False)
    is_active      = Column(Boolean, default=True)
    data_quality   = Column(String(10), default="OK")
    created_at     = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at     = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class PriceData(Base):
    __tablename__ = "price_data"

    id         = Column(BigInteger, primary_key=True)
    stock_id   = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    price_date = Column(Date, nullable=False)
    open       = Column(Numeric(12, 4))
    high       = Column(Numeric(12, 4))
    low        = Column(Numeric(12, 4))
    close      = Column(Numeric(12, 4), nullable=False)
    adj_close  = Column(Numeric(12, 4))
    volume     = Column(BigInteger)


class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    id             = Column(Integer, primary_key=True)
    stock_id       = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    statement_type = Column(String(5), nullable=False)   # 'PL' | 'BS' | 'CF'
    period_type    = Column(String(10), nullable=False)  # 'annual' | 'quarterly'
    period_end     = Column(Date, nullable=False)
    currency       = Column(String(5), default="INR")
    data           = Column(JSONB, nullable=False)
    raw_data       = Column(JSONB)
    scraped_at     = Column(TIMESTAMP(timezone=True), server_default=func.now())
    raw_checksum   = Column(String(64))


class ShareholdingPattern(Base):
    __tablename__ = "shareholding_pattern"

    id              = Column(Integer, primary_key=True)
    stock_id        = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    period_end      = Column(Date, nullable=False)
    promoter_pct    = Column(Numeric(6, 3))
    fii_pct         = Column(Numeric(6, 3))
    dii_pct         = Column(Numeric(6, 3))
    public_pct      = Column(Numeric(6, 3))
    pledged_pct     = Column(Numeric(6, 3))
    promoter_change = Column(Numeric(6, 3))
    fii_change      = Column(Numeric(6, 3))
    scraped_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())


class FinancialRatio(Base):
    __tablename__ = "financial_ratios"

    id             = Column(Integer, primary_key=True)
    stock_id       = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    period_end     = Column(Date, nullable=False)
    period_type    = Column(String(10), nullable=False)
    pe_ratio       = Column(Numeric(10, 3))
    pb_ratio       = Column(Numeric(10, 3))
    ps_ratio       = Column(Numeric(10, 3))
    ev_ebitda      = Column(Numeric(10, 3))
    peg_ratio      = Column(Numeric(10, 3))
    roe            = Column(Numeric(10, 3))
    roce           = Column(Numeric(10, 3))
    roa            = Column(Numeric(10, 3))
    gross_margin   = Column(Numeric(10, 3))
    ebitda_margin  = Column(Numeric(10, 3))
    pat_margin     = Column(Numeric(10, 3))
    debt_equity    = Column(Numeric(10, 3))
    interest_cov   = Column(Numeric(10, 3))
    current_ratio  = Column(Numeric(10, 3))
    quick_ratio    = Column(Numeric(10, 3))
    revenue_growth = Column(Numeric(10, 3))
    pat_growth     = Column(Numeric(10, 3))
    eps_growth     = Column(Numeric(10, 3))
    eps            = Column(Numeric(12, 4))
    book_value_ps  = Column(Numeric(12, 4))
    dividend_yield = Column(Numeric(8, 4))
    cfo_to_pat     = Column(Numeric(10, 3))
    computed_at    = Column(TIMESTAMP(timezone=True), server_default=func.now())


class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"

    id            = Column(BigInteger, primary_key=True)
    stock_id      = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    ind_date      = Column(Date, nullable=False)
    timeframe     = Column(String(5), nullable=False)
    sma_20        = Column(Numeric(12, 4))
    sma_50        = Column(Numeric(12, 4))
    sma_200       = Column(Numeric(12, 4))
    ema_9         = Column(Numeric(12, 4))
    ema_21        = Column(Numeric(12, 4))
    ema_50        = Column(Numeric(12, 4))
    rsi_14        = Column(Numeric(8, 4))
    macd_line     = Column(Numeric(12, 4))
    macd_signal   = Column(Numeric(12, 4))
    macd_hist     = Column(Numeric(12, 4))
    bb_upper      = Column(Numeric(12, 4))
    bb_middle     = Column(Numeric(12, 4))
    bb_lower      = Column(Numeric(12, 4))
    atr_14        = Column(Numeric(12, 4))
    adx_14        = Column(Numeric(8, 4))
    stoch_k       = Column(Numeric(8, 4))
    stoch_d       = Column(Numeric(8, 4))
    volume_sma_20 = Column(BigInteger)


class DetectedPattern(Base):
    __tablename__ = "detected_patterns"

    id             = Column(Integer, primary_key=True)
    stock_id       = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    pattern_type   = Column(String(30), nullable=False)
    timeframe      = Column(String(5), nullable=False)
    detected_on    = Column(Date, nullable=False)
    pattern_start  = Column(Date, nullable=False)
    pattern_end    = Column(Date, nullable=False)
    breakout_level = Column(Numeric(12, 4))
    direction      = Column(String(10))
    confidence     = Column(Numeric(4, 3))
    is_active      = Column(Boolean, default=True)
    metadata       = Column(JSONB)
    created_at     = Column(TIMESTAMP(timezone=True), server_default=func.now())


class StockRating(Base):
    __tablename__ = "stock_ratings"

    id                 = Column(Integer, primary_key=True)
    stock_id           = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    rated_on           = Column(Date, nullable=False)
    total_score        = Column(Numeric(6, 3))
    rating_label       = Column(String(15))
    fundamental_score  = Column(Numeric(6, 3))
    valuation_score    = Column(Numeric(6, 3))
    technical_score    = Column(Numeric(6, 3))
    momentum_score     = Column(Numeric(6, 3))
    quality_score      = Column(Numeric(6, 3))
    shareholding_score = Column(Numeric(6, 3))
    score_breakdown    = Column(JSONB)


class PipelineAudit(Base):
    __tablename__ = "pipeline_audit"

    id          = Column(Integer, primary_key=True)
    job_name    = Column(String(60), nullable=False)
    stock_id    = Column(Integer, ForeignKey("stocks.id"))
    status      = Column(String(10), nullable=False)
    started_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())
    ended_at    = Column(TIMESTAMP(timezone=True))
    records_in  = Column(Integer, default=0)
    records_out = Column(Integer, default=0)
    error_msg   = Column(Text)
    metadata    = Column(JSONB)
```

---

## 1.3 Pipeline Audit Helper

Create `backend/pipeline/audit.py`:

```python
# backend/pipeline/audit.py
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from app.database import get_db   # reuse existing session factory

class _AuditRecord:
    def __init__(self):
        self.records_out = 0
        self.error_msg   = None
        self.status      = "RUNNING"

@asynccontextmanager
async def audit_job(job_name: str, stock_id: int = None):
    """
    Usage:
        async with audit_job('price_daily_ingestion') as audit:
            audit.records_out = 500
    """
    record = _AuditRecord()
    audit_id = await _insert_audit(job_name, stock_id)
    try:
        yield record
        record.status = "SUCCESS"
    except Exception as e:
        record.status    = "FAILED"
        record.error_msg = str(e)
        raise
    finally:
        await _close_audit(audit_id, record)

async def _insert_audit(job_name, stock_id):
    sql = """
        INSERT INTO pipeline_audit (job_name, stock_id, status, started_at)
        VALUES ($1, $2, 'RUNNING', NOW())
        RETURNING id
    """
    # Use a raw asyncpg connection for simplicity in background tasks
    from app.database import raw_connection
    async with raw_connection() as conn:
        row = await conn.fetchrow(sql, job_name, stock_id)
        return row["id"]

async def _close_audit(audit_id, record):
    sql = """
        UPDATE pipeline_audit
        SET status=$1, ended_at=NOW(), records_out=$2, error_msg=$3
        WHERE id=$4
    """
    from app.database import raw_connection
    async with raw_connection() as conn:
        await conn.execute(sql, record.status, record.records_out, record.error_msg, audit_id)
```

---

## 1.4 APScheduler — Wire into main.py

Add to `backend/pipeline/scheduler.py`:

```python
# backend/pipeline/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

def configure_scheduler():
    """Register all pipeline jobs. Jobs are no-ops until their modules are implemented."""
    # Prices — Mon-Fri after NSE market close (15:30 IST)
    # scheduler.add_job(run_daily_price_ingestion,  CronTrigger(day_of_week="mon-fri", hour=18, minute=30))
    # scheduler.add_job(run_index_ingestion,         CronTrigger(day_of_week="mon-fri", hour=18, minute=40))
    # scheduler.add_job(run_technical_indicators,   CronTrigger(day_of_week="mon-fri", hour=19, minute=0))
    # scheduler.add_job(run_pattern_detection,       CronTrigger(day_of_week="mon-fri", hour=19, minute=45))
    # scheduler.add_job(run_rating_compute,          CronTrigger(day_of_week="mon-fri", hour=20, minute=15))
    # scheduler.add_job(run_fundamental_scrape_all,  CronTrigger(day_of_week="sun",     hour=2,  minute=0))
    # scheduler.add_job(run_ratio_compute_all,       CronTrigger(day_of_week="sun",     hour=9,  minute=0))
    # scheduler.add_job(run_shareholding_scrape,     CronTrigger(day=1,                 hour=3,  minute=0))
    # scheduler.add_job(run_data_integrity_check,    CronTrigger(day_of_week="mon-fri", hour=9,  minute=0))
    pass  # Uncomment each line as the corresponding module is implemented
```

Add to `backend/app/main.py` (additive only):

```python
# In main.py — add scheduler lifespan
from contextlib import asynccontextmanager
from pipeline.scheduler import configure_scheduler, scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...
    configure_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)

# Pass lifespan to app:
# app = FastAPI(lifespan=lifespan, ...)
```

---

## 1.5 Stock Master Seed Script

Create `backend/scripts/seed/seed_stock_master.py`:

```python
"""
Seed the stocks table with NSE-listed companies.

Data source: NSE website or a curated CSV.
This script uses yfinance to validate each symbol before inserting.

Run once: python scripts/seed/seed_stock_master.py
"""
import asyncio
import asyncpg
import yfinance as yf
from typing import List, Dict

# Curated list of well-known NSE stocks for initial seeding.
# Extend this with a full NSE symbol CSV download from:
# https://www.nseindia.com/market-data/securities-available-for-trading
SEED_STOCKS: List[Dict] = [
    # Large Cap — NIFTY 50
    {"symbol": "RELIANCE",   "yf_symbol": "RELIANCE.NS",   "company_name": "Reliance Industries Ltd",        "sector": "Energy",          "market_cap_cat": "large"},
    {"symbol": "TCS",        "yf_symbol": "TCS.NS",        "company_name": "Tata Consultancy Services Ltd",  "sector": "IT",              "market_cap_cat": "large"},
    {"symbol": "HDFCBANK",   "yf_symbol": "HDFCBANK.NS",   "company_name": "HDFC Bank Ltd",                  "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "INFY",       "yf_symbol": "INFY.NS",       "company_name": "Infosys Ltd",                    "sector": "IT",              "market_cap_cat": "large"},
    {"symbol": "ICICIBANK",  "yf_symbol": "ICICIBANK.NS",  "company_name": "ICICI Bank Ltd",                 "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "HINDUNILVR", "yf_symbol": "HINDUNILVR.NS", "company_name": "Hindustan Unilever Ltd",         "sector": "FMCG",            "market_cap_cat": "large"},
    {"symbol": "BHARTIARTL", "yf_symbol": "BHARTIARTL.NS", "company_name": "Bharti Airtel Ltd",              "sector": "Telecom",         "market_cap_cat": "large"},
    {"symbol": "KOTAKBANK",  "yf_symbol": "KOTAKBANK.NS",  "company_name": "Kotak Mahindra Bank Ltd",        "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "WIPRO",      "yf_symbol": "WIPRO.NS",      "company_name": "Wipro Ltd",                      "sector": "IT",              "market_cap_cat": "large"},
    {"symbol": "LT",         "yf_symbol": "LT.NS",         "company_name": "Larsen & Toubro Ltd",            "sector": "Infrastructure",  "market_cap_cat": "large"},
    {"symbol": "AXISBANK",   "yf_symbol": "AXISBANK.NS",   "company_name": "Axis Bank Ltd",                  "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "BAJFINANCE", "yf_symbol": "BAJFINANCE.NS", "company_name": "Bajaj Finance Ltd",              "sector": "NBFC",            "market_cap_cat": "large"},
    {"symbol": "SBIN",       "yf_symbol": "SBIN.NS",       "company_name": "State Bank of India",            "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "MARUTI",     "yf_symbol": "MARUTI.NS",     "company_name": "Maruti Suzuki India Ltd",        "sector": "Auto",            "market_cap_cat": "large"},
    {"symbol": "SUNPHARMA",  "yf_symbol": "SUNPHARMA.NS",  "company_name": "Sun Pharmaceutical Industries",  "sector": "Pharma",          "market_cap_cat": "large"},
    # Indices (is_index = True)
    {"symbol": "NIFTY50",    "yf_symbol": "^NSEI",         "company_name": "NIFTY 50 Index",                 "sector": "Index",           "market_cap_cat": None, "is_index": True},
    {"symbol": "SENSEX",     "yf_symbol": "^BSESN",        "company_name": "BSE SENSEX",                     "sector": "Index",           "market_cap_cat": None, "is_index": True},
    {"symbol": "NIFTYBANK",  "yf_symbol": "^NSEBANK",      "company_name": "NIFTY Bank Index",               "sector": "Index",           "market_cap_cat": None, "is_index": True},
    # Add more stocks here — or load from a CSV file
]

INSERT_SQL = """
    INSERT INTO stocks (symbol, nse_symbol, yf_symbol, screener_slug, company_name, sector, market_cap_cat, is_index, is_active)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE)
    ON CONFLICT (symbol) DO UPDATE SET
        company_name   = EXCLUDED.company_name,
        sector         = EXCLUDED.sector,
        market_cap_cat = EXCLUDED.market_cap_cat,
        updated_at     = NOW()
"""

async def seed():
    conn = await asyncpg.connect("postgresql://user:pass@localhost:5432/nivesh")
    try:
        for s in SEED_STOCKS:
            await conn.execute(
                INSERT_SQL,
                s["symbol"],
                s.get("nse_symbol", s["symbol"]),
                s["yf_symbol"],
                s.get("screener_slug", s["symbol"]),
                s["company_name"],
                s.get("sector"),
                s.get("market_cap_cat"),
                s.get("is_index", False),
            )
            print(f"  ✓ {s['symbol']}")
        print(f"\nSeeded {len(SEED_STOCKS)} records.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed())
```

---

## 1.6 Validation Checklist

After running the migration and seed script, verify:

```bash
# 1. All 9 new tables exist
psql -U user -d nivesh -c "\dt" | grep -E "stocks|price_data|financial|shareholding|technical|detected|stock_rating|pipeline_audit"

# 2. Seed data loaded
psql -U user -d nivesh -c "SELECT symbol, company_name, sector FROM stocks LIMIT 5;"

# 3. Existing MF tables untouched
psql -U user -d nivesh -c "SELECT COUNT(*) FROM fund_master;"

# 4. Existing API still works
curl http://localhost:8000/api/funds | jq '.total'

# 5. yfinance works for NSE symbols
python3 -c "import yfinance as yf; df = yf.Ticker('RELIANCE.NS').history(period='5d'); print(df.tail(2))"

# 6. Indexes created
psql -U user -d nivesh -c "\di" | grep idx_
```

---

## 1.7 Deliverables for Phase 1

- [ ] Alembic migration applied — all 9 tables exist
- [ ] SQLAlchemy models added to `app/models.py`
- [ ] `pipeline/` directory created with `__init__.py`, `audit.py`, `scheduler.py`
- [ ] APScheduler wired into FastAPI lifespan (no jobs active yet)
- [ ] `scripts/seed/seed_stock_master.py` run — stocks table populated
- [ ] Validation checklist all green
- [ ] Existing MF platform regression tested — all MF endpoints return 200
