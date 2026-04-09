# Stock Data Pipeline — Implementation Plan

> **Author:** Senior Backend Developer  
> **Date:** 2026-04-09  
> **Status:** Planning / Pre-implementation  
> **Scope:** Stock market data ingestion, metrics recomputation, screener.in sync, technical analysis triggers

---

## 1. Context & Current State

### What Already Exists

The backend (`backend/`) already has a working pipeline **for Mutual Funds** and a **partially wired** stock market pipeline:

| Component | File | Status |
|---|---|---|
| Price ingestion (OHLCV via yfinance) | `pipeline/price_ingestion.py` | ✅ Implemented |
| Index ingestion | `pipeline/price_ingestion.py` | ✅ Implemented |
| Screener.in fundamental scraper | `pipeline/fundamental_scraper.py` | ✅ Implemented |
| Financial ratio engine | `pipeline/ratio_engine.py` | ✅ Implemented |
| APScheduler configuration | `pipeline/scheduler.py` | ⚠️ Partial — TA jobs commented out |
| Technical indicators computation | *(missing)* | ❌ Not implemented |
| Pattern detection | *(missing)* | ❌ Not implemented |
| Stock rating engine | *(missing)* | ❌ Not implemented |
| API trigger endpoints for stocks | `app/routers/stocks.py` | ⚠️ Read-only — no write/trigger endpoints |
| API trigger for screener.in | *(missing)* | ❌ No dedicated trigger endpoint |
| API trigger for technical analysis | *(missing)* | ❌ No dedicated trigger endpoint |

### Key Models (Database Tables)

```
stocks               — master stock list (symbol, yf_symbol, screener_slug, sector, ...)
price_data           — daily OHLCV per stock_id + price_date
financial_statements — quarterly/annual P&L, BS, CF scraped from screener.in (JSONB)
shareholding_pattern — quarterly promoter/FII/DII breakdown
financial_ratios     — computed from financial_statements (PE, PB, ROE, etc.)
technical_indicators — SMA, EMA, RSI, MACD, Bollinger Bands, ATR, ADX, Stoch
detected_patterns    — chart patterns (trend lines, breakouts, etc.)
stock_ratings        — composite score (fundamental + technical + momentum)
pipeline_audit       — all job runs tracked with status & timing
```

### Key Issues Identified

1. **No `TechnicalIndicator` computation module exists** — `TechnicalIndicator` model is defined in `models.py` but no compute engine exists.
2. **Scheduler has TA jobs commented out** — `run_technical_indicators`, `run_pattern_detection`, `run_rating_compute` are commented in `scheduler.py`.
3. **`financial_ratios` PE/PB are price-dependent** — currently only recomputed when fundamentals change (Sunday), but PE/PB require the latest market price (daily changing). This is a gap.
4. **No API trigger endpoints for stock pipeline** — there are no `POST /stock-pipeline/*` admin endpoints to manually trigger price ingestion, screener scrape, or technical analysis per stock or for all stocks.
5. **`raw_connection()` opens/closes per call** — Each DB helper in pipeline modules opens a new `asyncpg` connection per call rather than using a connection pool, which is inefficient under load.
6. **Screener.in scraping is coupled** — `run_fundamental_scrape_all` filters by `scraped_at > 90 days`, but there's no on-demand single-stock or all-stocks HTTP trigger endpoint.

---

## 2. Phased Implementation Plan

### Priority Order

```
Phase 1 → Data Pipeline Structure (OHLC + Indices)
Phase 2 → Daily Metrics Re-computation (price-dependent metrics)
Phase 3 → Screener.in Trigger Endpoints (quarterly data)
Phase 4 → Technical Analysis Engine + Trigger Endpoints
Phase 5 → Scheduler Wiring & Documentation
```

---

## Phase 1 — Data Fetch Pipeline Structure (OHLC + Indices)

### Goal
Establish a clear, documented pipeline for fetching stock market data (OHLCV, indices) and understand what runs when.

### Current Pipeline Flow (Documented)

```
[APScheduler Mon-Fri 18:30 IST]
        │
        ▼
run_daily_price_ingestion()
 └─ _fetch_active_stocks(is_index=False)   → stocks table (is_active=TRUE, is_index=FALSE)
 └─ chunks of 50 symbols → yfinance.download(period="5d")
 └─ _upsert_price_rows(stock_id, df)       → price_data table (ON CONFLICT DO UPDATE)

[APScheduler Mon-Fri 18:40 IST]
        │
        ▼
run_index_ingestion()
 └─ _fetch_active_stocks(is_index=True)    → indices only
 └─ _ingest_chunk(period="5d")
 └─ _upsert_price_rows(stock_id, df)       → price_data table
```

### Changes Required in Phase 1

#### 1.1 — Add Admin Trigger Endpoint: Price Ingestion

**New file:** `backend/app/routers/pipeline.py`

```python
POST /api/v1/pipeline/prices/all
    → Triggers run_daily_price_ingestion() as a background task
    → Returns job_id from pipeline_audit

POST /api/v1/pipeline/prices/indices
    → Triggers run_index_ingestion() as a background task

POST /api/v1/pipeline/prices/backfill
    → Triggers run_backfill(period="5y") as a background task
    → Requires admin auth
```

#### 1.2 — Fix Connection Per Call Anti-pattern

In `price_ingestion.py`, each `_fetch_active_stocks()` and `_upsert_price_rows()` opens a fresh `asyncpg` connection. Replace with a connection pool passed through function arguments.

**Files to change:**
- `backend/pipeline/price_ingestion.py`
- `backend/pipeline/fundamental_scraper.py` (uses `raw_connection()` from `app.database`)
- `backend/pipeline/ratio_engine.py`

#### 1.3 — Add backfill_prices script

**New file:** `backend/scripts/seed/backfill_prices.py`

```python
# Usage: python -m scripts.seed.backfill_prices --period 5y
# Calls run_backfill(period="5y") for all active stocks
```

---

## Phase 2 — Daily Metrics Re-computation (Price-Dependent Metrics)

### Goal
Identify which metrics change with daily price data vs. which are quarterly. Re-trigger only price-dependent metrics after each price ingestion.

### Metric Classification

#### Group A — Changes Every Trading Day (Price-Dependent)

These must be recomputed after each daily price ingestion:

| Metric | Location | Dependency |
|---|---|---|
| `pe_ratio` | `financial_ratios` | `close` / `eps` — EPS is stable, close changes daily |
| `pb_ratio` | `financial_ratios` | `close` / `book_value_ps` |
| `ps_ratio` | `financial_ratios` | `close * shares` / `revenue` |
| `peg_ratio` | `financial_ratios` | derived from PE + EPS growth |
| `ev_ebitda` | `financial_ratios` | market cap (price-based) + debt - cash / EBITDA |
| `dividend_yield` | `financial_ratios` | `dividend` / `close` |
| `latest_close` (stock detail) | `price_data` (read) | latest row |
| `change_pct` (1-day) | computed in SQL | (close_today - close_prev) / close_prev |
| `sma_20/50/200` | `technical_indicators` | rolling avg of close prices |
| `EMA series` | `technical_indicators` | exponential avg of close prices |
| `RSI_14` | `technical_indicators` | relative strength of close |
| `MACD` | `technical_indicators` | EMA12 - EMA26 |
| `Bollinger Bands` | `technical_indicators` | SMA ± σ |
| `ATR_14` | `technical_indicators` | average true range |
| `ADX_14` | `technical_indicators` | trend strength |
| `Stochastic K/D` | `technical_indicators` | price channel momentum |
| `volume_sma_20` | `technical_indicators` | rolling volume avg |
| `total_score` (rating) | `stock_ratings` | partly price-based |
| `technical_score` (rating) | `stock_ratings` | from TA indicators |
| `momentum_score` (rating) | `stock_ratings` | price momentum |

#### Group B — Changes Every Quarter (Fundamental-Dependent)

These are recomputed only after screener.in scraping:

| Metric | Location | Dependency |
|---|---|---|
| `roe`, `roce`, `roa` | `financial_ratios` | P&L + BS |
| `pat_margin`, `ebitda_margin`, `gross_margin` | `financial_ratios` | P&L |
| `debt_equity`, `interest_cov`, `current_ratio` | `financial_ratios` | BS + P&L interest |
| `revenue_growth`, `pat_growth`, `eps_growth` | `financial_ratios` | YoY P&L |
| `eps`, `book_value_ps` | `financial_ratios` | P&L + BS per share |
| `cfo_to_pat` | `financial_ratios` | CF + P&L |
| `promoter_pct`, `fii_pct`, etc. | `shareholding_pattern` | quarterly scrape |
| `fundamental_score`, `quality_score` | `stock_ratings` | from ratios |
| `valuation_score`, `shareholding_score` | `stock_ratings` | from ratios + shareholding |

### Changes Required in Phase 2

#### 2.1 — New: `pipeline/metric_recompute.py`

Create a dedicated module that only refreshes Group A (price-based) metrics after daily data ingest:

```python
async def recompute_price_dependent_ratios(stock_id: int, latest_close: float):
    """Recompute only PE, PB, PS, PEG, dividend_yield from latest price."""
    # Fetch stored eps, book_value_ps, revenue, shares from financial_ratios
    # Recompute using latest close
    # Upsert only the price-dependent columns in financial_ratios

async def recompute_price_dependent_ratios_all():
    """Run for all active, non-index stocks after daily ingestion."""
```

#### 2.2 — Chain nightly price job → metric recompute

In `scheduler.py`, after `run_daily_price_ingestion` completes, trigger `recompute_price_dependent_ratios_all`:

```python
scheduler.add_job(
    recompute_price_dependent_ratios_all,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=0),
    max_instances=1,
    id="price_ratio_refresh"
)
```

---

## Phase 3 — Screener.in Trigger Endpoints

### Goal
Expose dedicated HTTP endpoints to trigger screener.in fundamental data scraping — either for a single stock or all stocks — independent of the Sunday scheduled job.

### Changes Required in Phase 3

#### 3.1 — Add Admin Trigger Endpoints for Screener

In `backend/app/routers/pipeline.py` (from Phase 1):

```python
POST /api/v1/pipeline/screener/all
    """
    Trigger fundamental scrape for all stocks that haven't been scraped
    in 90+ days. Runs as a background task. Returns audit_id.
    """

POST /api/v1/pipeline/screener/{symbol}
    """
    Trigger fundamental scrape for a single stock immediately.
    Useful for on-demand refresh after new quarterly results.
    Runs synchronously (returns scrape result) or as background.
    """

GET /api/v1/pipeline/screener/status
    """
    Return last scrape timestamp for all stocks.
    Shows which stocks are overdue for scraping (> 90 days).
    """
```

#### 3.2 — Add "Force Rescrape" Flag to `run_fundamental_scrape_one`

Currently `run_fundamental_scrape_one` uses checksum deduplication. Add a `force: bool = False` parameter so the admin endpoint can bypass the checksum check and force a fresh scrape.

#### 3.3 — After Screener Scrape → Trigger Ratio Recompute

After a successful scrape:
1. Trigger `run_ratio_compute_all()` for Group B metrics (or for the specific stock if single).
2. Trigger rating recompute (Phase 4) for that stock.

---

## Phase 4 — Technical Analysis Engine + Trigger Endpoints

### Goal
Build the `pipeline/technical_analysis.py` engine to compute all `TechnicalIndicator` rows, and expose trigger endpoints for per-stock or all-stocks computation.

### New Module: `backend/pipeline/technical_analysis.py`

```python
"""
Computes technical indicators from price_data and stores in technical_indicators.
Uses ta-lib for all indicator calculations.
"""

TIMEFRAMES = ["1d"]  # Extendable to "1w", "1mo"

async def run_technical_analysis_all():
    """Compute TA for all active stocks from price_data. Called by scheduler."""

async def run_technical_analysis_one(symbol: str):
    """Compute TA for a single stock. Called by trigger endpoint."""

async def _compute_indicators(stock_id: int, timeframe: str = "1d"):
    """
    1. Fetch all price_data rows for stock_id (ordered by date)
    2. Build OHLCV DataFrame
    3. Compute:
       - SMA(20), SMA(50), SMA(200)
       - EMA(9), EMA(21), EMA(50)
       - RSI(14)
       - MACD(12, 26, 9) → line, signal, histogram
       - Bollinger Bands (20, 2σ) → upper, middle, lower
       - ATR(14)
       - ADX(14)
       - Stochastic (14,3) → K, D
       - Volume SMA(20)
    4. Upsert only the LATEST row to technical_indicators table
       (ON CONFLICT stock_id, ind_date, timeframe DO UPDATE)
    """
```

#### Library Choice

Use `TA-Lib` (C-bindings) for high performance:
```bash
pip install TA-Lib
```

#### 4.1 — Trigger Endpoints

In `backend/app/routers/pipeline.py`:

```python
POST /api/v1/pipeline/technical/all
    """
    Trigger TA computation for all active stocks.
    Runs as background task. Reads from price_data, writes to technical_indicators.
    Returns: {"job_id": ..., "stocks_queued": N}
    """

POST /api/v1/pipeline/technical/{symbol}
    """
    Trigger TA computation for a single stock.
    Runs synchronously. Returns computed indicator values on success.
    """

GET /api/v1/pipeline/technical/status
    """
    Shows last TA computation date for each stock.
    Flags stocks with no TA data or TA older than 2 days.
    """
```

#### 4.2 — Scheduler Wiring

Uncomment and wire in `scheduler.py`:

```python
scheduler.add_job(
    run_technical_analysis_all,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=0),
    max_instances=1,
    id="technical_analysis_daily"
)
```

---

## Phase 5 — Scheduler Wiring & API Registration

### 5.1 — Complete Scheduler Configuration

**Final scheduler job sequence (weekdays):**

| Time (IST) | Job | Module |
|---|---|---|
| 18:30 | `price_daily_ingestion` | `pipeline/price_ingestion.py` |
| 18:40 | `index_daily_ingestion` | `pipeline/price_ingestion.py` |
| 19:00 | `price_ratio_refresh` | `pipeline/metric_recompute.py` |
| 19:30 | `technical_analysis_daily` | `pipeline/technical_analysis.py` |
| 20:15 | `rating_compute` | `pipeline/rating_engine.py` |

**Weekly jobs (Sunday):**

| Time (IST) | Job | Module |
|---|---|---|
| 02:00 | `fundamental_scrape_all` | `pipeline/fundamental_scraper.py` |
| 09:00 | `ratio_compute_all` (Group B) | `pipeline/ratio_engine.py` |

### 5.2 — Register New Router

In `backend/app/main.py`, register the new pipeline router:

```python
from .routers import pipeline
app.include_router(pipeline.router, prefix=settings.API_V1_STR)
```

---

## 3. Files to Create / Modify

### New Files

| File | Purpose |
|---|---|
| `backend/app/routers/pipeline.py` | Admin trigger endpoints for all pipeline jobs |
| `backend/pipeline/technical_analysis.py` | Technical indicator computation engine |
| `backend/pipeline/metric_recompute.py` | Price-dependent metric recompute (daily) |
| `backend/pipeline/rating_engine.py` | Stock rating/scoring engine |
| `backend/scripts/seed/backfill_prices.py` | One-time backfill of 5-year price history |

### Modified Files

| File | Change |
|---|---|
| `backend/pipeline/scheduler.py` | Uncomment and add new jobs |
| `backend/pipeline/fundamental_scraper.py` | Add `force` param to `run_fundamental_scrape_one` |
| `backend/pipeline/ratio_engine.py` | Separate Group A vs Group B recompute |
| `backend/app/main.py` | Register `pipeline` router |
| `backend/requirements.txt` | Add `TA-Lib` |

---

## 4. Open Questions / Decisions

1. **ta-lib vs pandas-ta**: DECISION LOCKED — We chose `ta-lib` (C-bindings) for performance over pure Python implementations.
2. **Pattern Detection**: `DetectedPattern` model exists but no detection algorithm. This is a complex ML/rule-based task. Defer to a separate phase.
3. **Rating Engine**: `StockRating` model exists but no computation module. The `stock_ratings` table is referenced in the screener and stock list but never written. Needs to be prioritized.
4. **Admin Auth for Trigger Endpoints**: Should we re-use the existing JWT security (like the mutual fund `/sync` router) or add a separate API key for pipeline triggers?
5. **Background vs Synchronous**: Single-stock triggers should run synchronously and return results. All-stocks triggers must run as background tasks. Use FastAPI `BackgroundTasks`.

---

## 5. Dependency Chain Summary

```
[yfinance] → price_data
                  │
                  ├──→ [metric_recompute.py] → financial_ratios (PE, PB, PS — daily)
                  │
                  └──→ [technical_analysis.py] → technical_indicators
                                                        │
                                                        └──→ [rating_engine.py] → stock_ratings

[screener.in] → financial_statements + shareholding_pattern
                           │
                           └──→ [ratio_engine.py] → financial_ratios (ROE, ROCE, D/E — quarterly)
                                                            │
                                                            └──→ [rating_engine.py] → stock_ratings
```
