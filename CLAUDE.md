# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

### Backend

```bash
cd backend

# Start everything (recommended for first run — creates venv, runs migrations, starts server)
./start.sh                # from project root
./start.sh --skip-deps    # skip pip install if already installed
./start.sh --seed         # also run seed + ETL scripts after startup

# Or manually:
source venv/bin/activate
docker-compose up -d                         # start PostgreSQL
uvicorn app.main:app --port 8000 --reload    # start API
```

**API docs available at:** `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev      # dev server at http://localhost:5173
npm run build    # production build (output: frontend/dist/)
npm run lint     # ESLint
```

### Database / Migrations

There is no Alembic — schema is managed via `Base.metadata.create_all` on startup. To reset benchmark data:

```bash
cd backend
python3 migrate.py --force    # requires --force flag to prevent accidental data loss
```

### Seed & ETL Scripts (run from `backend/`)

```bash
source venv/bin/activate

# Initial data load order (Mutual Funds):
python3 scripts/seed/seed_benchmarks.py          # seed 4 Nifty benchmark records
python3 scripts/seed/import_nifty_indices.py     # bulk-import Nifty index CSV files
python3 scripts/seed/ingest_isins_amfi.py        # fetch ISIN↔scheme_code mapping from AMFI

# Stock Master & Price Data (Phase 1–2):
python3 scripts/seed/seed_stock_master.py        # seed 18 large-cap stocks + 3 indices
python3 scripts/seed/backfill_prices.py 1y       # backfill 1 year of OHLCV data (use 1y for faster testing)
python3 scripts/seed/backfill_prices.py 5y       # backfill 5 years of OHLCV data (full history)

# Ongoing sync (Mutual Funds):
python3 scripts/populate_nav_history.py          # fetch NAV history from mftool for all funds
python3 scripts/etl_populate_data.py             # full ETL: benchmark + fund sync, metrics compute
python3 scripts/recompute_funds_metrics.py       # retrigger metrics for all funds via API
                                                  # (requires ADMIN_PASSWORD env var when ENABLE_AUTH=true)
```

### Stock Market Data (Phase 1–3)

Daily scheduled jobs run Mon–Fri (market hours):
- **18:30 IST:** Daily price ingestion (last 5 days OHLCV via yfinance)
- **18:40 IST:** Index ingestion (Nifty/Sensex indices)

Weekly scheduled job (Phase 3):
- **Sunday 02:00 IST:** Fundamental scrape (P&L, Balance Sheet, Cash Flow, shareholding from screener.in)

Jobs tracked in `pipeline_audit` table (separate from MF sync_jobs). APScheduler configured in `backend/pipeline/scheduler.py`.

---

## Architecture

### Project layout

```
stock_nivesh_platform/
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── main.py        # FastAPI app, CORS, lifespan (create_all), SPA fallback routing
│   │   ├── config.py      # pydantic-settings; startup ValueError if ENABLE_AUTH+dev SECRET_KEY
│   │   ├── database.py    # async engine, session_factory, get_db dependency
│   │   ├── models.py      # SQLAlchemy ORM (16 tables: 7 MF + 9 stocks)
│   │   ├── schemas.py     # Pydantic request/response models
│   │   ├── crud.py        # all DB queries; _apply_fund_filters() for shared filter logic
│   │   ├── analytics.py   # pure-Python financial metric computation (pandas/numpy)
│   │   ├── sync.py        # NAV fetch + metric pipeline; sync_fund_data(), sync_all_funds()
│   │   ├── security.py    # JWT (HS256), bcrypt, get_current_user dependency
│   │   └── routers/       # one file per resource: funds, benchmarks, navs, benchmark_navs,
│   │                      #   metrics, sync, auth, stocks
│   ├── pipeline/          # Background job scheduling & data ingestion
│   │   ├── __init__.py
│   │   ├── scheduler.py    # APScheduler instance + configure_scheduler()
│   │   ├── audit.py        # audit_job context manager for pipeline logging
│   │   └── price_ingestion.py # yfinance OHLCV fetch, backfill, and upsert logic
│   ├── scripts/           # standalone ETL/seed scripts (call HTTP API or use ORM directly)
│   │   └── seed/
│   │       ├── seed_stock_master.py    # seed 18 stocks + 3 indices
│   │       └── backfill_prices.py      # yfinance historical OHLCV backfill
│   ├── alembic/           # Database migration system (PostgreSQL schema management)
│   │   ├── versions/      # versioned migration files
│   │   └── env.py         # Alembic runtime configuration
│   ├── data/Nifty_indices/ # CSV files for benchmark NAV history
│   ├── docker-compose.yml # PostgreSQL 16-alpine
│   ├── migrate.py         # destructive benchmark table reset (requires --force)
│   ├── alembic.ini        # Alembic configuration
│   └── requirements.txt
├── frontend/              # React 19 + Vite + Tailwind
│   └── src/
│       ├── api/           # Axios client + per-resource service modules
│       │   └── services/  # stockService.js, fundService.js, etc.
│       ├── store/slices/  # Redux Toolkit: fundsSlice, syncSlice, compareSlice, indicesSlice, stocksSlice
│       ├── context/       # AuthContext (JWT storage), ThemeContext
│       └── pages/         # route-level components (StockListing.jsx, etc.)
├── docs/                  # architecture, API reference, migration plans
├── TODO.md                # prioritised audit backlog (P0–P3)
└── start.sh               # one-shot startup script
```

### Three-tier architecture

**Backend (FastAPI + PostgreSQL)**
- REST API at `/api/v1/*` serving financial data
- 7 SQLAlchemy models with async/await
- CORS enabled for frontend (localhost:5173 in dev)
- Metrics are computed on-demand via background workers (sync_jobs pattern)
- Auth optional: write endpoints require JWT when `ENABLE_AUTH=true`; reads are public
- SPA fallback: serves `frontend/dist/index.html` for unmatched routes (production deployment)

**Frontend (React 19 + Vite)**
- SPA deployed to `frontend/dist/`
- Redux Toolkit for server state (funds, metrics, comparisons)
- React Context for session state (auth JWT, theme)
- Pages: Dashboard, MF Listing/Detail/Compare, Stocks, Indices, Portfolio, Admin, Login
- Axios client auto-injects `Authorization` header from AuthContext
- JIT (just-in-time) sync polling: when metrics needed, polls `/api/v1/metrics/{code}/status` every 3s until completion

**How they connect**
- Frontend calls REST API at base URL (dev: `http://localhost:8000`, prod: same origin)
- Metrics requests are async: returns immediately with existing data, triggers background sync, frontend polls status
- Authentication: frontend stores JWT in AuthContext, Axios injects it on every request

### Database tables

**Mutual Fund Tables (7):**

| Table | Purpose |
|---|---|
| `fund_master` | Scheme metadata (AMFI code, category, AMC, ISIN, benchmark ref) |
| `benchmark_master` | Index metadata (code, ticker, asset class) |
| `fund_nav_history` | Daily NAV time-series; composite PK `(scheme_code, nav_date)` |
| `benchmark_nav_history` | Daily index value time-series; same PK pattern |
| `fund_metrics` | Computed risk/return metrics; upserted after every sync |
| `benchmark_metrics` | Computed benchmark metrics |
| `sync_jobs` | Background job tracker; partial unique index prevents duplicate RUNNING jobs per scheme |

**Stock Market Tables (9):**

| Table | Purpose |
|---|---|
| `stocks` | NSE/BSE symbol master (company_name, sector, market_cap_cat, is_index) |
| `price_data` | OHLCV time-series from yfinance; composite PK `(stock_id, price_date)` |
| `financial_statements` | P&L, Balance Sheet, Cash Flow (normalized JSON in data column) |
| `shareholding_pattern` | Promoter, FII, DII, Public ownership percentages |
| `financial_ratios` | 27 computed ratios (PE, PB, ROE, debt_equity, etc.) |
| `technical_indicators` | SMA, EMA, RSI, MACD, Bollinger Bands, ATR, ADX, Stochastic |
| `detected_patterns` | Chart patterns (Head & Shoulders, Breakout, Reversal, etc.) |
| `stock_ratings` | Composite scoring (fundamental 30%, valuation 20%, technical 20%, etc.) |
| `pipeline_audit` | Job tracking for stock ingestion pipelines (separate from sync_jobs) |

### Stock API Endpoints (Phase 2)

**GET /api/v1/stocks** — Paginated listing with filters
- Query params: `sector`, `market_cap_cat`, `page` (1), `limit` (25, max 100), `sort_by` (symbol|company_name|sector), `order` (asc|desc)
- Returns: Array of stocks with latest price + rating (LATERAL JOIN for efficiency)
- Example: `GET /stocks?sector=Banking&page=1&limit=10`

**GET /api/v1/stocks/search** — Full-text search
- Query param: `q` (1-50 chars) — searched against symbol (exact match priority) + company_name (tsvector)
- Returns: Array of matching stocks (max 20)
- Example: `GET /stocks/search?q=reliance`

**GET /api/v1/stocks/{symbol}** — Full stock snapshot
- Returns: Symbol, company metadata, latest OHLCV, 1-day change %, rating, technical indicators
- Example: `GET /stocks/RELIANCE`

**GET /api/v1/stocks/{symbol}/price** — OHLCV time-series
- Query params: `interval` (1d|1w|1mo), `from_date`, `to_date` (optional), `limit` (365, max 2000)
- Aggregation: Weekly/monthly use date_trunc() + ARRAY_AGG to compute OHLCV
- Returns: Time-series in chronological order (ascending dates)
- Example: `GET /stocks/RELIANCE/price?interval=1d&limit=90`

### Request → response flow (MF)

1. **List/detail reads** (`GET /funds/`, `GET /metrics/{code}`) — direct async DB queries via `crud.py`, eager-load with `joinedload`.
2. **Metrics request (GET /metrics/{code})** — checks cache age (24 h). If stale or missing, creates a `SyncJob` row and dispatches `background_sync_wrapper` via FastAPI `BackgroundTasks`. Returns immediately with current (possibly null) metrics and job status.
3. **Background sync** (`sync.sync_fund_data`) — fetches NAV via mftool (wrapped in `asyncio.to_thread`), fetches AUM/TER from Captnemo API (also `asyncio.to_thread`), computes all metrics in `analytics.compute_all_metrics`, upserts to `fund_metrics`, marks job COMPLETED/FAILED.
4. **`sync_all_funds`** — opens a **fresh `session_factory()` per fund** so session failure in one fund does not affect others.

### Auth pattern

`security.get_current_user` is a FastAPI dependency. When `ENABLE_AUTH=False` (dev default) it returns `"dev_user"` without touching the token. When `True`, it validates the JWT and raises 401. Write endpoints (`POST`, `PUT`, `DELETE`) depend on it; public read endpoints do not. The `GET /metrics/{code}` endpoint is intentionally public but validates `scheme_code` format before triggering any sync.

### Analytics formulas (analytics.py)

- **Risk-free rate:** 6.5% annualised (hardcoded `0.065` throughout)
- **Trading days per year:** 252
- **Sortino:** `sqrt(252) × mean(excess_ret) / sqrt(mean(min(excess_ret, 0)²))` — downside deviation, not std
- **Information Ratio:** `(active_daily.mean() / active_daily.std()) × sqrt(252)` — daily active returns
- **CAGR columns** named `cagr_3year` / `cagr_5year` (not "rolling_return" — those are point-to-point CAGRs)
- Metrics return `None` if data covers < 90% of the requested period (e.g. < 3.24 years for 3Y CAGR)

### Key conventions

**Mutual Funds & Benchmarks:**
- All blocking I/O inside async functions must use `asyncio.to_thread()` — mftool and `requests` are synchronous.
- `session_factory()` (not `get_db`) is used when opening a session outside of a request context (background tasks, `sync_all_funds`).
- `metrics_calculated_at` is always stored with `datetime.now(timezone.utc)` — never naive.
- NAV values ≤ 0 are rejected at the CRUD layer before insert.
- `_apply_fund_filters()` in `crud.py` is the single source of truth for FundMaster filter predicates — always use it in both count and list queries.
- GIN trigram indexes on `amc_name` and `scheme_category` require `CREATE EXTENSION IF NOT EXISTS pg_trgm` to be run once on the PostgreSQL instance.

**Stock Market Data:**
- OHLCV price data sourced via yfinance; batch processing in chunks of 50 to avoid API timeouts.
- Price ingestion jobs use `asyncio.to_thread()` for yfinance calls (synchronous blocking I/O).
- `price_data` upserted with ON CONFLICT DO NOTHING to allow safe re-runs of backfill.
- LATERAL JOINs used in stock queries for latest price/rating to avoid N+1 queries.
- Full-text search on company_name uses PostgreSQL tsvector + plainto_tsquery (GIN trigram index).
- Stock master registry has no foreign keys to MF tables (complete schema separation).

### Frontend state management

- **Redux slices** own server data:
  - `fundsSlice` — MF listing, detail, filtering, pagination
  - `syncSlice` — job polling (JIT sync)
  - `compareSlice` — up to 4 funds for comparison
  - `indicesSlice` — benchmarks (Nifty indices)
  - `stocksSlice` — stock listing, detail, screener, filters (sector, market_cap, rating, financial ratios)
- **Context** owns session state: `AuthContext` (JWT, login/logout), `ThemeContext` (dark mode tokens).
- Axios client (`src/api/`) injects `Authorization: Bearer` from `AuthContext` automatically.
- The frontend polls `GET /api/v1/metrics/{code}/status` every 3 s until a sync job reaches COMPLETED/FAILED (JIT sync pattern).
- Stock listing page uses dispatch(fetchStocks(filters)) with pagination + sector filtering.

### Stock API Endpoints (Phase 3 — Fundamentals & Shareholding)

**GET /api/v1/stocks/{symbol}/fundamentals** — Financial statements
- Query params: `statement_type` (PL|BS|CF), `period_type` (annual|quarterly), `limit` (5, max 20)
- Returns: Periods with normalized financial data as JSON (revenue, net_profit, borrowings, etc.)
- Example: `GET /stocks/BHARTIARTL/fundamentals?statement_type=PL&limit=5`

**GET /api/v1/stocks/{symbol}/shareholding** — Ownership by period
- Query params: `limit` (8, max 20)
- Returns: Shareholding records with promoter%, FII%, DII%, public%, pledged% by period
- Example: `GET /stocks/BHARTIARTL/shareholding?limit=8`

### Stock API Endpoints (Phase 4 — Ratio Engine & Screener)

**GET /api/v1/screener** — Dynamic stock screener with 15+ filters
- Query params: 
  - **Valuation**: `min_pe`, `max_pe`, `min_pb`, `max_pb`
  - **Profitability**: `min_roe`, `min_roce`, `min_pat_margin`, `min_ebitda_margin`
  - **Growth**: `min_revenue_growth`, `min_pat_growth`
  - **Leverage**: `max_debt_equity`, `min_interest_cov`
  - **Quality**: `min_cfo_to_pat`
  - **Stock filters**: `sector`, `market_cap_cat`, `rating_label`
  - **Pagination**: `page` (1), `limit` (25, max 100), `sort_by` (total_score|roe|pe_ratio|revenue_growth|pat_margin|symbol), `order` (asc|desc)
- Returns: Paginated results with latest price, ratios, and rating + total count
- Dynamic WHERE clause builder avoids SQL injection; filters only applied for non-None values
- LATERAL JOINs for efficiency: latest financial_ratios, price_data, stock_ratings
- Example: `GET /screener?min_roe=15&max_pe=25&sector=Banking&limit=10`

**GET /api/v1/stocks/{symbol}/ratios** — Financial ratio history
- Query params: `period_type` (annual|ttm), `limit` (5, max 20)
- Returns: 17-column ratio time-series: PE, PB, PS, ROE, ROCE, ROA, margins, growth rates, leverage, quality metrics
- Example: `GET /stocks/RELIANCE/ratios?period_type=annual&limit=5`

**GET /api/v1/compare** — Compare up to 5 stocks side-by-side
- Query param: `symbols` (comma-separated, max 5)
- Returns: Array of stocks with latest price, ratios, fundamental score, technical score
- Example: `GET /compare?symbols=RELIANCE,INFY,TCS,WIPRO,HCLTECH`

### Financial Ratio Engine (Phase 4)

**Ratios Computed (`pipeline/ratio_engine.py`):**

17 ratios calculated from normalized financial statements + price data:
- **Valuation**: PE (price/EPS), PB (price/book_value), PS (price/sales)
- **Profitability**: ROE (net_profit/equity), ROCE (EBIT/capital_employed), ROA (net_profit/assets)
- **Margins**: PAT margin (net_profit/revenue), EBITDA margin, Operating margin
- **Growth**: Revenue growth (YoY %), PAT growth (YoY %), EPS growth (YoY %)
- **Leverage**: Debt/Equity, Current ratio, Interest coverage (EBIT/interest)
- **Quality**: CFO-to-PAT (operating_cash_flow/net_profit), Book value per share

**Safe Division Pattern:**
- All ratios use `safe_div()` helper: returns None if denominator is 0 or None
- Prevents division-by-zero crashes; invalid ratios omitted from results
- Alternative column names handled: "sales" vs "revenue", "net_worth" vs "equity"

**YoY Growth Calculation:**
- `(current_period - previous_period) / abs(previous_period) * 100`
- Handles negative-to-positive transitions (e.g., loss to profit)
- Returns None if previous_period is missing or zero

**Storage & Compute:**
- `financial_ratios` table: upserted after every fundamental scrape
- One row per stock per period (annual only)
- Ratios recomputed on-demand via `/stocks/{symbol}/ratios` endpoint
- Cache via latest period query: `ORDER BY period_end DESC LIMIT 1`

### Screener Filtering Strategy (Phase 4)

**Dynamic WHERE Clause Builder:**
```python
filters = ["s.is_active = TRUE", "s.is_index = FALSE"]
params = {"limit": limit, "offset": offset}

def add_filter(col, op, val, key):
    if val is not None:
        filters.append(f"{col} {op} :{key}")
        params[key] = val

# Build filters only for non-None params
add_filter("r.pe_ratio", ">=", min_pe, "min_pe")
add_filter("r.roe", ">=", min_roe, "min_roe")
# ... etc ...

where = " AND ".join(filters)
sql = f"... WHERE {where} ..."
```

**Key Benefits:**
- No string concatenation of user input → SQL injection safe
- Parametrized queries (`:key` placeholders)
- Optional filters: only added to WHERE if value is not None
- Clear audit trail: `filters_applied` in response shows which filters were active

**LATERAL JOIN Optimization:**
```sql
LEFT JOIN LATERAL (
    SELECT roe, roce, pat_margin, pe_ratio, ...
    FROM financial_ratios
    WHERE stock_id = s.id AND period_type = 'annual'
    ORDER BY period_end DESC LIMIT 1
) r ON TRUE
```
- Avoids N+1 queries (single query gets latest ratio per stock)
- Efficient: PostgreSQL materializes subquery only for matching stocks
- Fallback to NULL for stocks with no ratio data (LEFT JOIN)

### Design System (Nivesh Elite — Phase 3)

**Color Palette:**
- **Primary (Gold)**: #e9c349 — Accents, highlights, hero elements
- **Secondary (Emerald)**: #66dd8b — Interactive elements, success states
- **Background**: #0f1419 — Dark navy main canvas
- **Surface Container**: #1b2025 — Card backgrounds
- **On-Surface**: #dee3ea — Primary text (high contrast)
- **On-Surface-Variant**: #c6c6cc — Secondary text, labels
- **Error**: #ffb4ab — Losses, destructive actions

**Effects & Styling:**
- **Glassmorphism**: `rgba(48, 53, 59, 0.6)` background + `backdrop-filter: blur(20px)` on all cards/panels
- **Glass borders**: Top/left 1px `rgba(69, 70, 76, 0.2)` for frosted effect
- **Hover state**: Scale 105%, opacity 0.6 → 0.7
- **Gold gradient**: `linear-gradient(135deg, #e9c349 0%, #9d7e00 100%)` for hero accents
- **Emerald glow**: `drop-shadow(0 0 8px rgba(102, 221, 139, 0.1))` for highlights

**Typography:**
- **Manrope** (600–800 weight): Headlines, body text
- **Inter** (300–600 weight): Labels, small UI text
- **Scale**: h1 (2.25rem bold), h3 (1.125rem bold), p (1rem), label (0.75rem uppercase)

**Components:**
- **Cards**: Rounded-xl (0.75rem) glass background + hover scale effect
- **Buttons**: Emerald `secondary` background, variant text on hover
- **Chips**: Rounded-full with proper padding and color per type
- **Tables**: Glass container with subtle hover row highlighting
- **Tabs**: Gold underline on active tab, emerald text accent
- **Badges**: Status-colored (emerald success, error loss, gold warning)

### Fundamental Scraper (Phase 3)

**Indian Number Parsing (`pipeline/normalizer.py`):**
- Handles: "87,939", "(12,345)" (negative), "1,23,456" (lakh), "12.34%", empty strings, "N/A"
- Converts to typed Python float or None
- Test coverage: 15 unit tests, 100% pass

**Financial Statement Storage:**
- Period-wise P&L, Balance Sheet, Cash Flow in `financial_statements` table
- Normalized JSON in `data` column: `{"revenue": 87939.0, "net_profit": 5048.0, ...}`
- Checksum deduplication prevents duplicate writes on re-run
- Raw ScreenerScraper output stored for audit trail

**Shareholding Tracking:**
- `shareholding_pattern` table: promoter/FII/DII/public/pledged percentages by period
- One record per quarter/month extracted from screener.in
- Upserted with ON CONFLICT to handle re-runs

**Scheduler:**
- Sunday 02:00 IST: `run_fundamental_scrape_all()` via APScheduler
- Rate-limited: 2–5 second delays between stocks (polite scraping)
- Full error logging via `audit_job` context manager

### Mandatory Task: Maintain Changelog
- Ensure a file exists at memory/changelog.md. Create it if it does not exist.
- At the end of each session, update this file with all changes made.
- For each modified file, add a one-line summary describing the change.
- Use this file as the single source of truth to track all historical changes.
- Always review memory/changelog.md before making new changes to understand prior updates.
