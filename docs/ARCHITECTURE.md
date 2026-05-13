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
| `app/sync.py` | AMFI NAV sync |
| `app/ingestion/` | (Phase 3) APScheduler jobs |
| `alembic/` | Alembic migrations (raw SQL, 18 files) |
| `scripts/seed/` | One-time data seeding scripts |
| `data/` | CSV files for initial seeding |

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
| P2 | Pending | Server Core API on Render |
| P3 | Pending | Ingestion pipeline (NSE bhavcopy, AMFI, FII/DII) |
| P4 | Pending | Client SQLite + local API |
| P5 | Pending | JWT auth + sync engine |
| P6 | Pending | Agentic layer |
| P7 | Pending | React UI |
| P8 | Pending | CI/CD + production hardening |

---

## Known Blockers

See `BLOCKERS.md` in the repo root for deferred work that must be resolved before certain features go live.

Current open blockers:
- **BLOCKER-001** — App code still references old `sync_jobs` / `pipeline_audit` tables. The new DB only has `etl_runs`. Affects: `crud.py`, `routers/sync.py`, `app/sync.py`, `backend/pipeline/audit.py`.
