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
# ta-lib requires the C library before pip install:
#   Ubuntu/Debian: sudo apt-get install -y libta-lib-dev
#   OR compile from source: see ta-lib/ dir in repo root (extracted ta-lib-0.4.0-src.tar.gz)
docker-compose up -d                         # start PostgreSQL
uvicorn app.main:app --port 8000 --reload    # start API
```

**API docs available at:** `http://localhost:8000/docs`
**Health check:** `curl http://localhost:8000/api/health`

### Frontend

```bash
cd frontend
npm install
npm run dev      # dev server at http://localhost:5173
npm run build    # production build (output: frontend/dist/)
npm run lint     # ESLint
```

### Tests

```bash
cd backend
source venv/bin/activate

pytest                                        # run all tests (in-memory SQLite, no DB needed)
pytest tests/test_funds.py                   # run a single test file
pytest tests/test_funds.py::test_list_funds  # run a single test function
pytest -x                                    # stop on first failure
pytest -v                                    # verbose output
```

Tests use in-memory SQLite via `conftest.py`. Stock table tests that require PostgreSQL JSONB are skipped automatically. `asyncio_mode = auto` (pytest-asyncio) — no `@pytest.mark.asyncio` needed.

### Database / Migrations

**MF tables** (fund_master, benchmark_master, nav_history, metrics, sync_jobs): managed via `Base.metadata.create_all` on startup — `pg_trgm` extension is created automatically before `create_all` runs.

**Stock tables** (stocks, price_data, financial_statements, etc.): managed via Alembic. The migration is idempotent — safe to run even if tables already exist (created by `create_all`):

```bash
cd backend
source venv/bin/activate
alembic upgrade head    # runs 001_add_stock_tables.py — creates all stock tables + indexes
```

**DB setup utility** (used by setup scripts, also available standalone):

```bash
python3 scripts/db_setup.py --check         # exit 0 if any tables exist, 1 if none
python3 scripts/db_setup.py --drop-all      # drop ALL tables + alembic_version
python3 scripts/db_setup.py --drop-mf       # drop only MF tables
python3 scripts/db_setup.py --drop-stocks   # drop stock tables + reset alembic_version
```

To reset MF benchmark data (destructive):

```bash
cd backend
python3 migrate.py --force    # requires --force flag to prevent accidental data loss
```

### Seed & ETL Scripts (run from `backend/`)

```bash
source venv/bin/activate

# Mutual Fund initial load:
python3 scripts/seed_funds.py          # seed fund_master records
python3 scripts/seed_indices.py        # seed benchmark/index records from CSV
python3 scripts/sync_data.py           # full MF sync: NAV history + metrics

# Stock Master & Price Data (Phase 1–2):
python3 scripts/seed/seed_stock_master.py        # seed 18 large-cap stocks + 3 indices
python3 scripts/seed/backfill_prices.py 1y       # backfill 1 year of OHLCV (faster for dev)
python3 scripts/seed/backfill_prices.py 5y       # backfill 5 years of OHLCV (full history)

# Rebuild / one-off:
python3 scripts/rebuild_data.py                  # trigger price backfill via pipeline module
python3 scripts/demo_fundamental_sync.py         # test run fundamental scraper for one stock
python3 scripts/db_init.py                       # initialise DB tables (alternative to alembic)
```

### Setup Scripts (cross-platform, interactive)

```bash
./setup/setup.sh          # Linux / macOS
.\setup\setup.ps1         # Windows PowerShell (recommended on Windows)
setup\setup.bat           # Windows CMD
```

Each script walks through PostgreSQL setup, venv, env file generation, DB migrations, optional seeding (MF only / Stocks only / Both), and frontend build.

### Required Environment Variables

```bash
# backend/.env  (create this file — not committed)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/nivesh
SECRET_KEY=any-secret           # only required when ENABLE_AUTH=true
ENABLE_AUTH=false               # set true to enforce JWT on write endpoints
ADMIN_PASSWORD=secret           # required for admin-gated scripts when auth on

# frontend/.env.development  (already committed — no action needed for local dev)
VITE_API_URL=http://localhost:8000/api/v1
```

### Stock Market Data Pipeline

Daily scheduled jobs run Mon–Fri (APScheduler, IST):
- **18:30** Price ingestion — last 5 days OHLCV for all active stocks (yfinance)
- **18:40** Index ingestion — Nifty/Sensex indices (separate job so stocks don't block)
- **19:00** Price-dependent ratio refresh — PE, PB, PS, dividend yield
- **19:30** Technical analysis — SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, Stochastic (ta-lib)
- **20:15** Composite rating compute — fundamental + valuation + technical + momentum + shareholding

Weekly scheduled jobs (Sunday):
- **02:00** Fundamental scrape — P&L, Balance Sheet, Cash Flow, shareholding from screener.in (only stocks not updated in 90+ days)
- **09:00** Quarterly ratio compute — ROE, ROCE, D/E, margins, etc. (runs after scrape)

Jobs tracked in `pipeline_audit` table (separate from MF `sync_jobs`). APScheduler configured in `backend/pipeline/scheduler.py`.

Admin trigger endpoints (all require JWT) at `POST /api/v1/pipeline/*` — see `backend/app/routers/pipeline.py`.

---

## Architecture

### Project layout

```
Nivesh-Platform/
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── main.py        # FastAPI app, CORS, lifespan (pg_trgm + create_all), SPA fallback routing
│   │   ├── config.py      # pydantic-settings; startup ValueError if ENABLE_AUTH+dev SECRET_KEY
│   │   ├── database.py    # async engine, session_factory, get_db dependency
│   │   ├── models.py      # SQLAlchemy ORM (16 tables: 7 MF + 9 stocks)
│   │   ├── schemas.py     # Pydantic request/response models
│   │   ├── crud.py        # all DB queries; _apply_fund_filters() for shared filter logic
│   │   ├── analytics.py   # pure-Python financial metric computation (pandas/numpy)
│   │   ├── sync.py        # NAV fetch + metric pipeline; sync_fund_data(), sync_all_funds()
│   │   ├── security.py    # JWT (HS256), bcrypt, get_current_user dependency
│   │   ├── rate_limiting.py  # in-memory per-user/per-endpoint rate limiter (middleware)
│   │   └── routers/       # one file per resource: funds, benchmarks, navs, benchmark_navs,
│   │                      #   metrics, sync, auth, stocks, screener, pipeline
│   ├── pipeline/          # Background job scheduling & data ingestion
│   │   ├── scheduler.py    # APScheduler + configure_scheduler() — 7 cron jobs
│   │   ├── audit.py        # audit_job context manager → pipeline_audit table
│   │   ├── price_ingestion.py    # yfinance OHLCV fetch, backfill, upsert
│   │   ├── fundamental_scraper.py # screener.in P&L/BS/CF/shareholding scrape
│   │   ├── normalizer.py         # raw scraped data → normalised JSONB form
│   │   ├── ratio_engine.py       # quarterly ratios from financial_statements JSONB
│   │   ├── metric_recompute.py   # price-dependent ratios (PE/PB/PS) after daily price load
│   │   ├── technical_analysis.py # ta-lib indicators (SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, Stoch)
│   │   └── rating_engine.py      # composite stock rating (0–100 score across 5 pillars)
│   ├── scripts/           # standalone ETL/seed scripts
│   │   ├── db_setup.py    # DB utility: --check / --drop-all / --drop-mf / --drop-stocks
│   │   └── seed/
│   │       ├── seed_stock_master.py    # seed 18 stocks + 3 indices
│   │       └── backfill_prices.py      # yfinance historical OHLCV backfill
│   ├── alembic/           # Database migration system (PostgreSQL schema management)
│   │   └── versions/001_add_stock_tables.py  # idempotent — skips if stocks already exists
│   ├── data/Nifty_indices/ # CSV files for benchmark NAV history
│   ├── docker-compose.yml # PostgreSQL 16-alpine
│   ├── migrate.py         # destructive benchmark table reset (requires --force)
│   ├── alembic.ini        # Alembic configuration
│   └── requirements.txt
├── frontend/              # React 19 + Vite + Tailwind
│   └── src/
│       ├── api/services/  # Axios service modules (stockService.js, fundService.js, etc.)
│       ├── store/slices/  # Redux Toolkit: fundsSlice, syncSlice, compareSlice, indicesSlice,
│       │                  #   stocksSlice, stockCompareSlice, fundDetailSlice, dashboardSlice
│       ├── context/       # AuthContext (JWT storage), ThemeContext
│       └── pages/         # Dashboard, MFListing, MFDetail, MFCompare, StockListing, StockDetail,
│                          #   StockCompare, Screener, IndicesListing, IndexDetail, Portfolio, Admin, Login
├── setup/                 # Cross-platform interactive setup scripts (sh / ps1 / bat)
├── docs/                  # Architecture docs, API reference, DB schema, frontend guide
├── memory/                # Session memory — changelog.md is the source of truth for changes
├── phases/                # Phase planning documents for feature rollouts
├── TODO.md                # Prioritised audit backlog (P0–P3)
└── start.sh               # One-shot startup script
```

### Three-tier architecture

**Backend (FastAPI + PostgreSQL)**
- REST API at `/api/v1/*` serving financial data
- SQLAlchemy ORM (16 tables: 7 MF + 9 stocks) with async/await
- CORS enabled for frontend (localhost:5173 in dev)
- Metrics are computed on-demand via background workers (sync_jobs pattern)
- Auth optional: write endpoints require JWT when `ENABLE_AUTH=true`; reads are public
- SPA fallback: serves `frontend/dist/index.html` for unmatched routes (production deployment)

**Frontend (React 19 + Vite)**
- SPA deployed to `frontend/dist/`
- Redux Toolkit for server state (funds, metrics, comparisons)
- React Context for session state (auth JWT, theme)
- Axios client auto-injects `Authorization` header from AuthContext
- JIT (just-in-time) sync polling: when metrics needed, polls `/api/v1/metrics/{code}/status` every 3s until completion

**How they connect**
- Frontend calls REST API at base URL (dev: `http://localhost:8000`, prod: same origin)
- Metrics requests are async: returns immediately with existing data, triggers background sync, frontend polls status
- Authentication: frontend stores JWT in AuthContext, Axios injects it on every request

Full database schema, table definitions, coding conventions, and storage patterns: see [`docs/DATABASE.md`](docs/DATABASE.md).

Full API endpoint reference (all phases): see [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

### Request → response flow (MF)

1. **List/detail reads** (`GET /funds/`, `GET /metrics/{code}`) — direct async DB queries via `crud.py`, eager-load with `joinedload`.
2. **Metrics request (GET /metrics/{code})** — checks cache age (24 h). If stale or missing, creates a `SyncJob` row and dispatches `background_sync_wrapper` via FastAPI `BackgroundTasks`. Returns immediately with current (possibly null) metrics and job status.
3. **Background sync** (`sync.sync_fund_data`) — fetches NAV via mftool (wrapped in `asyncio.to_thread`), fetches AUM/TER from Captnemo API (also `asyncio.to_thread`), computes all metrics in `analytics.compute_all_metrics`, upserts to `fund_metrics`, marks job COMPLETED/FAILED.
4. **`sync_all_funds`** — opens a **fresh `session_factory()` per fund** so session failure in one fund does not affect others.

### Database access patterns

- **`get_db`** (`app/database.py`) — SQLAlchemy `AsyncSession` via FastAPI dependency injection. Used in all routers.
- **`raw_connection`** (`app/database.py`) — raw `asyncpg` connection for direct SQL. Used in all `pipeline/` modules (ratio_engine, technical_analysis, rating_engine, etc.) because `asyncpg.executemany` is significantly faster than the ORM for batch upserts.

### Auth pattern

`security.get_current_user` is a FastAPI dependency. When `ENABLE_AUTH=False` (dev default) it returns `"dev_user"` without touching the token. When `True`, it validates the JWT and raises 401. Write endpoints (`POST`, `PUT`, `DELETE`) depend on it; public read endpoints do not. The `GET /metrics/{code}` endpoint is intentionally public but validates `scheme_code` format before triggering any sync.

### Analytics formulas (analytics.py)

- **Risk-free rate:** 6.5% annualised (hardcoded `0.065` throughout, sourced from `app/constants.py`)
- **Trading days per year:** 252
- **Sortino:** `sqrt(252) × mean(excess_ret) / sqrt(mean(min(excess_ret, 0)²))` — downside deviation, not std
- **Information Ratio:** `(active_daily.mean() / active_daily.std()) × sqrt(252)` — daily active returns
- **CAGR columns** named `cagr_3year` / `cagr_5year` (not "rolling_return" — those are point-to-point CAGRs)
- Metrics return `None` if data covers < 90% of the requested period (e.g. < 3.24 years for 3Y CAGR)

Frontend state management and design system: see [`docs/FRONTEND.md`](docs/FRONTEND.md).

### Fundamental Scraper

- Rate-limited: 2–5 second delays between stocks (polite scraping from screener.in)
- Only scrapes stocks not updated in the last 90 days
- Raw data normalised via `pipeline/normalizer.py` before storage
- Storage patterns and number parsing: see [`docs/DATABASE.md`](docs/DATABASE.md)

### Frontend Build Gotchas

- **Vite 8 / Rolldown**: `manualChunks` in `vite.config.js` must be a **function** (`manualChunks(id) { ... }`), not an object literal (`{ 'vendor-react': [...] }`). The object form is silently ignored by Rolldown and produces no vendor splitting.
- **ESLint `motion` errors**: Pre-existing lint errors for `motion` (from `framer-motion`) are **not regressions** — `eslint-plugin-react` is not installed so the linter can't resolve JSX namespace usage (`motion.div`, `motion.section`). `npm run build` still succeeds. Do not remove `motion` imports to fix these.

### Mandatory Task: Maintain Changelog
- Ensure a file exists at `memory/changelog.md`. Create it if it does not exist.
- At the end of each session, update this file with all changes made.
- For each modified file, add a one-line summary describing the change.
- Use this file as the single source of truth to track all historical changes.
- Always review `memory/changelog.md` before making new changes to understand prior updates.
