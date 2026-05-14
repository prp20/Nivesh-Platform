# Architecture Overview

Nivesh is a personal stock and mutual fund analytics platform structured as a monorepo with three pip packages.

---

## Package Layout

```
stock_platform/
├── nivesh-server/     ← Cloud FastAPI (PostgreSQL via Supabase)
├── nivesh-client/     ← Local FastAPI + React (SQLite)
├── nivesh-shared/     ← Shared Pydantic schemas (pip-installable)
├── backend/           ← LEGACY — original monolith, reference only
├── frontend/          ← LEGACY — original frontend, reference only
├── docs/              ← This documentation
└── requirements-dev.txt
```

### Package responsibilities

| Package | Deployed on | Database | Purpose |
|---------|------------|----------|---------|
| `nivesh-server` | Render.com | Supabase PostgreSQL | All market data, analytics, ingestion pipelines |
| `nivesh-client` | User's machine | SQLite (`~/.nivesh/`) | Portfolio, local UI, agent layer |
| `nivesh-shared` | Both (pip install) | — | Shared Pydantic v2 schemas (API contract) |

**Core rule:** The server owns all canonical market data. The client never connects directly to PostgreSQL — all data flows via the server REST API.

---

## Data Flow

```
AMFI / NSE / Yahoo Finance
        │
        ▼
  nivesh-server  ──── Supabase PostgreSQL
  (Render.com)         (market data, all tables)
        │
        │  REST API (JSON)
        ▼
  nivesh-client  ──── SQLite (~/.nivesh/)
  (local machine)     (portfolio, JWT tokens, TTL cache)
        │
        ▼
  React UI (browser)
```

---

## nivesh-server

Cloud FastAPI application. Owns all financial data and computation.

### Key files

| Path | Role |
|------|------|
| `app/main.py` | FastAPI entry, lifespan (scheduler start/stop) |
| `app/config.py` | Pydantic Settings — reads env vars |
| `app/database.py` | Async SQLAlchemy engine → Supabase |
| `app/security.py` | JWT encode/decode, bcrypt |
| `app/routers/` | Route handlers |
| `app/analytics.py` | Fund metrics: Sharpe, Sortino, Alpha, Beta |
| `app/sync.py` | AMFI NAV sync (bulk, per-fund EtlRun tracking) |
| `pipeline/` | Ingestion pipeline package — all 7 APScheduler jobs |
| `pipeline/scheduler.py` | `AsyncIOScheduler` + `configure_scheduler()` — 7 IST cron jobs |
| `pipeline/price_ingestion.py` | yfinance OHLCV delta-sync + AMFI NAV wrapper |
| `pipeline/technical_analysis.py` | TA-Lib indicators (20+), memory-safe one-stock-at-a-time |
| `pipeline/rating_engine.py` | Composite stock rating (5-component, 0–10 scale) |
| `pipeline/fundamental_scraper.py` | Screener.in HTML scraper with checksum dedup |
| `pipeline/ratio_engine.py` | Financial ratio computation from JSONB statements |
| `pipeline/metric_recompute.py` | PE/PB/PS refresh from latest close + fund metrics |
| `pipeline/base.py` | `BasePipeline` ABC — EtlRun lifecycle (RUNNING → COMPLETED/FAILED/PARTIAL) |
| `fundamental_scorer/` | LangGraph AI fundamental scoring (Fetch → Compute → Reason → Persist) |
| `fund_scorer/` | LangGraph fund quality scoring with Groq LLM |
| `alembic/` | Alembic migrations (18 files) |
| `scripts/seed/` | One-time data seeding scripts |
| `data/` | CSV files for initial seeding |

### Ingestion pipeline

All pipelines run on the Render server via APScheduler (`AsyncIOScheduler`, IST timezone).

| Job ID | Schedule (IST) | What it does |
|--------|---------------|--------------|
| `yf_price` | Mon–Fri 19:00 | yfinance OHLCV delta-sync for all active stocks |
| `benchmark_nav` | Daily 19:30 | Benchmark index NAV from yfinance |
| `technical_analysis` | Mon–Fri 20:00 | TA-Lib indicators (SMA/EMA/RSI/MACD/BB/ATR/ADX/etc.) |
| `amfi_nav` | Daily 21:30 | AMFI mutual fund NAV via `app/sync.py` |
| `stock_ratings` | Daily 21:00 | Composite stock rating (5-component) |
| `fund_metrics` | Daily 23:00 | Fund Sharpe/Sortino/Alpha/Beta recompute |
| `screener_fundamentals` | Sunday 06:00 | Screener.in financial statement scrape |

Every job creates an `etl_runs` row (status: RUNNING → COMPLETED / FAILED / PARTIAL). Duplicate runs are blocked by a partial unique index on `(pipeline_name, entity_id) WHERE status = 'RUNNING'`.

### LangGraph AI scoring

Two LangGraph pipelines run on demand via admin HTTP endpoints:

**`fundamental_scorer/`** — 4-stage pipeline per stock:
1. **Fetch** — load `financial_statements` from DB
2. **Compute** — deterministic PL/BS/CF scoring (0–10, weighted)
3. **Reason** — Groq LLM (llama3-8b) generates 2–3 sentence qualitative verdict; falls back to template if `GROQ_API_KEY` unset
4. **Persist** — upsert to `fundamental_scores`

**`fund_scorer/`** — 2-stage pipeline per fund:
1. Compute quantitative score from `fund_metrics` (returns, Sharpe, alpha, drawdown)
2. Groq LLM verdict with template fallback

### Database connection rules

Two URLs are required — do not mix them up:

| URL | Env var | Port | Use |
|-----|---------|------|-----|
| Supavisor pooler | `DATABASE_URL` | `6543` | Runtime (FastAPI, seed scripts) |
| Direct | `ALEMBIC_URL` | `5432` | Alembic migrations only |

The pooler (6543) uses IPv4 and works on Render free tier. The direct URL uses IPv6 and is only needed for DDL during migrations.

### Schema import pattern

```python
# Correct — from shared package
from schemas.funds import FundMasterRead, FundMetricsResponse
from schemas.stocks import StockListResponse, ScreenerResponse
from schemas.market import BenchmarkMasterRead
from schemas.auth import TokenResponse

# Allowed — server-internal only
from app.schemas import ScoringStateSchema  # LangGraph state
```

---

## nivesh-client

Local FastAPI + React application. Stores only user-private data.

### Key rules

- SQLite at `~/.nivesh/nivesh_client.db` — auto-created on first run
- JWT tokens stored in SQLite `auth_tokens` table, **never** in browser localStorage
- All market data fetched from `nivesh-server` and cached locally with TTL
- Never connects directly to Supabase
- Never runs heavy computation (pandas-ta, scipy) — server pre-computes all indicators

---

## nivesh-shared

Pip-installable package containing all Pydantic v2 schemas used by both server and client.

### Schema files

| File | Contains |
|------|---------|
| `schemas/funds.py` | FundMaster, FundMetrics, FundNav, Comparison schemas |
| `schemas/stocks.py` | Stock, Screener, FundamentalScore schemas |
| `schemas/market.py` | Benchmark, MarketSnapshot, SyncJob schemas |
| `schemas/auth.py` | TokenResponse, LoginRequest schemas |

### Install pattern

```bash
# In development (editable)
pip install -e ./nivesh-shared

# In production (Render build)
pip install -e ../nivesh-shared -r requirements.txt
```

Any type that appears in both server and client responses belongs in `nivesh-shared`. Server-internal types (LangGraph state, ORM internals) stay in `app/schemas.py`.

---

## Implementation Phases

| Phase | Status | Description |
|-------|--------|-------------|
| P0 | Done | Monorepo restructure |
| P1 | Done | Supabase DB setup — 18 Alembic migrations + seed scripts |
| P2 | Done | Server Core API on Render — auth, EtlRun model, delta-sync, Render deploy |
| P3 | Done | Ingestion pipeline — APScheduler (7 IST cron jobs), pipeline/ package, LangGraph AI scoring |
| P4 | Pending | Client SQLite + local API |
| P5 | Pending | JWT auth + sync engine |
| P6 | Pending | Agentic layer |
| P7 | Pending | React UI |
| P8 | Pending | CI/CD + production hardening |

---

## Known Blockers

None open. BLOCKER-001 (SyncJob/PipelineAudit → EtlRun migration) was resolved in Phase 2.
