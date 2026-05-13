# Nivesh Platform — Phased Implementation Plan
## Server/Client Split · Render.com + Supabase + SQLite + JWT
### Version 1.0 · May 2026

---

## Table of Contents

1. [Infrastructure Stack Decision](#1-infrastructure-stack-decision)
2. [Platform Constraints & Gotchas](#2-platform-constraints--gotchas)
3. [Phase Overview](#3-phase-overview)
4. [Phase 0 — Repo Restructure](#phase-0--repo-restructure)
5. [Phase 1 — Supabase Database Setup](#phase-1--supabase-database-setup)
6. [Phase 2 — Server: Core API on Render](#phase-2--server-core-api-on-render)
7. [Phase 3 — Server: Ingestion Pipeline](#phase-3--server-ingestion-pipeline)
8. [Phase 4 — Client: SQLite + Local API](#phase-4--client-sqlite--local-api)
9. [Phase 5 — Client: JWT Auth + Sync Engine](#phase-5--client-jwt-auth--sync-engine)
10. [Phase 6 — Client: Agentic Layer](#phase-6--client-agentic-layer)
11. [Phase 7 — Client: UI Adaptation](#phase-7--client-ui-adaptation)
12. [Phase 8 — CI/CD + Production Hardening](#phase-8--cicd--production-hardening)
13. [Environment Variables Reference](#13-environment-variables-reference)
14. [Dependency Reference](#14-dependency-reference)
15. [Risk Register](#15-risk-register)

---

## 1. Infrastructure Stack Decision

| Concern | Choice | Rationale |
|---|---|---|
| Server hosting | **Render.com** | Native FastAPI support, git-push deploy, no Docker required for start, free tier available, Singapore region for low latency to India |
| Cloud DB | **Supabase (PostgreSQL 16)** | Managed Postgres, built-in connection pooler (Supavisor), free tier 500MB + 60 direct / 200 pooler connections, dashboard SQL editor, no separate DB server to manage |
| Local DB | **SQLite via SQLAlchemy** | Zero install, portable, Alembic migrations work identically to server PostgreSQL |
| Auth | **JWT (existing `security.py`)** | Already implemented in the codebase — extend, don't replace |
| HTTP client | **httpx (async)** | Already in Python ecosystem, async-native, built-in retry support |
| Scheduler | **APScheduler (existing)** | Already used in the project — keep it |
| Analytics | **pandas, pandas-ta, scipy** | Already used in the project — keep as-is |
| ORM | **SQLAlchemy (async)** | Already used in the project — keep as-is |
| Migrations | **Alembic** | Already used in the project — extend for client SQLite |

---

## 2. Platform Constraints & Gotchas

### 2.1 Supabase Free Tier Limits

You need to know these before designing the DB connection layer:

| Limit | Free Tier Value | Impact on Nivesh |
|---|---|---|
| Storage | 500 MB | Sufficient for MVP; OHLCV history for 500 stocks × 10Y ≈ 300–400 MB with compression |
| Direct connections | 60 | **Do not use direct connection string from Render** — use Supavisor pooler instead |
| Pooler connections (Supavisor) | 200 client connections → 20 backend connections | More than enough for a single Render instance |
| Active projects | 2 | Use 1 for prod, 1 for dev/staging |
| Backups | None on free tier | Implement your own: GitHub Actions + pg_dump weekly |
| Paused projects | Paused after 1 week of inactivity | Set up a simple cron ping via Render's health check or UptimeRobot |

**Critical connection rule:** Always connect using the **Supavisor transaction-mode pooler URL** (port `6543`), never the direct URL (port `5432`), from Render. Direct connections use IPv6 by default and will fail on Render's free tier. The pooler URL works over IPv4.

```
# WRONG — direct connection, IPv6 only, connection-hungry
postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres

# CORRECT — Supavisor pooler, IPv4, connection-efficient
postgresql://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

Set `pool_pre_ping=True` and `pool_size=5` in SQLAlchemy — do not exceed 10 connections from the app side.

### 2.2 Render Free Tier Limits

| Limit | Free Tier Value | Impact |
|---|---|---|
| Compute | 512 MB RAM, shared CPU | Enough for FastAPI + APScheduler; pandas jobs may spike — run heavy analytics in off-peak hours |
| Spin-down | Spins down after 15 min inactivity | Add a `GET /health` ping via UptimeRobot (free) to keep it alive |
| Build minutes | 500 min/month | Well within limits for a single service |
| Bandwidth | 100 GB/month | Fine for API traffic |
| Custom domains | 2 domains on Hobby tier | Use for production URLs |

**Upgrade trigger:** Once ingestion jobs run daily (Phase 3), move to Render's **Starter** plan ($7/month) to avoid spin-down interrupting scheduled jobs. Free tier is fine for Phase 0–2.

### 2.3 SQLite in Production (Client-side)

SQLite is appropriate here because the client is a single-user local application. Key rules:

- Set `check_same_thread=False` in SQLAlchemy for SQLite (required for async FastAPI)
- Use WAL mode: `PRAGMA journal_mode=WAL` — enables concurrent reads with one writer
- SQLite file location: `~/.nivesh/nivesh_client.db` (not the project directory — survives reinstalls)
- Alembic migrations run automatically on `nivesh-client` startup via `alembic upgrade head`

---

## 3. Phase Overview

```
Phase 0  │ Repo Restructure                    │ 1–2 days │ No risk
Phase 1  │ Supabase DB Setup                   │ 2–3 days │ Low
Phase 2  │ Server: Core API on Render          │ 4–5 days │ Medium
Phase 3  │ Server: Ingestion Pipeline          │ 5–7 days │ High
Phase 4  │ Client: SQLite + Local API          │ 3–4 days │ Low
Phase 5  │ Client: JWT Auth + Sync Engine      │ 4–5 days │ High
Phase 6  │ Client: Agentic Layer               │ 3–5 days │ Medium
Phase 7  │ Client: UI Adaptation               │ 2–3 days │ Low
Phase 8  │ CI/CD + Production Hardening        │ 2–3 days │ Low
─────────────────────────────────────────────────────────────────
Total    │                                     │ 26–37 days
```

**Parallel tracks** (after Phase 0 completes):
- Track A: Phase 1 → Phase 2 → Phase 3 (server work)
- Track B: Phase 4 → Phase 5 → Phase 6 → Phase 7 (client work)
- Phase 8 depends on both tracks completing

**Realistic wall-clock with parallel tracks: 18–24 days.**

**Sequencing logic:** Phase 5 (client sync) depends on Phase 2 (server API) being deployed and accessible. Everything else can proceed independently.

---

## Phase 0 — Repo Restructure

**Duration:** 1–2 days | **Risk:** None | **Depends on:** Nothing

### Goal

Transform the existing flat `backend/` + `frontend/` structure into a proper monorepo with three packages.

### Current Structure

```
Nivesh-Platform/
├── backend/
│   └── app/           ← everything lives here today
├── frontend/
├── docs/
└── setup/
```

### Target Structure

```
Nivesh-Platform/
├── nivesh-server/     ← cloud FastAPI app (moved from backend/)
├── nivesh-client/     ← local FastAPI + React app
├── nivesh-shared/     ← shared Pydantic schemas
├── docs/
└── setup/
```

### Step-by-Step Tasks

**Task 0.1 — Create directory skeleton**

```bash
mkdir -p nivesh-server/app
mkdir -p nivesh-client/app
mkdir -p nivesh-shared/schemas
```

**Task 0.2 — Move existing backend**

```bash
# Move all existing app code to server
cp -r backend/app/* nivesh-server/app/
cp backend/requirements.txt nivesh-server/requirements.txt
cp -r backend/scripts nivesh-server/scripts
cp -r backend/alembic* nivesh-server/
```

**Task 0.3 — Move existing frontend**

```bash
cp -r frontend/ nivesh-client/frontend/
```

**Task 0.4 — Extract shared schemas**

Move `backend/app/schemas.py` → `nivesh-shared/schemas/`. Split into:
- `nivesh-shared/schemas/funds.py` — FundSummary, FundMetrics, NAVRow
- `nivesh-shared/schemas/stocks.py` — StockSummary, StockDetail, OHLCVRow (new)
- `nivesh-shared/schemas/market.py` — MarketSnapshot, SectorReturn (new)
- `nivesh-shared/schemas/auth.py` — TokenResponse, UserBase

Create `nivesh-shared/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "nivesh-shared"
version = "0.1.0"
dependencies = ["pydantic>=2.0"]
```

**Task 0.5 — Update imports in server app**

In `nivesh-server/app/`, replace:
```python
# Before
from app.schemas import FundSummary

# After
from nivesh_shared.schemas.funds import FundSummary
```

**Task 0.6 — Create root `requirements-dev.txt`**

```text
# Root dev install — links both packages in editable mode
-e ./nivesh-shared
-e ./nivesh-server
-e ./nivesh-client
```

**Task 0.7 — Verify existing tests still pass**

```bash
cd nivesh-server && pip install -e ../nivesh-shared -r requirements.txt
uvicorn app.main:app --port 8000
# Confirm all existing routes respond
```

**Task 0.8 — Update docs/README**

- Update `README.md` with new folder layout
- Archive old `backend/` and `frontend/` directories (do not delete yet — keep for reference)

### Deliverable

Existing platform works identically from `nivesh-server/`, imports from `nivesh-shared/`, tests pass. No functional changes — pure reorganisation.

---

## Phase 1 — Supabase Database Setup

**Duration:** 2–3 days | **Risk:** Low | **Depends on:** Phase 0

### Goal

Provision Supabase, configure the connection, extend the existing schema with all new tables, and set up Alembic to manage migrations against Supabase.

### Step-by-Step Tasks

**Task 1.1 — Provision Supabase project**

1. Create account at supabase.com
2. Create new project: `nivesh-prod`
3. Region: **Southeast Asia (Singapore)** — lowest latency from India
4. Note down from `Project Settings → Database`:
   - Supavisor pooler URL (port `6543`) — this is your `DATABASE_URL`
   - Direct URL (port `5432`) — this is your `ALEMBIC_URL` (Alembic needs session mode for migrations)

**Task 1.2 — Configure SQLAlchemy for Supabase**

Update `nivesh-server/app/database.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Async engine for FastAPI routes — uses Supavisor pooler (port 6543)
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=5,          # Keep well under Supabase's 20 backend connection limit
    max_overflow=5,
    pool_pre_ping=True,   # Detect stale connections
    pool_recycle=300,     # Recycle connections every 5 minutes
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

**Task 1.3 — Configure Alembic for Supabase**

Update `alembic.ini` to read URL from environment (not hardcoded):

```ini
# alembic.ini
sqlalchemy.url = %(DATABASE_URL)s
```

Update `alembic/env.py`:

```python
import os
from alembic import context

# Use ALEMBIC_URL (direct connection, port 5432) for migrations
# This avoids Supavisor transaction-mode limitations with DDL statements
config.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_URL"])
```

**Task 1.4 — Write new SQLAlchemy models**

Create the following new model files in `nivesh-server/app/models/`:

`stocks.py` — New file:
```python
from sqlalchemy import Column, String, Float, Date, Integer, TIMESTAMP, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CompanyMaster(Base):
    __tablename__ = "company_master"
    symbol          = Column(String, primary_key=True)
    isin            = Column(String, unique=True)
    company_name    = Column(String)
    exchange        = Column(String)          # NSE / BSE
    sector          = Column(String)
    industry        = Column(String)
    market_cap_bucket = Column(String)        # Large / Mid / Small
    listing_date    = Column(Date)
    is_active       = Column(Integer, default=1)

class StockOHLCVDaily(Base):
    __tablename__ = "stock_ohlcv_daily"
    symbol          = Column(String, primary_key=True)
    trade_date      = Column(Date, primary_key=True)
    open            = Column(Float)
    high            = Column(Float)
    low             = Column(Float)
    close           = Column(Float)
    volume          = Column(Integer)
    delivery_pct    = Column(Float)
    adjusted_close  = Column(Float)

class StockTechnicalIndicators(Base):
    __tablename__ = "stock_technical_indicators"
    symbol          = Column(String, primary_key=True)
    trade_date      = Column(Date, primary_key=True)
    rsi_14          = Column(Float)
    macd            = Column(Float)
    macd_signal     = Column(Float)
    macd_hist       = Column(Float)
    bb_upper        = Column(Float)
    bb_mid          = Column(Float)
    bb_lower        = Column(Float)
    ema_20          = Column(Float)
    ema_50          = Column(Float)
    ema_200         = Column(Float)
    atr_14          = Column(Float)
    vwap            = Column(Float)

class StockRatios(Base):
    __tablename__ = "stock_ratios"
    symbol          = Column(String, primary_key=True)
    ratio_date      = Column(Date, primary_key=True)
    pe              = Column(Float)
    pb              = Column(Float)
    ps              = Column(Float)
    ev_ebitda       = Column(Float)
    roe             = Column(Float)
    roce            = Column(Float)
    debt_equity     = Column(Float)
    current_ratio   = Column(Float)
    dividend_yield  = Column(Float)

class FundamentalSnapshot(Base):
    __tablename__ = "fundamental_snapshots"
    symbol          = Column(String, primary_key=True)
    quarter         = Column(String, primary_key=True)  # e.g. "Q4FY25"
    data            = Column(JSON)                       # JSONB in PostgreSQL

class MarketDailySnapshot(Base):
    __tablename__ = "market_daily_snapshot"
    snap_date       = Column(Date, primary_key=True)
    nifty50         = Column(Float)
    sensex          = Column(Float)
    bank_nifty      = Column(Float)
    nifty500        = Column(Float)
    advance_count   = Column(Integer)
    decline_count   = Column(Integer)
    unchanged_count = Column(Integer)
    total_volume_cr = Column(Float)    # in crore INR

class FIIDIIFlow(Base):
    __tablename__ = "fii_dii_flows"
    flow_date       = Column(Date, primary_key=True)
    data            = Column(JSON)     # JSONB: {fii_buy, fii_sell, dii_buy, dii_sell}

class TopMoverDaily(Base):
    __tablename__ = "top_movers_daily"
    snap_date       = Column(Date, primary_key=True)
    data            = Column(JSON)     # JSONB: {gainers: [...], losers: [...]}
```

**Task 1.5 — Generate and run Alembic migrations**

```bash
cd nivesh-server
export ALEMBIC_URL="postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres"
alembic revision --autogenerate -m "add_stocks_market_tables"
alembic upgrade head
```

Verify in Supabase dashboard: all tables created under `public` schema.

**Task 1.6 — Run existing seed scripts against Supabase**

```bash
export DATABASE_URL="postgresql://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
python scripts/seed/seed_benchmarks.py
python scripts/seed/import_nifty_indices.py
python scripts/seed/ingest_isins_amfi.py
python scripts/etl_populate_data.py   # existing MF data — runs against Supabase now
```

### Deliverable

- Supabase project live with complete schema
- Existing MF data (fund_master, nav_history, fund_metrics) migrated to Supabase
- Alembic migrations committed to repo and reproducible

---

## Phase 2 — Server: Core API on Render

**Duration:** 4–5 days | **Risk:** Medium | **Depends on:** Phase 1

### Goal

Deploy the FastAPI server to Render. Implement all REST endpoints with proper auth, pagination, and response envelope. Generate and commit the OpenAPI spec.

### Step-by-Step Tasks

**Task 2.1 — Create `render.yaml`**

Add to repo root `nivesh-server/render.yaml`:

```yaml
services:
  - type: web
    name: nivesh-server
    runtime: python
    rootDir: nivesh-server
    buildCommand: pip install -e ../nivesh-shared -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        sync: false         # Set manually in Render dashboard — never commit
      - key: SECRET_KEY
        generateValue: true # Render auto-generates a secure random value
      - key: ALGORITHM
        value: HS256
      - key: ACCESS_TOKEN_EXPIRE_MINUTES
        value: 15
      - key: REFRESH_TOKEN_EXPIRE_DAYS
        value: 7
      - key: ENVIRONMENT
        value: production
```

**Task 2.2 — Implement health endpoint**

In `nivesh-server/app/main.py`:

```python
@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "version": settings.APP_VERSION,
    }
```

**Task 2.3 — Implement JWT auth router**

`nivesh-server/app/routers/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.security import (
    verify_password, create_access_token, create_refresh_token,
    verify_token, add_token_to_blocklist
)
from app.crud import get_user_by_username
from app.database import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/login")
async def login(form: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(db, form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "access_token": create_access_token({"sub": user.username}),
        "refresh_token": create_refresh_token({"sub": user.username}),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

@router.post("/refresh")
async def refresh(body: RefreshRequest):
    payload = verify_token(body.refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return {
        "access_token": create_access_token({"sub": payload["sub"]}),
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

@router.post("/logout")
async def logout(body: RefreshRequest):
    add_token_to_blocklist(body.refresh_token)  # server-side invalidation
    return {"message": "Logged out"}
```

**Task 2.4 — Implement response envelope helper**

`nivesh-server/app/utils/envelope.py`:

```python
from datetime import datetime, timezone
from typing import Any, Optional

def envelope(data: Any, total: int = None, page: int = 1,
             page_size: int = 50, from_date: Optional[str] = None) -> dict:
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "page": page,
        "page_size": page_size,
    }
    if total is not None:
        meta["total"] = total
    if from_date:
        meta["from_date"] = from_date
    return {"data": data, "meta": meta}
```

**Task 2.5 — Implement all API routers**

Priority order (implement in this sequence — each builds on the last):

1. `routers/funds.py` — Reuse existing routes, adapt to envelope + delta sync
2. `routers/auth.py` — Done in Task 2.3
3. `routers/stocks.py` — New: /stocks, /stocks/{symbol}, /stocks/{symbol}/ohlcv, /technicals, /fundamentals, /ratios/history, /patterns
4. `routers/market.py` — New: /market/snapshot, /market/sectors, /market/movers, /market/fii-dii
5. `routers/sync.py` — New: /sync/status (reads sync_jobs table)

For all time-series endpoints, add `from_date` query parameter:

```python
@router.get("/api/v1/stocks/{symbol}/ohlcv")
async def get_ohlcv(
    symbol: str,
    from_date: Optional[date] = Query(None, description="Delta sync — return only rows after this date"),
    interval: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    rows = await crud.get_ohlcv(db, symbol, from_date, interval)
    return envelope(rows, from_date=str(from_date) if from_date else None)
```

**Task 2.6 — Export OpenAPI spec**

```python
# Add to main.py startup
import json
from fastapi.openapi.utils import get_openapi

@app.on_event("startup")
async def export_openapi():
    if settings.ENVIRONMENT == "development":
        spec = get_openapi(title=app.title, version=app.version, routes=app.routes)
        with open("../docs/api-contract.json", "w") as f:
            json.dump(spec, f, indent=2)
```

**Task 2.7 — Deploy to Render**

1. Go to render.com → New → Web Service
2. Connect GitHub repo, root directory: `nivesh-server`
3. Build command: `pip install -e ../nivesh-shared -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from Task 2.1 — set `DATABASE_URL` to the Supavisor pooler URL
6. Deploy → test `https://nivesh-server.onrender.com/health`

**Task 2.8 — Smoke test all endpoints**

```bash
# Login
curl -X POST https://nivesh-server.onrender.com/api/v1/auth/login \
  -d '{"username":"admin","password":"xxx"}' | jq .

# Funds list
TOKEN="<access_token_from_above>"
curl -H "Authorization: Bearer $TOKEN" \
  https://nivesh-server.onrender.com/api/v1/funds | jq .meta

# Delta sync test
curl -H "Authorization: Bearer $TOKEN" \
  "https://nivesh-server.onrender.com/api/v1/funds/119598/nav?from_date=2026-01-01" | jq .
```

### Deliverable

- Server live on Render with HTTPS
- All endpoints from the API contract implemented and tested
- `docs/api-contract.json` committed to repo
- Smoke tests passing

---

## Phase 3 — Server: Ingestion Pipeline

**Duration:** 5–7 days | **Risk:** High | **Depends on:** Phase 1

> This is the highest-risk phase. It involves external data sources (NSE bhavcopy, AMFI, Yahoo Finance) that can change format, go down, or rate-limit you. Build defensively.

### Goal

Promote existing ETL scripts to a production APScheduler pipeline. Add new ingestion jobs for stocks, technical indicators, and market daily data.

### Step-by-Step Tasks

**Task 3.1 — Create ingestion package structure**

```
nivesh-server/app/ingestion/
├── __init__.py
├── scheduler.py          ← APScheduler setup + all job registrations
├── amfi_nav.py           ← Existing sync.py logic, promoted
├── nse_bhavcopy.py       ← New: daily EOD stock OHLCV
├── technical.py          ← New: pandas-ta indicators post-bhavcopy
├── fundamentals.py       ← New: quarterly fundamental data
├── fii_dii.py            ← New: FII/DII daily flows
└── market_snapshot.py    ← New: EOD market aggregation
```

**Task 3.2 — Implement scheduler**

`ingestion/scheduler.py`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

IST = pytz.timezone("Asia/Kolkata")

scheduler = AsyncIOScheduler(timezone=IST)

def register_jobs():
    # MF NAV — daily at 22:00 IST (AMFI publishes by 21:00)
    scheduler.add_job(run_amfi_nav, CronTrigger(hour=22, minute=0, timezone=IST),
                      id="amfi_nav", replace_existing=True)

    # NSE bhavcopy — Monday–Friday at 19:00 IST
    scheduler.add_job(run_nse_bhavcopy, CronTrigger(day_of_week="mon-fri",
                      hour=19, minute=0, timezone=IST),
                      id="nse_bhavcopy", replace_existing=True)

    # Technical indicators — after bhavcopy, 20:00 IST
    scheduler.add_job(run_technical_indicators, CronTrigger(day_of_week="mon-fri",
                      hour=20, minute=0, timezone=IST),
                      id="technical_indicators", replace_existing=True)

    # Market snapshot (indices, movers, FII/DII) — 20:30 IST
    scheduler.add_job(run_market_snapshot, CronTrigger(day_of_week="mon-fri",
                      hour=20, minute=30, timezone=IST),
                      id="market_snapshot", replace_existing=True)

    # Fund metrics recompute — daily at 23:00 IST (after NAV sync)
    scheduler.add_job(run_fund_metrics, CronTrigger(hour=23, minute=0, timezone=IST),
                      id="fund_metrics", replace_existing=True)

    # Fundamentals — quarterly, first Sunday of each quarter month at 10:00
    scheduler.add_job(run_fundamentals, CronTrigger(month="1,4,7,10",
                      day="1-7", day_of_week="sun", hour=10, timezone=IST),
                      id="fundamentals", replace_existing=True)
```

**Task 3.3 — Implement NSE bhavcopy ingestion**

`ingestion/nse_bhavcopy.py`:

```python
import httpx
import pandas as pd
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.stocks import StockOHLCVDaily
from app.ingestion.utils import log_sync_job

NSE_BHAVCOPY_URL = (
    "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date}_F_0000.csv.zip"
)

async def run_nse_bhavcopy(db: AsyncSession):
    today = date.today()
    url = NSE_BHAVCOPY_URL.format(date=today.strftime("%d%m%Y"))
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        # Parse CSV, upsert to stock_ohlcv_daily
        df = pd.read_csv(...)
        # Bulk upsert using PostgreSQL ON CONFLICT DO UPDATE
        await bulk_upsert_ohlcv(db, df)
        await log_sync_job(db, "nse_bhavcopy", "COMPLETED", records=len(df))
    except Exception as e:
        await log_sync_job(db, "nse_bhavcopy", "FAILED", error=str(e))
        raise
```

**Task 3.4 — Implement technical indicators post-processing**

`ingestion/technical.py`:

```python
import pandas_ta as ta
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

async def run_technical_indicators(db: AsyncSession):
    """
    Runs after nse_bhavcopy completes.
    For each active symbol, fetch last 250 days OHLCV, compute indicators,
    upsert today's row into stock_technical_indicators.
    """
    symbols = await get_active_symbols(db)
    for symbol in symbols:
        ohlcv = await get_ohlcv_for_ta(db, symbol, lookback_days=250)
        df = pd.DataFrame(ohlcv)

        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        df.ta.bbands(append=True)
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.atr(length=14, append=True)

        today_row = df.iloc[-1]
        await upsert_technicals(db, symbol, today_row)
```

**Task 3.5 — Implement sync_jobs logging utility**

`ingestion/utils.py`:

```python
from datetime import datetime, timezone

async def log_sync_job(db, job_name: str, status: str,
                       records: int = 0, error: str = None):
    from app.models.system import SyncJob
    job = SyncJob(
        job_name=job_name,
        status=status,
        records_processed=records,
        error_message=error,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
```

**Task 3.6 — Register scheduler in FastAPI lifespan**

```python
# main.py
from contextlib import asynccontextmanager
from app.ingestion.scheduler import scheduler, register_jobs

@asynccontextmanager
async def lifespan(app: FastAPI):
    register_jobs()
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

**Task 3.7 — Test ingestion pipeline end-to-end**

```bash
# Test manual trigger (don't wait for cron)
python -c "
import asyncio
from app.database import AsyncSessionLocal
from app.ingestion.nse_bhavcopy import run_nse_bhavcopy
async def main():
    async with AsyncSessionLocal() as db:
        await run_nse_bhavcopy(db)
asyncio.run(main())
"
# Check sync_jobs table in Supabase dashboard
```

**Task 3.8 — Keep-alive ping (prevent Render spin-down during jobs)**

On Render free tier, deploy a second job — a simple ping script via GitHub Actions cron, or use UptimeRobot (free) to ping `GET /health` every 10 minutes. This keeps the Render instance warm so scheduled jobs fire on time.

> **Upgrade note:** Once ingestion is critical, upgrade Render to Starter ($7/month) — always-on instances, no spin-down.

### Deliverable

- All ingestion jobs implemented and tested manually
- Scheduler registers all jobs on server startup
- `sync_jobs` table populated with real run history
- MF data flowing nightly; NSE bhavcopy flowing on weekdays

---

## Phase 4 — Client: SQLite + Local API

**Duration:** 3–4 days | **Risk:** Low | **Depends on:** Phase 0

### Goal

Build the client's local FastAPI application with SQLite storage for all user-private data, cache tables, and auth tokens. This phase runs independently of the server phases.

### Step-by-Step Tasks

**Task 4.1 — Set up client app skeleton**

```
nivesh-client/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py           ← SQLAlchemy → SQLite
│   ├── models/
│   │   ├── user_data.py
│   │   ├── cache.py
│   │   ├── agent.py
│   │   └── auth.py
│   └── routers/
│       └── portfolio.py
├── alembic/
├── alembic.ini
├── .env.example
└── requirements.txt
```

**Task 4.2 — Configure SQLite database**

`nivesh-client/app/database.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from app.config import settings
import os

DB_PATH = os.path.expanduser("~/.nivesh/nivesh_client.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

# Enable WAL mode for concurrent reads
@event.listens_for(engine.sync_engine, "connect")
def set_wal_mode(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

**Task 4.3 — Define all client SQLite models**

`models/user_data.py`:
```python
class Watchlist(Base):
    __tablename__ = "watchlist"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    symbol          = Column(String, nullable=False)
    asset_type      = Column(String)       # STOCK / FUND
    notes           = Column(String)
    target_price    = Column(Float)
    alert_threshold = Column(Float)
    added_at        = Column(TIMESTAMP, default=datetime.utcnow)

class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    symbol          = Column(String)
    asset_type      = Column(String)
    quantity        = Column(Float)
    avg_cost        = Column(Float)
    buy_date        = Column(Date)
    folio_number    = Column(String)       # for MF

class Transaction(Base):
    __tablename__ = "transactions"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    symbol          = Column(String)
    asset_type      = Column(String)
    txn_type        = Column(String)       # BUY / SELL / DIVIDEND
    quantity        = Column(Float)
    price           = Column(Float)
    txn_date        = Column(Date)
    notes           = Column(String)
```

`models/cache.py`:
```python
class CacheStockSummary(Base):
    __tablename__ = "cache_stock_summary"
    symbol          = Column(String, primary_key=True)
    data            = Column(JSON)
    fetched_at      = Column(TIMESTAMP)
    ttl_seconds     = Column(Integer, default=3600)   # 1 hour

class CacheFundMetrics(Base):
    __tablename__ = "cache_fund_metrics"
    scheme_code     = Column(String, primary_key=True)
    data            = Column(JSON)
    fetched_at      = Column(TIMESTAMP)
    ttl_seconds     = Column(Integer, default=86400)  # 24 hours

class SyncState(Base):
    __tablename__ = "sync_state"
    resource_key    = Column(String, primary_key=True)  # e.g. "ohlcv:RELIANCE"
    last_synced_at  = Column(TIMESTAMP)
    last_generated_at = Column(TIMESTAMP)               # from server's meta.generated_at
```

`models/auth.py`:
```python
class AuthToken(Base):
    __tablename__ = "auth_tokens"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    access_token    = Column(String)
    refresh_token   = Column(String)
    expires_at      = Column(TIMESTAMP)
    created_at      = Column(TIMESTAMP, default=datetime.utcnow)

class ServerConfig(Base):
    __tablename__ = "server_config"
    key             = Column(String, primary_key=True)
    value           = Column(String)
    # Keys: NIVESH_SERVER_URL, last_connected_at, server_version
```

**Task 4.4 — Configure Alembic for SQLite**

```bash
cd nivesh-client
alembic init alembic
```

`alembic/env.py` — same pattern as server but pointing to SQLite URL.

```bash
alembic revision --autogenerate -m "initial_client_schema"
alembic upgrade head
```

**Task 4.5 — Auto-migrate on startup**

```python
# main.py — client
from alembic.config import Config
from alembic import command

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run migrations automatically on every startup
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    yield

app = FastAPI(lifespan=lifespan, title="Nivesh Client", version="0.1.0")
```

**Task 4.6 — Implement portfolio/watchlist CRUD routers**

`routers/portfolio.py`:
```python
router = APIRouter(prefix="/local/portfolio", tags=["portfolio"])

@router.get("/holdings")
async def get_holdings(db: AsyncSession = Depends(get_db)):
    ...

@router.post("/holdings")
async def add_holding(holding: HoldingCreate, db: AsyncSession = Depends(get_db)):
    ...

@router.get("/watchlist")
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    ...
```

**Task 4.7 — Create `.env.example`**

```bash
# .env.example — copy to .env and fill in
NIVESH_SERVER_URL=https://nivesh-server.onrender.com
CLIENT_PORT=8001
SQLITE_DB_PATH=~/.nivesh/nivesh_client.db
```

**Task 4.8 — Test client in isolation (no server needed)**

```bash
cd nivesh-client
pip install -r requirements.txt
uvicorn app.main:app --port 8001
# Test portfolio CRUD via http://localhost:8001/docs
```

### Deliverable

- Client runs independently at port 8001
- SQLite DB auto-created at `~/.nivesh/nivesh_client.db`
- Alembic migrations run on startup
- Portfolio/watchlist CRUD endpoints tested

---

## Phase 5 — Client: JWT Auth + Sync Engine

**Duration:** 4–5 days | **Risk:** High | **Depends on:** Phase 2 (server must be deployed), Phase 4

### Goal

Implement the JWT authentication flow and the sync engine that fetches data from the server, caches it locally, and handles offline mode.

### Step-by-Step Tasks

**Task 5.1 — Implement auth router on client**

`routers/auth.py` on client side:

```python
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
async def login(form: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Client receives username+password from UI,
    forwards to server, stores tokens in SQLite.
    """
    async with get_server_client() as client:
        resp = await client.post("/api/v1/auth/login",
                                 json={"username": form.username, "password": form.password})
        resp.raise_for_status()
        tokens = resp.json()

    # Store tokens in local SQLite
    await store_tokens(db, tokens["access_token"], tokens["refresh_token"],
                       expires_in=tokens["expires_in"])
    return {"message": "Logged in", "expires_in": tokens["expires_in"]}

@router.post("/logout")
async def logout(db: AsyncSession = Depends(get_db)):
    token = await get_current_token(db)
    # Notify server to invalidate refresh token
    async with get_server_client(token) as client:
        await client.post("/api/v1/auth/logout",
                          json={"refresh_token": token.refresh_token})
    await clear_tokens(db)
    return {"message": "Logged out"}
```

**Task 5.2 — Implement httpx server client with JWT injection**

`sync/http_client.py`:

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings

class NiveshServerClient:
    """
    Async httpx client that:
    1. Injects JWT access_token on every request
    2. Auto-refreshes on 401
    3. Retries on 5xx with exponential backoff
    4. Raises OfflineError when server unreachable
    """
    def __init__(self, db):
        self.db = db
        self.base_url = settings.NIVESH_SERVER_URL

    async def __aenter__(self):
        token = await get_current_token(self.db)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token.access_token}"},
            timeout=30,
        )
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get(self, path: str, **kwargs):
        try:
            resp = await self._client.get(path, **kwargs)
            if resp.status_code == 401:
                await self._refresh_token()
                resp = await self._client.get(path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise OfflineError(f"Cannot reach server: {self.base_url}")

    async def _refresh_token(self):
        token = await get_current_token(self.db)
        async with httpx.AsyncClient(base_url=self.base_url) as c:
            resp = await c.post("/api/v1/auth/refresh",
                                json={"refresh_token": token.refresh_token})
            if resp.status_code == 401:
                raise SessionExpiredError("Session expired — please log in again")
            new_token = resp.json()
        await update_access_token(self.db, new_token["access_token"],
                                   expires_in=new_token["expires_in"])
        self._client.headers["Authorization"] = f"Bearer {new_token['access_token']}"
```

**Task 5.3 — Implement delta sync engine**

`sync/delta.py`:

```python
from datetime import datetime, timezone

async def get_from_date(db, resource_key: str) -> Optional[str]:
    """
    Returns the from_date to use for delta fetch.
    Based on last_synced_at in sync_state table.
    """
    state = await db.get(SyncState, resource_key)
    if not state:
        return None  # No prior sync — full fetch
    return state.last_synced_at.date().isoformat()

async def is_stale(db, resource_key: str, ttl_seconds: int) -> bool:
    state = await db.get(SyncState, resource_key)
    if not state:
        return True
    age = (datetime.now(timezone.utc) - state.last_synced_at).total_seconds()
    return age > ttl_seconds

async def mark_synced(db, resource_key: str, generated_at: str):
    state = await db.get(SyncState, resource_key) or SyncState(resource_key=resource_key)
    state.last_synced_at = datetime.now(timezone.utc)
    state.last_generated_at = datetime.fromisoformat(generated_at)
    db.add(state)
    await db.commit()
```

**Task 5.4 — Implement sync engine orchestrator**

`sync/engine.py`:

```python
from app.sync.delta import is_stale, get_from_date, mark_synced
from app.sync.http_client import NiveshServerClient

async def sync_fund_metrics(db):
    """Called on demand or by scheduler. Fetches fresh metrics if stale."""
    if not await is_stale(db, "fund_metrics_all", ttl_seconds=86400):
        return  # Cache is fresh — skip

    try:
        async with NiveshServerClient(db) as client:
            resp = await client.get("/api/v1/funds", params={"page_size": 500})
        # Upsert into cache_fund_metrics
        for fund in resp["data"]:
            await upsert_cache(db, "cache_fund_metrics", fund["scheme_code"], fund)
        await mark_synced(db, "fund_metrics_all", resp["meta"]["generated_at"])
    except OfflineError:
        # Serve stale cache — log the offline event, don't raise
        await log_offline_event(db, "fund_metrics_all")

async def sync_stock_ohlcv(db, symbol: str):
    """Delta fetch — only gets rows since last sync."""
    resource_key = f"ohlcv:{symbol}"
    from_date = await get_from_date(db, resource_key)

    try:
        async with NiveshServerClient(db) as client:
            resp = await client.get(f"/api/v1/stocks/{symbol}/ohlcv",
                                    params={"from_date": from_date} if from_date else {})
        await upsert_ohlcv_cache(db, symbol, resp["data"])
        await mark_synced(db, resource_key, resp["meta"]["generated_at"])
    except OfflineError:
        await log_offline_event(db, resource_key)
```

**Task 5.5 — Implement background scheduler (client-side)**

`sync/scheduler.py`:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

client_scheduler = AsyncIOScheduler()

def register_client_jobs(db_factory):
    # Market snapshot — every 30 minutes during market hours
    client_scheduler.add_job(
        lambda: sync_market_snapshot(db_factory()),
        CronTrigger(day_of_week="mon-fri", hour="9-16", minute="*/30"),
        id="sync_market_snapshot",
    )
    # Fund metrics — once daily at startup + 09:00
    client_scheduler.add_job(
        lambda: sync_fund_metrics(db_factory()),
        CronTrigger(hour=9, minute=0),
        id="sync_fund_metrics",
    )
    # Server health ping — every 60 seconds
    client_scheduler.add_job(
        lambda: ping_server_health(db_factory()),
        "interval", seconds=60,
        id="health_ping",
    )
```

**Task 5.6 — Implement proxy router**

`routers/proxy.py` — routes client UI calls through to server, injecting JWT:

```python
router = APIRouter(prefix="/proxy", tags=["proxy"])

@router.get("/funds")
async def proxy_funds(request: Request, db: AsyncSession = Depends(get_db)):
    """
    UI calls /proxy/funds → client FastAPI → server /api/v1/funds.
    Client injects JWT. UI never sees the token.
    """
    # Check local cache first
    cached = await get_cached_fund_list(db)
    if cached and not await is_stale(db, "fund_list", 3600):
        return cached

    # Cache miss — fetch from server
    try:
        async with NiveshServerClient(db) as client:
            data = await client.get("/api/v1/funds",
                                    params=dict(request.query_params))
        await cache_fund_list(db, data)
        return data
    except OfflineError:
        if cached:
            return {**cached, "meta": {**cached["meta"], "offline": True}}
        raise HTTPException(503, "Server unreachable and no cache available")
```

### Deliverable

- Client can log in, store JWT, and auto-refresh tokens
- Sync engine fetches from server with delta logic and caches locally
- Offline mode returns stale cache with `offline: true` flag
- Background scheduler runs market snapshot and health ping

---

## Phase 6 — Client: Agentic Layer

**Duration:** 3–5 days | **Risk:** Medium | **Depends on:** Phase 5

### Goal

Implement a local LLM-powered agent that can analyse stocks, compare funds, and answer portfolio questions. All agent state stored in client SQLite.

### Step-by-Step Tasks

**Task 6.1 — Define agent tools**

`agent/tools.py`:

```python
AGENT_TOOLS = [
    {
        "name": "fetch_stock",
        "description": "Get current price, technicals, and fundamentals for a stock symbol",
        "parameters": {"symbol": "string (NSE symbol, e.g. RELIANCE)"},
    },
    {
        "name": "fetch_fund",
        "description": "Get NAV, metrics (Sharpe/Sortino/Alpha), and rolling returns for a mutual fund",
        "parameters": {"scheme_code": "string (AMFI scheme code)"},
    },
    {
        "name": "compare_funds",
        "description": "Side-by-side comparison of up to 5 mutual funds on key metrics",
        "parameters": {"codes": "list of scheme codes (max 5)"},
    },
    {
        "name": "get_portfolio_summary",
        "description": "Summarise user's holdings with current prices and P&L",
        "parameters": {},
    },
    {
        "name": "get_market_context",
        "description": "Today's index levels, top movers, sector performance, FII/DII flows",
        "parameters": {},
    },
    {
        "name": "screen_stocks",
        "description": "Find stocks matching filter criteria (e.g. PE < 20, RSI < 40, sector = IT)",
        "parameters": {
            "filters": "dict of criteria: {pe_lt, pb_lt, rsi_lt, rsi_gt, sector, market_cap}"
        },
    },
]
```

**Task 6.2 — Implement tool executor**

`agent/tools.py` — executor that dispatches tool calls to the sync engine:

```python
async def execute_tool(tool_name: str, params: dict, db: AsyncSession) -> str:
    if tool_name == "fetch_stock":
        data = await sync_stock_summary(db, params["symbol"])
        return json.dumps(data)
    elif tool_name == "fetch_fund":
        data = await get_cached_fund_metrics(db, params["scheme_code"])
        return json.dumps(data)
    elif tool_name == "get_portfolio_summary":
        holdings = await get_all_holdings(db)
        # Enrich with cached prices
        return json.dumps(await enrich_holdings_with_prices(db, holdings))
    # ... etc
```

**Task 6.3 — Implement agent runner**

`agent/runner.py`:

```python
async def run_agent_turn(session_id: str, user_message: str, db: AsyncSession) -> str:
    """
    Single turn of the agent loop.
    Stores all messages and tool calls in SQLite.
    """
    # Load conversation history
    history = await get_session_messages(db, session_id)

    # Call LLM (using Anthropic API or local model)
    response = await call_llm(
        messages=history + [{"role": "user", "content": user_message}],
        tools=AGENT_TOOLS,
    )

    # Save user message
    await save_message(db, session_id, "user", user_message)

    # Handle tool calls
    if response.tool_calls:
        for tool_call in response.tool_calls:
            # Log the tool call
            await save_tool_call(db, session_id, tool_call.name, tool_call.params)
            # Execute
            result = await execute_tool(tool_call.name, tool_call.params, db)
            # Feed result back into LLM context (handled by next turn)

    # Save assistant response
    await save_message(db, session_id, "assistant", response.content)

    return response.content
```

**Task 6.4 — Implement agent memory**

`agent/memory.py`:

```python
async def update_memory(db, key: str, value: str):
    """Stores persistent facts the agent learns about the user."""
    mem = await db.get(AgentMemory, key) or AgentMemory(key=key)
    mem.value = value
    mem.updated_at = datetime.utcnow()
    db.add(mem)
    await db.commit()

async def get_memory_context(db) -> str:
    """Returns all agent memories as a formatted string for LLM context."""
    memories = await db.execute(select(AgentMemory))
    return "\n".join(f"{m.key}: {m.value}" for m in memories.scalars())
```

**Task 6.5 — Agent API router**

`routers/agent.py`:

```python
router = APIRouter(prefix="/agent", tags=["agent"])

@router.post("/sessions")
async def create_session(context: AgentContextCreate, db: AsyncSession = Depends(get_db)):
    session = AgentSession(context_type=context.type)
    db.add(session)
    await db.commit()
    return {"session_id": session.id}

@router.post("/sessions/{session_id}/chat")
async def chat(session_id: str, msg: ChatMessage, db: AsyncSession = Depends(get_db)):
    reply = await run_agent_turn(session_id, msg.content, db)
    return {"reply": reply, "session_id": session_id}

@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str, db: AsyncSession = Depends(get_db)):
    return await get_session_messages(db, session_id)
```

### Deliverable

- Agent can handle stock, fund, portfolio, and market queries
- All agent state persisted in SQLite
- Tool calls logged with params and response summary
- Agent memory persists across sessions

---

## Phase 7 — Client: UI Adaptation

**Duration:** 2–3 days | **Risk:** Low | **Depends on:** Phase 4, Phase 5

### Goal

Update the existing React frontend to talk exclusively to the client's local FastAPI (port 8001) instead of the server directly. Add sync status and offline indicators.

### Step-by-Step Tasks

**Task 7.1 — Update API base URL**

In React (Vite), update `src/config.ts`:

```typescript
// Before — pointed directly at server or backend
export const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// After — always points to local client FastAPI
export const API_BASE = "http://localhost:8001";
```

All existing API calls continue to work — the client proxy router handles forwarding.

**Task 7.2 — Add login screen**

New component `src/pages/Login.tsx`:

```typescript
const handleLogin = async (username: string, password: string) => {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (resp.ok) navigate("/dashboard");
};
```

Note: React never handles JWT tokens directly — it just calls the client API which manages tokens.

**Task 7.3 — Add sync status bar**

New component `src/components/SyncStatus.tsx`:

```typescript
// Polls GET /local/sync-status every 60 seconds
// Shows: "Last synced: 2 hours ago" or "Offline — showing cached data"
const { data } = useSWR("/local/sync-status", fetcher, { refreshInterval: 60000 });

return (
  <div className={`sync-bar ${data?.offline ? "offline" : "online"}`}>
    {data?.offline
      ? `⚠ Offline — cached data from ${data.last_synced}`
      : `✓ Synced ${data?.last_synced_relative}`}
  </div>
);
```

**Task 7.4 — Add portfolio views**

New pages that read from local API (not server proxy):
- `src/pages/Portfolio.tsx` → `GET /local/portfolio/holdings`
- `src/pages/Watchlist.tsx` → `GET /local/portfolio/watchlist`
- `src/pages/Transactions.tsx` → `GET /local/portfolio/transactions`

**Task 7.5 — Add agent chat UI**

New page `src/pages/AgentChat.tsx`:

```typescript
const sendMessage = async (text: string) => {
  const resp = await fetch(`${API_BASE}/agent/sessions/${sessionId}/chat`, {
    method: "POST",
    body: JSON.stringify({ content: text }),
  });
  const { reply } = await resp.json();
  setMessages(prev => [...prev, { role: "assistant", content: reply }]);
};
```

**Task 7.6 — Rebuild and verify**

```bash
cd nivesh-client/frontend
npm install && npm run build
# Test full flow: login → dashboard → portfolio → agent chat
```

### Deliverable

- React UI points to `localhost:8001` only
- Login screen working — JWT handled invisibly by client backend
- Sync status bar visible on all pages
- Portfolio and agent chat pages functional

---

## Phase 8 — CI/CD + Production Hardening

**Duration:** 2–3 days | **Risk:** Low | **Depends on:** All prior phases

### Goal

Set up GitHub Actions for automated deployment to Render, implement backups for Supabase, and write the client install script.

### Step-by-Step Tasks

**Task 8.1 — GitHub Actions: Server deploy to Render**

`.github/workflows/deploy-server.yml`:

```yaml
name: Deploy Server to Render

on:
  push:
    branches: [main]
    paths:
      - "nivesh-server/**"
      - "nivesh-shared/**"

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run server tests
        run: |
          pip install -e ./nivesh-shared -r ./nivesh-server/requirements.txt
          cd nivesh-server && pytest tests/ -v

      - name: Trigger Render deploy
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
            "https://api.render.com/v1/services/${{ secrets.RENDER_SERVICE_ID }}/deploys" \
            -d '{}'
```

**Task 8.2 — GitHub Actions: Supabase weekly backup**

`.github/workflows/backup-supabase.yml`:

```yaml
name: Weekly Supabase Backup

on:
  schedule:
    - cron: "0 2 * * 0"    # Every Sunday at 02:00 UTC

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - name: pg_dump to artifact
        run: |
          pg_dump ${{ secrets.ALEMBIC_URL }} \
            --no-password --format=custom \
            -f nivesh_backup_$(date +%Y%m%d).dump

      - name: Upload to GitHub artifacts
        uses: actions/upload-artifact@v4
        with:
          name: supabase-backup-${{ github.run_number }}
          path: "*.dump"
          retention-days: 30
```

**Task 8.3 — UptimeRobot keep-alive**

1. Create free account at uptimerobot.com
2. Add HTTP monitor: `https://nivesh-server.onrender.com/health`
3. Check interval: 5 minutes
4. This prevents Render free tier spin-down during business hours

**Task 8.4 — Client install script**

Extend existing `setup/setup.bat` (Windows) and create `setup/setup.sh` (Linux/Mac):

`setup/setup.sh`:

```bash
#!/bin/bash
set -e
echo "Installing Nivesh Client..."

# Check Python 3.11+
python3 --version || { echo "Python 3.11+ required"; exit 1; }

# Install shared package
pip install -e ./nivesh-shared

# Install client
pip install -e ./nivesh-client

# Create config directory
mkdir -p ~/.nivesh

# Copy .env if not exists
if [ ! -f ~/.nivesh/.env ]; then
    cp ./nivesh-client/.env.example ~/.nivesh/.env
    echo "⚠ Edit ~/.nivesh/.env and set NIVESH_SERVER_URL"
fi

echo "✓ Nivesh Client installed."
echo "Run: uvicorn nivesh_client.app.main:app --port 8001"
```

**Task 8.5 — Final `requirements.txt` audit**

Ensure both packages have pinned versions:

`nivesh-server/requirements.txt`:
```text
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0              # PostgreSQL async driver
alembic==1.13.1
httpx==0.27.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
apscheduler==3.10.4
pandas==2.2.2
pandas-ta==0.3.14b
scipy==1.13.0
python-multipart==0.0.9
tenacity==8.3.0
pytz==2024.1
nivesh-shared @ ../nivesh-shared  # local editable
```

`nivesh-client/requirements.txt`:
```text
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.30
aiosqlite==0.20.0            # SQLite async driver
alembic==1.13.1
httpx==0.27.0
python-jose[cryptography]==3.3.0
apscheduler==3.10.4
tenacity==8.3.0
pytz==2024.1
anthropic==0.28.0            # for agent LLM calls
nivesh-shared @ ../nivesh-shared
```

**Task 8.6 — Update `docs/BACKEND.md`**

Rewrite to reflect new split architecture, Render deployment steps, Supabase connection config, and client install instructions.

### Deliverable

- Auto-deploy on push to `main` for server changes
- Weekly Supabase backup running
- Client install script tested on Windows and Linux
- All requirements pinned

---

## 13. Environment Variables Reference

### Server (`nivesh-server/.env` / Render Dashboard)

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres.[ref]:[pwd]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres` | Supavisor pooler — use this for FastAPI |
| `ALEMBIC_URL` | `postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres` | Direct connection — Alembic migrations only |
| `SECRET_KEY` | Random 256-bit string | Render generates via `generateValue: true` |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Short-lived access tokens |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Longer-lived refresh tokens |
| `ENVIRONMENT` | `production` | Controls OpenAPI export, debug mode |
| `APP_VERSION` | `0.1.0` | Returned in `/health` response |

### Client (`~/.nivesh/.env`)

| Variable | Value | Notes |
|---|---|---|
| `NIVESH_SERVER_URL` | `https://nivesh-server.onrender.com` | The deployed server URL |
| `CLIENT_PORT` | `8001` | Local FastAPI port |
| `SQLITE_DB_PATH` | `~/.nivesh/nivesh_client.db` | Expands to user home directory |

---

## 14. Dependency Reference

| Library | Used in | Purpose | Already in project? |
|---|---|---|---|
| `fastapi` | Both | API framework | ✅ Yes |
| `uvicorn` | Both | ASGI server | ✅ Yes |
| `sqlalchemy[asyncio]` | Both | ORM (PostgreSQL + SQLite) | ✅ Yes |
| `asyncpg` | Server | Async PostgreSQL driver | ✅ Yes |
| `aiosqlite` | Client | Async SQLite driver | ❌ New |
| `alembic` | Both | DB migrations | ✅ Yes |
| `httpx` | Client | Async HTTP client for server calls | ✅ Yes |
| `python-jose` | Both | JWT encode/decode | ✅ Yes |
| `passlib[bcrypt]` | Server | Password hashing | ✅ Yes |
| `apscheduler` | Both | Job scheduling | ✅ Yes |
| `pandas` | Server | Data processing | ✅ Yes |
| `pandas-ta` | Server | Technical indicators | ✅ Yes |
| `scipy` | Server | Pattern detection | ✅ Yes |
| `tenacity` | Client | Retry with backoff | ❌ New |
| `anthropic` | Client | LLM calls for agent | ❌ New |
| `pytz` | Both | IST timezone for scheduler | ✅ Yes |

**New dependencies needed:** `aiosqlite`, `tenacity`, `anthropic` — everything else is already in the project.

---

## 15. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | NSE bhavcopy URL changes format | High | High | Wrap in try/except; log to sync_jobs; alert via email on 3 consecutive failures |
| R2 | Supabase free tier storage fills up (500MB) | Medium | High | Monitor via Supabase dashboard; implement data retention (delete OHLCV older than 5Y for small-cap stocks) |
| R3 | Render free tier spins down during market hours | High | Medium | UptimeRobot keep-alive ping every 5 min; upgrade to Starter ($7/mo) when ingestion is live |
| R4 | Supabase free tier paused after inactivity | Medium | High | Same UptimeRobot ping hits `/health` which queries DB, keeping project active |
| R5 | Client sync gets stuck in inconsistent state | Medium | Medium | `sync_state` table is the source of truth; add a "Force full re-sync" button in UI that clears sync_state |
| R6 | JWT refresh token expires while client is offline | Low | Medium | On SessionExpiredError, redirect to login; re-login restores all functionality immediately |
| R7 | pandas-ta compute spikes Render's 512MB RAM | Medium | Medium | Run TA computation in batches of 50 symbols; schedule during off-peak hours (20:00–21:00 IST) |
| R8 | Supabase connection pooler limits hit | Low | High | `pool_size=5` in SQLAlchemy keeps well under the 20 backend connection limit; upgrade compute add-on if needed |

---

*Document version: 1.0 · Generated: May 2026*
*Previous document: `NIVESH_ARCHITECTURE.md`*
*Next: Low-Level Design — Sync Engine & Delta Fetch Protocol*
