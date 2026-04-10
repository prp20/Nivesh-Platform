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

**MF tables** (fund_master, benchmark_master, nav_history, metrics, sync_jobs): managed via `Base.metadata.create_all` on startup — no migration files.

**Stock tables** (stocks, price_data, financial_statements, etc.): managed via Alembic. On first checkout run:

```bash
cd backend
source venv/bin/activate
alembic upgrade head    # creates all 9 stock tables + indexes
```

To reset MF benchmark data (destructive):

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

### Required Environment Variables

```bash
# backend/.env  (create this file — not committed)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/nivesh
SECRET_KEY=any-secret           # only required when ENABLE_AUTH=true
ENABLE_AUTH=false               # set true to enforce JWT on write endpoints
ADMIN_PASSWORD=secret           # required by recompute_funds_metrics.py when auth on

# frontend/.env.development  (already committed — no action needed for local dev)
VITE_API_URL=http://localhost:8000/api/v1
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

Full database schema, table definitions, coding conventions, and storage patterns: see [`docs/DATABASE.md`](docs/DATABASE.md).

Full API endpoint reference (all phases): see [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

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

Frontend state management and design system: see [`docs/FRONTEND.md`](docs/FRONTEND.md).

### Fundamental Scraper Scheduler

- Sunday 02:00 IST: `run_fundamental_scrape_all()` via APScheduler (`backend/pipeline/scheduler.py`)
- Rate-limited: 2–5 second delays between stocks (polite scraping)
- Full error logging via `audit_job` context manager
- Storage patterns and number parsing: see [`docs/DATABASE.md`](docs/DATABASE.md)

### Frontend Build Gotchas

- **Vite 8 / Rolldown**: `manualChunks` in `vite.config.js` must be a **function** (`manualChunks(id) { ... }`), not an object literal (`{ 'vendor-react': [...] }`). The object form is silently ignored by Rolldown and produces no vendor splitting.
- **ESLint `motion` errors**: Pre-existing lint errors for `motion` (from `framer-motion`) are **not regressions** — `eslint-plugin-react` is not installed so the linter can't resolve JSX namespace usage (`motion.div`, `motion.section`). `npm run build` still succeeds. Do not remove `motion` imports to fix these.

### Mandatory Task: Maintain Changelog
- Ensure a file exists at memory/changelog.md. Create it if it does not exist.
- At the end of each session, update this file with all changes made.
- For each modified file, add a one-line summary describing the change.
- Use this file as the single source of truth to track all historical changes.
- Always review memory/changelog.md before making new changes to understand prior updates.
