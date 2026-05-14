# Nivesh Platform — Phase 2: Server Core API on Render
## Detailed Implementation Plan · Based on dev branch code
### Version 1.0 · May 2026

---

## Table of Contents

1. [Phase 2 Goal & Scope](#1-phase-2-goal--scope)
2. [What Already Exists vs What Gets Built](#2-what-already-exists-vs-what-gets-built)
3. [File-by-File Change Map](#3-file-by-file-change-map)
4. [Task 2.1 — Wire Supabase Connection](#task-21--wire-supabase-connection)
5. [Task 2.2 — Update models.py for Supabase](#task-22--update-modelspy-for-supabase)
6. [Task 2.3 — Add admin_users & etl_runs to models.py](#task-23--add-admin_users--etl_runs-to-modelspy)
7. [Task 2.4 — JWT Auth Layer](#task-24--jwt-auth-layer)
8. [Task 2.5 — Update crud.py — Sync Job → etl_runs](#task-25--update-crudpy--sync-job--etl_runs)
9. [Task 2.6 — Update schemas.py — Auth Schemas](#task-26--update-schemaspy--auth-schemas)
10. [Task 2.7 — Auth Router](#task-27--auth-router)
11. [Task 2.8 — Protect Existing Routes with JWT](#task-28--protect-existing-routes-with-jwt)
12. [Task 2.9 — Health Endpoint](#task-29--health-endpoint)
13. [Task 2.10 — Render Deployment](#task-210--render-deployment)
14. [Task 2.11 — Smoke Tests](#task-211--smoke-tests)
15. [Dependency Changes](#15-dependency-changes)
16. [Environment Variables](#16-environment-variables)
17. [File Tree After Phase 2](#17-file-tree-after-phase-2)
18. [Definition of Done](#18-definition-of-done)

---

## 1. Phase 2 Goal & Scope

**Goal:** Take the existing working FastAPI app from the `dev` branch, point it at Supabase, add JWT authentication, add the two new tables (`admin_users`, `etl_runs`), and deploy to Render — **without breaking any existing functionality**.

**In scope:**
- Supabase connection (swap local Postgres for Supabase pooler URL)
- `TIMESTAMP` → `TIMESTAMPTZ` fix across all models
- Add `admin_users` and `etl_runs` to `models.py`
- JWT auth: login, token refresh, logout, protected route dependency
- Replace `SyncJob`/`PipelineAudit` references with `EtlRun` in `crud.py`
- Auth router + protect all existing routes
- `GET /health` endpoint
- Deploy to Render with env vars

**Out of scope for Phase 2:**
- Client application (Phase 4–7)
- New ingestion pipelines (Phase 3)
- Stock/fund data changes — existing routes stay exactly as they are
- Schema changes to existing tables beyond `TIMESTAMP → TIMESTAMPTZ`

---

## 2. What Already Exists vs What Gets Built

### Already working in dev branch — keep as-is

| What | File | Status |
|---|---|---|
| Fund master CRUD | `crud.py` lines 30–308 | ✅ Keep exactly |
| Benchmark CRUD | `crud.py` lines 310–373 | ✅ Keep exactly |
| NAV bulk insert (upsert) | `crud.py` lines 379–431 | ✅ Keep exactly |
| Benchmark price window query | `crud.py` lines 443–481 | ✅ Keep exactly |
| Fund/benchmark metrics upsert | `crud.py` lines 487–514 | ✅ Keep exactly |
| All Pydantic schemas | `schemas.py` | ✅ Keep exactly |
| All SQLAlchemy models except `SyncJob` | `models.py` | ✅ Keep — only `TIMESTAMPTZ` fix |
| All existing routers (funds, benchmarks, stocks) | `routers/` | ✅ Keep — add JWT dependency only |

### Built in Phase 2

| What | Where | Notes |
|---|---|---|
| Supabase async engine config | `database.py` | Replace engine creation |
| `AdminUser` model | `models.py` | New class |
| `EtlRun` model | `models.py` | Replaces `SyncJob` + `PipelineAudit` |
| `TIMESTAMP → TIMESTAMPTZ` | `models.py` | All 15 existing models |
| JWT `security.py` | `app/security.py` | New file |
| Auth schemas | `schemas.py` | 3 new Pydantic classes appended |
| CRUD for `etl_runs` | `crud.py` | Replace sync_job functions |
| Auth router | `routers/auth.py` | New file |
| `get_current_user` dependency | `dependencies.py` | New file |
| `GET /health` | `main.py` | One new endpoint |
| JWT protection on all routes | all routers | One-line change per router |
| `render.yaml` | repo root | New file |
| `requirements.txt` update | `requirements.txt` | 3 new packages |

---

## 3. File-by-File Change Map

```
nivesh-server/
├── app/
│   ├── database.py          ← MODIFY: swap engine for Supabase pooler
│   ├── models.py            ← MODIFY: TIMESTAMPTZ fix + add AdminUser + EtlRun
│   ├── schemas.py           ← MODIFY: append 3 auth schemas
│   ├── crud.py              ← MODIFY: replace SyncJob functions with EtlRun
│   ├── main.py              ← MODIFY: add /health + lifespan startup
│   ├── config.py            ← MODIFY: add JWT + Supabase env vars
│   ├── security.py          ← CREATE: JWT encode/decode/verify
│   ├── dependencies.py      ← CREATE: get_current_user FastAPI dependency
│   └── routers/
│       ├── auth.py          ← CREATE: /auth/login, /refresh, /logout
│       ├── funds.py         ← MODIFY: add Depends(get_current_user)
│       ├── benchmarks.py    ← MODIFY: add Depends(get_current_user)
│       └── stocks.py        ← MODIFY: add Depends(get_current_user)
├── alembic/
│   └── versions/
│       ├── 001_timestamptz_fix.py        ← NEW migration
│       ├── 002_add_admin_users.py        ← NEW migration
│       ├── 003_add_etl_runs.py           ← NEW migration
│       └── 004_migrate_sync_jobs.py      ← NEW migration
├── render.yaml              ← CREATE
└── requirements.txt         ← MODIFY: add 3 packages
```

---

## Task 2.1 — Wire Supabase Connection

**File:** `app/database.py`
**Estimated time:** 1 hour

### What to change

The existing `database.py` creates a SQLAlchemy engine pointing at a local or generic Postgres URL. Replace it with an async engine configured for Supabase's Supavisor pooler.

**Existing pattern (what's there now):**
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

**New `database.py`:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import text
from .config import settings


# ── Engine ────────────────────────────────────────────────────────────────────
# Always use the Supavisor pooler URL (port 6543) for the running app.
# SQLAlchemy needs asyncpg driver: postgresql+asyncpg://
# The URL in settings already uses postgresql:// — we swap the scheme here
# so the env var itself is driver-neutral.

def _make_async_url(url: str) -> str:
    """Convert postgresql:// → postgresql+asyncpg:// for SQLAlchemy async."""
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


engine = create_async_engine(
    _make_async_url(settings.DATABASE_URL),
    # ── Pool settings tuned for Supabase free tier ──────────────────────────
    # Supabase free: 60 direct connections, 200 pooler → 20 backend connections.
    # Keep pool small so multiple Render restarts don't exhaust the limit.
    pool_size=5,
    max_overflow=3,
    pool_pre_ping=True,      # Drop stale connections before using them
    pool_recycle=300,        # Recycle connections every 5 min
    echo=settings.DEBUG,     # SQL logging only in dev
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ─────────────────────────────────────────────────────────
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### What to verify

```bash
# Quick connectivity test before running the app
python -c "
import asyncio
from app.database import engine
from sqlalchemy import text

async def test():
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT NOW()'))
        print('Supabase connected:', result.scalar())

asyncio.run(test())
"
```

---

## Task 2.2 — Update models.py for Supabase

**File:** `app/models.py`
**Estimated time:** 1 hour

### Change 1 — `TIMESTAMP` → `TIMESTAMPTZ` on all existing models

Every `TIMESTAMP` in the existing models needs `timezone=True`. This is a single find-and-replace in the file.

**Before:**
```python
created_at = Column(TIMESTAMP, server_default=func.now())
updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
```

**After:**
```python
created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
```

**Affected models** (every one of them):
- `SyncJob` — `created_at`, `updated_at`
- `FundMaster` — `created_at`, `updated_at`
- `BenchmarkMaster` — `created_at`, `updated_at`
- `FundNavHistory` — `created_at`
- `BenchmarkNavHistory` — `created_at`
- `BenchmarkMetrics` — `metrics_calculated_at`, `updated_at`
- `FundMetrics` — `metrics_calculated_at`, `updated_at`
- `Stock` — `created_at`, `updated_at`
- `PriceData` — no timestamp column (fine)
- `FinancialStatement` — `scraped_at`
- `ShareholdingPattern` — `scraped_at`
- `FinancialRatio` — `computed_at`
- `TechnicalIndicator` — no timestamp column (fine)
- `DetectedPattern` — `created_at`
- `StockRating` — no timestamp column (fine)
- `PipelineAudit` — `started_at`, `ended_at`
- `FundamentalScore` — `computed_at`

### Change 2 — Remove `SyncJob` import usage

`SyncJob` is defined in `models.py` and imported in `crud.py`. After Phase 2, `EtlRun` replaces it. Keep `SyncJob` in `models.py` temporarily until the Alembic migration copies data and drops the old table (Task 2.5 covers this).

---

## Task 2.3 — Add `admin_users` & `etl_runs` to models.py

**File:** `app/models.py`
**Estimated time:** 1 hour

Append these two classes to the bottom of `models.py`. They follow the exact same SQLAlchemy style as the existing models in the file.

```python
# ─── Auth & ETL Models ────────────────────────────────────────────────────────

import uuid as _uuid


class AdminUser(Base):
    """Platform users — admins, analysts, and service accounts for ETL."""
    __tablename__ = "admin_users"

    user_id          = Column(String(36), primary_key=True,
                              default=lambda: str(_uuid.uuid4()))
    username         = Column(String(50), nullable=False, unique=True)
    email            = Column(String(255), nullable=False, unique=True)
    hashed_password  = Column(String(255), nullable=False)
    user_role        = Column(String(20), nullable=False, default="analyst")
    # role values: 'admin' | 'analyst' | 'service'
    is_active        = Column(Boolean, nullable=False, default=True)
    last_login_at    = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at       = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at       = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                              onupdate=func.now())


class EtlRun(Base):
    """
    Unified ETL run log — replaces SyncJob (MF) and PipelineAudit (stocks).

    One row per pipeline execution. pipeline_name identifies the job type;
    entity_id is the scheme_code (MF jobs) or stock symbol (stock jobs).
    Market-wide jobs (e.g. 'fund_metrics_all') leave entity_id as NULL.
    """
    __tablename__ = "etl_runs"

    __table_args__ = (
        # Prevent two concurrent RUNNING jobs for the same pipeline + entity.
        # Mirrors the partial unique index on SyncJob.
        Index(
            "uq_etl_runs_running",
            "pipeline_name", "entity_id",
            unique=True,
            postgresql_where=text("status = 'RUNNING'"),
        ),
        Index("ix_etl_runs_pipeline_started", "pipeline_name", "started_at"),
        Index("ix_etl_runs_status", "status", "started_at"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    pipeline_name = Column(String(60), nullable=False)
    # Pipeline name values in use:
    #   'amfi_nav'               — MF NAV sync (was SyncJob)
    #   'fund_metrics'           — MF metrics recompute
    #   'nse_price'              — Stock price ingestion
    #   'technical_indicators'   — TA computation (was PipelineAudit)
    #   'financial_statements'   — Screener scrape
    #   'stock_ratings'          — Rating pipeline
    #   'fundamental_scores'     — Scoring pipeline
    entity_id     = Column(String(50), nullable=True)
    # scheme_code for MF jobs; stock symbol for stock jobs; NULL for market-wide
    status        = Column(String(10), nullable=False, default="RUNNING")
    # status values: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'PARTIAL'
    triggered_by  = Column(String(20), nullable=False, default="scheduler")
    # triggered_by values: 'scheduler' | 'manual' | 'backfill'
    started_at    = Column(TIMESTAMP(timezone=True), server_default=func.now())
    ended_at      = Column(TIMESTAMP(timezone=True), nullable=True)
    records_in    = Column(Integer, nullable=False, default=0)
    records_out   = Column(Integer, nullable=False, default=0)
    error_msg     = Column(Text, nullable=True)
    metadata_     = Column("metadata", JSONB, nullable=True)
```

> **Note on `metadata_`:** The existing `PipelineAudit` in `models.py` already uses the `Column("metadata", JSONB)` alias pattern to avoid PostgreSQL's reserved word. `EtlRun` follows the same convention — the Python attribute is `metadata_`, the DB column is `metadata`.

---

## Task 2.4 — JWT Auth Layer

**File:** `app/security.py` (new file)
**File:** `app/config.py` (modify)
**Estimated time:** 2 hours

### Update `config.py`

Add JWT and Supabase-specific settings to the existing `Settings` class. Keep all existing fields — add only what's new.

```python
# app/config.py — additions to existing Settings class
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # ── Existing fields (keep as-is) ─────────────────────────────────────────
    # DATABASE_URL, APP_NAME, DEBUG, etc. — do not change

    # ── New: Supabase ─────────────────────────────────────────────────────────
    DATABASE_URL: str          # Supavisor pooler URL (port 6543)
    ALEMBIC_URL: Optional[str] = None  # Direct URL (port 5432) — migrations only

    # ── New: JWT ──────────────────────────────────────────────────────────────
    SECRET_KEY: str            # Random 256-bit string — set in Render dashboard
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── New: App ──────────────────────────────────────────────────────────────
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "production"

    class Config:
        env_file = ".env"
        extra = "ignore"    # Ignore unknown env vars — safe for future additions
```

### Create `security.py`

```python
# app/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token creation ────────────────────────────────────────────────────────────

def _make_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(username: str) -> str:
    return _make_token(
        {"sub": username, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(username: str) -> str:
    return _make_token(
        {"sub": username, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


# ── Token verification ────────────────────────────────────────────────────────

def decode_access_token(token: str) -> Optional[str]:
    """
    Decode an access token and return the username (sub claim).
    Returns None if the token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[str]:
    """
    Decode a refresh token and return the username.
    Returns None if invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None
```

### Create `dependencies.py`

```python
# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import get_db
from .models import AdminUser
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """
    FastAPI dependency — validates the Bearer token and returns the AdminUser.
    Raise 401 if the token is missing, invalid, expired, or the user is inactive.

    Usage in any router:
        @router.get("/some-route")
        async def my_route(user: AdminUser = Depends(get_current_user)):
            ...
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    username = decode_access_token(token)
    if not username:
        raise credentials_exception

    result = await db.execute(
        select(AdminUser).where(
            AdminUser.username == username,
            AdminUser.is_active == True,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    return user
```

---

## Task 2.5 — Update crud.py — Sync Job → etl_runs

**File:** `app/crud.py`
**Estimated time:** 1.5 hours

### Change 1 — Update imports at the top of crud.py

```python
# BEFORE (line 18):
from .models import FundMaster, BenchmarkMaster, FundNavHistory, BenchmarkNavHistory, \
                    FundMetrics, BenchmarkMetrics, SyncJob

# AFTER:
from .models import FundMaster, BenchmarkMaster, FundNavHistory, BenchmarkNavHistory, \
                    FundMetrics, BenchmarkMetrics, EtlRun, AdminUser
```

### Change 2 — Replace the three SyncJob CRUD functions

The existing `create_sync_job`, `update_sync_job`, and `get_latest_sync_job` (lines 520–545) are replaced with the following. The behaviour is identical — the table and field names change.

**Remove these three functions entirely:**
```python
# DELETE: create_sync_job (line 520)
# DELETE: update_sync_job (line 532)
# DELETE: get_latest_sync_job (line 542)
```

**Add these replacements at the bottom of crud.py:**

```python
# ============================================================================
# ETL RUN CRUD  (replaces SyncJob + PipelineAudit)
# ============================================================================

async def start_etl_run(
    session: AsyncSession,
    pipeline_name: str,
    entity_id: Optional[str] = None,
    triggered_by: str = "scheduler",
) -> tuple["EtlRun", bool]:
    """
    Create a new RUNNING etl_run row.

    Mirrors the old create_sync_job behaviour:
    - Returns (run, True) if a new row was created.
    - Returns (existing_run, False) if a RUNNING row already exists
      for this pipeline_name + entity_id (partial unique index prevents duplicates).

    Args:
        pipeline_name: Job identifier, e.g. 'amfi_nav', 'technical_indicators'
        entity_id: scheme_code for MF jobs; stock symbol for stock jobs; None for market-wide
        triggered_by: 'scheduler' | 'manual' | 'backfill'
    """
    run = EtlRun(
        pipeline_name=pipeline_name,
        entity_id=entity_id,
        status="RUNNING",
        triggered_by=triggered_by,
    )
    try:
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run, True
    except IntegrityError:
        await session.rollback()
        existing = await get_latest_etl_run(session, pipeline_name, entity_id)
        return existing, False


async def finish_etl_run(
    session: AsyncSession,
    run_id: int,
    status: str,                       # 'COMPLETED' | 'FAILED' | 'PARTIAL'
    records_in: int = 0,
    records_out: int = 0,
    error_msg: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional["EtlRun"]:
    """
    Mark an etl_run as finished. Sets ended_at to NOW().

    Replaces the old update_sync_job — covers both MF and stock pipelines.
    """
    from datetime import datetime, timezone
    values: dict = {
        "status": status,
        "ended_at": datetime.now(timezone.utc),
        "records_in": records_in,
        "records_out": records_out,
    }
    if error_msg is not None:
        values["error_msg"] = error_msg
    if metadata is not None:
        values["metadata_"] = metadata

    stmt = (
        update(EtlRun)
        .where(EtlRun.id == run_id)
        .values(**values)
        .returning(EtlRun)
    )
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one_or_none()


async def get_latest_etl_run(
    session: AsyncSession,
    pipeline_name: str,
    entity_id: Optional[str] = None,
) -> Optional["EtlRun"]:
    """
    Fetch the most recent etl_run for a pipeline + entity combination.
    Mirrors the old get_latest_sync_job.
    """
    q = (
        select(EtlRun)
        .where(EtlRun.pipeline_name == pipeline_name)
        .order_by(EtlRun.started_at.desc())
        .limit(1)
    )
    if entity_id is not None:
        q = q.where(EtlRun.entity_id == entity_id)

    res = await session.execute(q)
    return res.scalar_one_or_none()


async def get_etl_run_summary(
    session: AsyncSession,
    pipeline_name: Optional[str] = None,
    limit: int = 50,
) -> List["EtlRun"]:
    """
    Return recent etl_run rows for the /sync/status endpoint.
    If pipeline_name is given, filter to that pipeline only.
    """
    q = select(EtlRun).order_by(EtlRun.started_at.desc()).limit(limit)
    if pipeline_name:
        q = q.where(EtlRun.pipeline_name == pipeline_name)
    res = await session.execute(q)
    return res.scalars().all()


# ============================================================================
# ADMIN USER CRUD
# ============================================================================

async def get_user_by_username(
    session: AsyncSession, username: str
) -> Optional["AdminUser"]:
    """Used by the auth login endpoint to look up a user."""
    result = await session.execute(
        select(AdminUser).where(
            AdminUser.username == username,
            AdminUser.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def update_last_login(session: AsyncSession, user_id: str) -> None:
    """Called after a successful login to record last_login_at."""
    from datetime import datetime, timezone
    await session.execute(
        update(AdminUser)
        .where(AdminUser.user_id == user_id)
        .values(last_login_at=datetime.now(timezone.utc))
    )
    await session.commit()
```

### Change 3 — Update callers of the old SyncJob functions

In your existing code outside `crud.py` (routers and pipeline scripts), find all calls to:
- `create_sync_job(session, scheme_code)` → `start_etl_run(session, "amfi_nav", entity_id=scheme_code)`
- `update_sync_job(session, job_id, status=..., message=...)` → `finish_etl_run(session, run_id, status=..., error_msg=...)`
- `get_latest_sync_job(session, scheme_code)` → `get_latest_etl_run(session, "amfi_nav", entity_id=scheme_code)`

Do a project-wide search for `sync_job` and `SyncJob` to find all call sites:
```bash
grep -rn "sync_job\|SyncJob" nivesh-server/app/ --include="*.py"
```

---

## Task 2.6 — Update schemas.py — Auth Schemas

**File:** `app/schemas.py`
**Estimated time:** 30 minutes

Append these three classes to the bottom of the existing `schemas.py`. Do not touch any existing schemas.

```python
# ============================================================================
# AUTH SCHEMAS  (appended — do not modify existing schemas above)
# ============================================================================

class LoginRequest(BaseModel):
    """Body for POST /auth/login."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Response for both /auth/login and /auth/refresh."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds until access_token expires


class RefreshRequest(BaseModel):
    """Body for POST /auth/refresh."""
    refresh_token: str


class EtlRunRead(BaseModel):
    """Response schema for etl_run rows — used by GET /sync/status."""
    id: int
    pipeline_name: str
    entity_id: Optional[str] = None
    status: str
    triggered_by: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    records_in: int
    records_out: int
    error_msg: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
```

---

## Task 2.7 — Auth Router

**File:** `app/routers/auth.py` (new file)
**Estimated time:** 1.5 hours

```python
# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..crud import get_user_by_username, update_last_login
from ..security import verify_password, create_access_token, create_refresh_token, decode_refresh_token
from ..schemas import LoginRequest, TokenResponse, RefreshRequest
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with username + password.

    Returns a short-lived access_token (15 min) in the response body.
    Sets a HttpOnly cookie containing the refresh_token (7 days).

    The client stores the access_token in memory (not localStorage).
    The refresh_token cookie is sent automatically by the browser / httpx.
    """
    user = await get_user_by_username(db, body.username)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token(user.username)
    refresh_token = create_refresh_token(user.username)

    # Set refresh token as HttpOnly cookie — never readable by JS
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=True,           # HTTPS only — Render provides this
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",          # Only sent to /auth/* endpoints
    )

    await update_last_login(db, user.user_id)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh_token cookie for a new access_token.

    The refresh_token is read from the HttpOnly cookie — the client
    never needs to handle it explicitly.
    """
    from fastapi import Request
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )

    username = decode_refresh_token(refresh_token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Verify user still exists and is active
    user = await get_user_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return TokenResponse(
        access_token=create_access_token(username),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """
    Clear the refresh_token cookie.
    Access tokens expire naturally (15 min) — no server-side blocklist needed
    for a single-admin platform.
    """
    response.delete_cookie(key=_REFRESH_COOKIE, path="/auth")
```

> **Design note on the token strategy:** The refresh token is stored as an `HttpOnly` cookie — the React frontend and client app never see it. The access token is returned in the response body and held in memory (React state / Python variable). This avoids the need for a `refresh_token_blocklist` table for a platform where there will be at most a handful of admin users. If you later need server-side revocation (e.g. multi-user with forced logout), add the blocklist table at that point.

### Register the auth router in `main.py`

```python
# In app/main.py — add to existing router registrations:
from .routers.auth import router as auth_router
app.include_router(auth_router)
```

---

## Task 2.8 — Protect Existing Routes with JWT

**Files:** `app/routers/funds.py`, `app/routers/benchmarks.py`, `app/routers/stocks.py`
**Estimated time:** 1 hour

This is the minimal change — one import line added per router file, then `Depends(get_current_user)` added to each route function signature. No logic changes.

### Pattern — apply to every route in every router file:

```python
# Add this import to the top of each router file:
from ..dependencies import get_current_user
from ..models import AdminUser

# Before (example from funds router):
@router.get("/funds/{scheme_code}")
async def get_fund(scheme_code: str, db: AsyncSession = Depends(get_db)):
    ...

# After:
@router.get("/funds/{scheme_code}")
async def get_fund(
    scheme_code: str,
    db: AsyncSession = Depends(get_db),
    _user: AdminUser = Depends(get_current_user),   # ← add this line
):
    ...
```

The `_user` variable is prefixed with `_` to signal it's only used for auth enforcement, not in the function body. FastAPI will call `get_current_user`, validate the token, and raise 401 automatically if it fails — before the route body executes.

### Which routes get protected

**Every route** in the three routers gets the dependency. There are no public routes on the server — all data access requires authentication. The only public endpoints are:
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /health`

---

## Task 2.9 — Health Endpoint

**File:** `app/main.py`
**Estimated time:** 30 minutes

```python
# app/main.py — add this endpoint and update the lifespan

from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from .database import engine, get_db
from .config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Verify DB connection on startup — fail fast if Supabase is unreachable
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print(f"[startup] Supabase connection OK — {settings.ENVIRONMENT}")
    except Exception as e:
        print(f"[startup] WARNING: DB connection failed: {e}")
        # Don't crash — Render will retry; let /health report the issue
    yield
    await engine.dispose()


app = FastAPI(
    title="Nivesh Platform API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # Disable docs in production to avoid exposing the API schema publicly
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

# ── Existing router registrations (keep as-is) ────────────────────────────────
# app.include_router(funds_router)
# app.include_router(benchmarks_router)
# app.include_router(stocks_router)

# ── New auth router ───────────────────────────────────────────────────────────
from .routers.auth import router as auth_router
app.include_router(auth_router)


# ── Health endpoint (no auth required) ────────────────────────────────────────
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

@app.get("/health", tags=["system"])
async def health(db: AsyncSession = Depends(get_db)):
    """
    Returns server + DB status.
    Polled by:
      - Render's health check (keeps instance warm)
      - UptimeRobot (keeps Supabase project active on free tier)
      - Client application (connectivity check every 60s)
    """
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)[:100]}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


# ── Sync status endpoint (auth required) ──────────────────────────────────────
from .crud import get_etl_run_summary
from .dependencies import get_current_user
from .models import AdminUser
from typing import Optional

@app.get("/sync/status", tags=["system"])
async def sync_status(
    pipeline_name: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _user: AdminUser = Depends(get_current_user),
):
    """Last N ETL run records, optionally filtered by pipeline_name."""
    runs = await get_etl_run_summary(db, pipeline_name, limit)
    return {"runs": runs, "total": len(runs)}
```

---

## Task 2.10 — Render Deployment

**File:** `render.yaml` (new, at `nivesh-server/` root)
**Estimated time:** 2 hours (including account setup and first deploy)

### Create `render.yaml`

```yaml
# render.yaml
services:
  - type: web
    name: nivesh-server
    runtime: python
    rootDir: nivesh-server
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
    healthCheckPath: /health
    autoDeploy: true       # Deploy automatically on push to main branch

    envVars:
      - key: DATABASE_URL
        sync: false        # Set manually in Render dashboard — never commit
      - key: ALEMBIC_URL
        sync: false        # Direct Supabase URL for migrations — set manually
      - key: SECRET_KEY
        generateValue: true  # Render generates a secure random value
      - key: ALGORITHM
        value: HS256
      - key: ACCESS_TOKEN_EXPIRE_MINUTES
        value: "15"
      - key: REFRESH_TOKEN_EXPIRE_DAYS
        value: "7"
      - key: ENVIRONMENT
        value: production
      - key: APP_VERSION
        value: "0.1.0"
      - key: DEBUG
        value: "false"
```

### Render dashboard setup steps (in order)

**Step 1 — Create Render account**
- Go to render.com → sign up with GitHub
- Connect the `prp20/Nivesh-Platform` repository

**Step 2 — Create Web Service**
- New → Web Service
- Select repo: `Nivesh-Platform`
- Branch: `main` (deploy from main, not dev)
- Root Directory: `nivesh-server`
- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`

**Step 3 — Set environment variables in Render dashboard**

Go to your service → Environment tab. Add these manually (never in `render.yaml` for secrets):

| Key | Value | Source |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres.[ref]:[pwd]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres` | Supabase dashboard → Settings → Database → Connection string → URI (Transaction mode) |
| `ALEMBIC_URL` | `postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres` | Supabase dashboard → Settings → Database → Connection string → URI (Session mode) |
| `SECRET_KEY` | Auto-generated by Render (`generateValue: true`) | — |

**Step 4 — Run Alembic migrations before first deploy**

Migrations must run against Supabase before the app starts. Run locally using the direct `ALEMBIC_URL`:

```bash
cd nivesh-server
export DATABASE_URL=$ALEMBIC_URL   # Use direct connection for Alembic
alembic upgrade head
```

Or use Render's one-off job (Render Shell) once the service is deployed:
```bash
# In Render shell (Service → Shell tab):
alembic upgrade head
```

**Step 5 — Set health check**
- In Render service settings → Health & Alerts
- Health Check Path: `/health`
- This keeps the Render instance from spinning down (free tier spins down after 15 min inactivity)

**Step 6 — UptimeRobot (keep Supabase active)**

Supabase free tier pauses projects after 1 week of inactivity. Set up a free UptimeRobot monitor:
- URL: `https://nivesh-server.onrender.com/health`
- Interval: every 5 minutes
- This simultaneously keeps Render warm and Supabase active

**Step 7 — Create first admin user**

After deploy, create the initial admin account via a one-time script:

```python
# scripts/create_admin.py — run once locally against ALEMBIC_URL
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import AdminUser
from app.security import hash_password
import uuid, os

async def main():
    engine = create_async_engine(
        os.environ["ALEMBIC_URL"].replace("postgresql://", "postgresql+asyncpg://")
    )
    async with AsyncSession(engine) as session:
        user = AdminUser(
            user_id=str(uuid.uuid4()),
            username="admin",
            email="your@email.com",
            hashed_password=hash_password("your-strong-password"),
            user_role="admin",
        )
        session.add(user)
        await session.commit()
        print(f"Admin user created: {user.username}")
    await engine.dispose()

asyncio.run(main())
```

```bash
export ALEMBIC_URL="postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres"
python scripts/create_admin.py
```

---

## Task 2.11 — Smoke Tests

**Estimated time:** 1 hour

Run these in sequence after deployment. Every one must pass before Phase 2 is considered done.

```bash
BASE="https://nivesh-server.onrender.com"

# ── 1. Health check (no auth)
curl -s $BASE/health | python -m json.tool
# Expected: {"status": "ok", "db": "ok", "version": "0.1.0", "environment": "production"}

# ── 2. Unauthenticated request should 401
curl -s -o /dev/null -w "%{http_code}" $BASE/api/funds
# Expected: 401

# ── 3. Login
TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-strong-password"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token: ${TOKEN:0:30}..."
# Expected: Token: eyJ... (non-empty)

# ── 4. Authenticated fund list
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/funds?limit=5" | python -m json.tool
# Expected: JSON with fund list from Supabase

# ── 5. Fund detail
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/funds/119598" | python -m json.tool
# Expected: Single fund with metrics

# ── 6. Benchmark list
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/benchmarks?limit=5" | python -m json.tool
# Expected: JSON with benchmark list

# ── 7. Sync status (uses EtlRun model)
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/sync/status" | python -m json.tool
# Expected: {"runs": [], "total": 0} (empty until ETL runs in Phase 3)

# ── 8. Expired token should 401
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer expired.token.here" $BASE/api/funds
# Expected: 401

# ── 9. Token refresh
curl -s -X POST $BASE/auth/refresh \
  --cookie "refresh_token=<cookie-value-from-login>" \
  | python -m json.tool
# Expected: new access_token

# ── 10. Logout
curl -s -X POST $BASE/auth/logout -H "Authorization: Bearer $TOKEN"
# Expected: 204 No Content
```

---

## 15. Dependency Changes

`requirements.txt` — add these three packages. Everything else already in requirements stays.

```text
# New additions for Phase 2:
python-jose[cryptography]==3.3.0    # JWT encode/decode
passlib[bcrypt]==1.7.4              # Password hashing
asyncpg==0.29.0                     # Async PostgreSQL driver for SQLAlchemy

# Already in requirements — confirm these are present:
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
sqlalchemy[asyncio]>=2.0.30
alembic>=1.13.1
pydantic-settings>=2.0.0
```

---

## 16. Environment Variables

### Local development (`.env` file in `nivesh-server/`)

```bash
# .env — local dev only, never committed
DATABASE_URL=postgresql://postgres:[pwd]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
ALEMBIC_URL=postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres
SECRET_KEY=dev-secret-key-change-in-production-minimum-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ENVIRONMENT=development
DEBUG=true
APP_VERSION=0.1.0
```

### Production (Render dashboard — never in files)

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Supabase → Project Settings → Database → URI (Transaction mode, port 6543) |
| `ALEMBIC_URL` | Supabase → Project Settings → Database → URI (Session mode, port 5432) |
| `SECRET_KEY` | Render auto-generates via `generateValue: true` |
| All others | Set in `render.yaml` as plain values |

---

## 17. File Tree After Phase 2

```
nivesh-server/
├── app/
│   ├── __init__.py
│   ├── main.py              ← modified: lifespan, /health, /sync/status, auth router
│   ├── config.py            ← modified: JWT + Supabase settings added
│   ├── database.py          ← modified: Supabase async engine with pool settings
│   ├── models.py            ← modified: TIMESTAMPTZ + AdminUser + EtlRun added
│   ├── schemas.py           ← modified: LoginRequest, TokenResponse, RefreshRequest added
│   ├── crud.py              ← modified: SyncJob functions → EtlRun functions
│   ├── security.py          ← NEW: hash_password, verify_password, create/decode tokens
│   ├── dependencies.py      ← NEW: get_current_user FastAPI dependency
│   └── routers/
│       ├── auth.py          ← NEW: /auth/login, /auth/refresh, /auth/logout
│       ├── funds.py         ← modified: Depends(get_current_user) added
│       ├── benchmarks.py    ← modified: Depends(get_current_user) added
│       └── stocks.py        ← modified: Depends(get_current_user) added
├── alembic/
│   └── versions/
│       ├── 001_timestamptz_fix.py
│       ├── 002_add_admin_users.py
│       ├── 003_add_etl_runs.py
│       └── 004_migrate_sync_jobs.py
├── scripts/
│   └── create_admin.py      ← NEW: one-time admin user creation
├── render.yaml              ← NEW
├── requirements.txt         ← modified: 3 new packages
└── .env.example             ← NEW
```

---

## 18. Definition of Done

Phase 2 is complete when all of the following are true:

- [ ] `GET /health` returns `{"status": "ok", "db": "ok"}` from the Render URL
- [ ] `POST /auth/login` with correct credentials returns an `access_token`
- [ ] `POST /auth/login` with wrong credentials returns 401
- [ ] All existing fund, benchmark, and stock routes return 401 without a token
- [ ] All existing fund, benchmark, and stock routes return data with a valid token
- [ ] `POST /auth/refresh` returns a new access token when given a valid refresh cookie
- [ ] `POST /auth/logout` clears the refresh cookie
- [ ] `GET /sync/status` returns the etl_runs table (empty or with migrated data)
- [ ] Alembic `alembic current` shows `head` against Supabase
- [ ] `admin_users` table exists in Supabase with the initial admin row
- [ ] `etl_runs` table exists in Supabase
- [ ] `sync_jobs` and `pipeline_audit` tables are dropped (after data migration)
- [ ] UptimeRobot monitor is pinging `/health` every 5 minutes
- [ ] All 10 smoke tests in Task 2.11 pass

---

## Execution Order

```
Day 1 (4h)
  Task 2.1  Supabase connection                    1h
  Task 2.2  TIMESTAMPTZ fix across models.py       1h
  Task 2.3  Add AdminUser + EtlRun to models.py    1h
  Task 2.4  security.py + dependencies.py          1h

Day 2 (4h)
  Task 2.5  Update crud.py                         1.5h
  Task 2.6  Auth schemas in schemas.py             0.5h
  Task 2.7  Auth router                            1.5h
  Task 2.8  Protect existing routes                0.5h

Day 3 (3h)
  Task 2.9  Health + sync/status in main.py        0.5h
  Task 2.10 Render setup + Alembic migrations      2h
  Task 2.11 Smoke tests + fix any issues           0.5h
```

**Total: 3 working days**

---

*Phase 2 Implementation Plan · Nivesh Platform · May 2026*
*Previous: Phase 1 — Supabase DB Design*
*Next: Phase 3 — Ingestion Pipeline*
