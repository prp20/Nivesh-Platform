# nivesh-server — Cloud FastAPI Application

## Purpose

Cloud-hosted FastAPI application deployed on Render.com. Owns all canonical financial data (stocks, mutual funds, market data). Performs all analytics computation. Exposes a versioned REST API consumed by `nivesh-client`.

## Stack

- **FastAPI** + **Uvicorn** — API framework
- **SQLAlchemy (async)** + **asyncpg** — ORM → PostgreSQL (Supabase)
- **Alembic** — DB migrations
- **APScheduler** — ingestion pipeline scheduling (IST timezone)
- **pandas + TA-Lib** — technical indicator computation
- **LangGraph + langchain-groq** — fundamental scoring pipeline

## Key Files

| File | Role |
|---|---|
| `app/main.py` | FastAPI entry point, lifespan (scheduler start/stop) |
| `app/config.py` | Pydantic Settings — reads all env vars |
| `app/database.py` | Async SQLAlchemy engine → Supabase PostgreSQL |
| `app/security.py` | JWT encode/decode, bcrypt, auth deps |
| `app/models.py` | SQLAlchemy ORM models |
| `app/schemas.py` | Legacy local schemas (being migrated to `nivesh-shared`) |
| `app/analytics.py` | Fund metrics: Sharpe, Sortino, Alpha, Beta |
| `app/sync.py` | AMFI NAV sync logic |
| `app/routers/` | All FastAPI route handlers |
| `app/ingestion/` | (Phase 3) APScheduler jobs — NSE bhavcopy, AMFI, FII/DII |
| `alembic/` | PostgreSQL migration files |
| `scripts/` | One-time seed and setup scripts |

## Database Connection Rules

**CRITICAL — Supabase connection:**
- Runtime (FastAPI): use **Supavisor pooler URL** (port `6543`) — `DATABASE_URL`
- Migrations (Alembic): use **direct URL** (port `5432`) — `ALEMBIC_URL`
- SQLAlchemy config: `pool_size=5`, `max_overflow=5`, `pool_pre_ping=True`

```python
# CORRECT runtime URL
postgresql://postgres.[ref]:[pwd]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# CORRECT Alembic URL (migrations only)
postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres
```

## Schema Imports

Prefer importing from `nivesh_shared.schemas.*` over local `app.schemas`:

```python
# Preferred (shared)
from schemas.funds import FundMasterRead, FundMetricsResponse
from schemas.stocks import StockListResponse, ScreenerResponse
from schemas.market import BenchmarkMasterRead, SyncJobRead
from schemas.auth import TokenResponse, LoginRequest

# Allowed for server-internal types only
from app.schemas import ScoringStateSchema  # LangGraph state — not shared
```

## Environment Variables

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Supavisor pooler URL — port 6543 |
| `ALEMBIC_URL` | Direct connection URL — port 5432 — migrations only |
| `SECRET_KEY` | JWT signing key — Render auto-generates |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` |
| `ENVIRONMENT` | `production` or `development` |

## Running Locally

```bash
# From repo root
pip install -r requirements-dev.txt

cd nivesh-server
cp .env.example .env  # fill in DATABASE_URL
uvicorn app.main:app --port 8000 --reload
```

## Migrations

```bash
cd nivesh-server
export ALEMBIC_URL="postgresql://..."
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Tests

```bash
cd nivesh-server
pytest tests/ -v
```

## Deployment (Render)

- Push to `main` → GitHub Actions triggers Render deploy
- Root dir on Render: `nivesh-server`
- Build: `pip install -e ../nivesh-shared -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `GET /health`
