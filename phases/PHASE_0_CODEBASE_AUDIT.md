# Phase 0 — Codebase Audit & Context
> **Read before touching any code.** This document defines the integration contract between the existing Nivesh Platform and the new Stock Market module.

---

## 0.1 What Already Exists (Do Not Break)

| Attribute | Current State |
|---|---|
| Platform | Nivesh Elite — Mutual Fund analytics SPA |
| Backend | FastAPI + SQLAlchemy (Async) + Uvicorn on port 8000 |
| Frontend | React 19 + Vite 8 + Redux Toolkit (4 slices) + Axios + Recharts |
| Database | PostgreSQL 16 (plain — no TimescaleDB) |
| Auth | JWT via python-jose + bcrypt. Protected routes via FastAPI dependency injection |
| MF Data Source | mftool (AMFI) — **keep untouched** |
| Styling | CALIFINO custom CSS tokens — permanent dark mode. **Do not introduce Tailwind or new CSS frameworks** |
| Frontend Router | Custom hash-based router in `App.jsx` via `hashchange` — no react-router-dom |
| State Management | Redux Toolkit: `syncSlice`, `compareSlice`, `fundsSlice`, `indicesSlice` + `AuthContext` + `ThemeContext` |
| Background Jobs | ETL scripts run manually (`etl_populate_data.py`, `populate_nav_history.py`, `recompute_funds_metrics.py`) |
| Screener Scraper | `fundamental_data_extractor.py` — **ScreenerScraper class already built.** Handles P&L, Balance Sheet, CF, Shareholding with multi-strategy section detection. **Do not rewrite.** |
| Sample Data | `BHARTIARTL.json` — real output from ScreenerScraper. Use this as the test fixture for the normalizer. |
| Existing DB Tables | `fund_master`, `benchmark_master`, `fund_metrics`, `fund_nav_history`, `benchmark_nav_history`, `sync_jobs` |
| Placeholder Pages | `StockListing` and `StockDetail` exist as empty shells — waiting to be implemented |
| Docker | `docker-compose.yml` in `backend/` for the DB. Backend runs with venv + uvicorn. |

---

## 0.2 The Existing ScreenerScraper — Reuse It

`fundamental_data_extractor.py` is **production-ready**. Do not modify it. Import it in `pipeline/fundamental_scraper.py`.

**What it does:**
- Builds URL: `https://www.screener.in/company/{TICKER}/consolidated/`
- Uses 4-strategy section detection: ID match → anchor href → heading text → full-text scan
- Has configurable delay (default 1.5s), session management, and User-Agent headers
- Returns a structured dict with `profit_and_loss`, `balance_sheet`, `cash_flow`, `shareholding_pattern`

**Its output shape (from `BHARTIARTL.json`):**
```json
{
  "ticker": "BHARTIARTL",
  "company_name": "Bharti Airtel Limited",
  "statement_type": "consolidated",
  "profit_and_loss": {
    "headers": ["", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
    "rows": [
      {"": "Revenue", "Mar 2020": "87,939", "Mar 2021": "100,616", ...},
      {"": "Expenses", ...}
    ]
  },
  "balance_sheet": { "headers": [...], "rows": [...] },
  "cash_flow":     { "headers": [...], "rows": [...] },
  "shareholding_pattern": { "tables": [{ "headers": [...], "rows": [...] }] }
}
```

> ⚠️ **Critical:** Values are Indian-formatted strings. `'87,939'` → `87939.0`. `'(12,345)'` → `-12345.0`. `'12.34%'` → `12.34`. The normalizer in Phase 3 handles all of this.

---

## 0.3 Gap Analysis — What Needs to Be Built

| Module | Status | Phase |
|---|---|---|
| Stock master registry (NSE/BSE symbols + yf mapping) | MISSING | Phase 1 |
| DB schema — all 8 new tables | MISSING | Phase 1 |
| Price data ingestion (yfinance OHLCV) | MISSING | Phase 2 |
| Basic stock listing + price API | MISSING | Phase 2 |
| Fundamental data normalizer | MISSING | Phase 3 |
| Fundamental pipeline (wraps ScreenerScraper) | MISSING | Phase 3 |
| Financial ratios engine | MISSING | Phase 4 |
| Screener API | MISSING | Phase 4 |
| Technical indicators computation | MISSING | Phase 5 |
| Pattern recognition engine | MISSING | Phase 5 |
| Rating engine | MISSING | Phase 6 |
| Compare + Dashboard updates | MISSING | Phase 6 |
| Frontend: StockListing page | PLACEHOLDER | Phase 2/4 |
| Frontend: StockDetail page | PLACEHOLDER | Phase 3/5 |
| Frontend: Screener page | MISSING | Phase 4 |
| Frontend: StockCompare page | MISSING | Phase 6 |
| ScreenerScraper class | **DONE** | Reuse |
| JWT auth system | **DONE** | Reuse |
| MF fund/indices endpoints | **DONE** | Do not touch |

---

## 0.4 Additive-Only Rule

> **Never modify existing files.** Only add to them.

- `app/models.py` — add new model classes below existing ones
- `app/schemas.py` — add new Pydantic schemas below existing ones
- `app/crud.py` — add new CRUD functions below existing ones
- `app/main.py` — add `include_router()` calls and scheduler lifespan
- `store/slices/compareSlice.js` — add `stockCompareList` state and reducers only
- `App.jsx` — add new hash routes to the existing route map only

All new backend logic lives in the new `pipeline/` directory. All new frontend logic lives in new files.

---

## 0.5 Complete File Structure (After All Phases)

```
backend/
├── app/
│   ├── main.py          ← ADD: stock routers + scheduler lifespan
│   ├── models.py        ← ADD: Stock, PriceData, FinancialStatement, etc.
│   ├── database.py      ← NO CHANGE
│   ├── security.py      ← NO CHANGE
│   ├── crud.py          ← ADD: stock CRUD functions
│   ├── schemas.py       ← ADD: stock Pydantic schemas
│   ├── analytics.py     ← NO CHANGE (MF analytics)
│   └── routers/
│       ├── funds.py         ← NO CHANGE
│       ├── indices.py       ← NO CHANGE
│       ├── auth.py          ← NO CHANGE
│       ├── stocks.py        ← NEW
│       ├── technicals.py    ← NEW
│       ├── ratings.py       ← NEW
│       ├── screener.py      ← NEW
│       └── admin_pipeline.py← NEW (JWT protected)
├── pipeline/                ← NEW directory
│   ├── __init__.py
│   ├── scheduler.py         ← APScheduler setup + job registry
│   ├── price_ingestion.py
│   ├── fundamental_scraper.py  ← wraps existing ScreenerScraper
│   ├── normalizer.py        ← Indian number parser
│   ├── ratio_engine.py
│   ├── technical_engine.py
│   ├── pattern_engine.py
│   ├── rating_engine.py
│   └── audit.py             ← pipeline_audit table writer
├── scripts/
│   ├── seed/
│   │   ├── seed_stock_master.py   ← NEW
│   │   └── backfill_prices.py     ← NEW
│   └── (existing scripts untouched)
└── fundamental_data_extractor.py  ← NO CHANGE — imported by pipeline/

frontend/src/
├── pages/
│   ├── StockListing.jsx   ← IMPLEMENT (was placeholder)
│   ├── StockDetail.jsx    ← IMPLEMENT (was placeholder)
│   ├── Screener.jsx       ← NEW
│   └── (existing pages unchanged)
├── store/slices/
│   ├── stocksSlice.js     ← NEW
│   └── (existing slices unchanged)
├── api/
│   ├── stockService.js    ← NEW
│   └── (existing services unchanged)
└── components/
    ├── charts/
    │   ├── CandlestickChart.jsx  ← NEW
    │   ├── RSIChart.jsx          ← NEW
    │   └── MACDChart.jsx         ← NEW
    └── stocks/
        ├── StockCard.jsx         ← NEW
        ├── RatingBadge.jsx       ← NEW
        ├── FilterPanel.jsx       ← NEW
        └── PatternAlertBanner.jsx← NEW
```

---

## 0.6 New Dependencies to Add

**Backend (`requirements.txt`):**
```
yfinance>=0.2.40
pandas-ta>=0.3.14b
scipy>=1.12.0
apscheduler>=3.10.4
# Already present (verify):
# requests, beautifulsoup4, pandas, sqlalchemy, fastapi, asyncpg
```

**Frontend (`package.json`):**
```
lightweight-charts@^4.1.0   # TradingView candlestick charts
# recharts — already present, reuse for RSI/MACD sub-charts
```

---

## 0.7 Environment Variables to Add

```env
# Existing (already set):
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/nivesh
SECRET_KEY=...
ALGORITHM=HS256

# New (add to .env):
SCREENER_DELAY_SECONDS=2.5        # polite crawl delay
SCREENER_MAX_RETRIES=3
PRICE_CHUNK_SIZE=50               # yfinance batch size
PIPELINE_LOG_LEVEL=INFO
```
