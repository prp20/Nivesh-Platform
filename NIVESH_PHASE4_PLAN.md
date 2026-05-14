# Nivesh Platform — Phase 4: Client Application
## Detailed Implementation Plan · Grounded in dev branch code
### Version 1.0 · May 2026

---

## Table of Contents

1. [Phase 4 Goal & Scope](#1-phase-4-goal--scope)
2. [What the Codebase Tells Us](#2-what-the-codebase-tells-us)
3. [Client Architecture Overview](#3-client-architecture-overview)
4. [File Tree — Full Client](#4-file-tree--full-client)
5. [Task 4.1 — Project Scaffold & Config](#task-41--project-scaffold--config)
6. [Task 4.2 — SQLite Database & Models](#task-42--sqlite-database--models)
7. [Task 4.3 — Alembic for SQLite](#task-43--alembic-for-sqlite)
8. [Task 4.4 — Server HTTP Client](#task-44--server-http-client)
9. [Task 4.5 — JWT Auth Flow](#task-45--jwt-auth-flow)
10. [Task 4.6 — Cache Layer](#task-46--cache-layer)
11. [Task 4.7 — Sync Engine](#task-47--sync-engine)
12. [Task 4.8 — Portfolio & Watchlist CRUD](#task-48--portfolio--watchlist-crud)
13. [Task 4.9 — Proxy Router](#task-49--proxy-router)
14. [Task 4.10 — Agentic Layer](#task-410--agentic-layer)
15. [Task 4.11 — Client FastAPI Main](#task-411--client-fastapi-main)
16. [Task 4.12 — Install Script](#task-412--install-script)
17. [Client SQLite Schema — Full DDL](#17-client-sqlite-schema--full-ddl)
18. [Dependency Reference](#18-dependency-reference)
19. [Environment Variables](#19-environment-variables)
20. [Definition of Done](#20-definition-of-done)
21. [Execution Order — Day by Day](#21-execution-order--day-by-day)

---

## 1. Phase 4 Goal & Scope

**Goal:** Build the client application — a local FastAPI process running on the user's machine at port `8001`. It owns all user-private data (portfolio, watchlist), caches server responses in SQLite with TTL expiry, handles JWT auth transparently, and exposes a local API that the React frontend talks to. The React UI never communicates with the cloud server directly.

**In scope:**
- `nivesh-client/` directory with its own FastAPI app, SQLite DB, and Alembic migrations
- All client SQLite models: watchlist, portfolio, transactions, user preferences, cache tables, auth token storage, agentic session tables
- JWT auth flow: login via server → store token in SQLite → inject on every proxied request → auto-refresh on 401
- Sync engine: pull from server API, cache locally, serve stale cache on offline
- Proxy router: React calls `localhost:8001/proxy/*` → client injects JWT → forwards to Render server
- Portfolio and watchlist local CRUD (no server involvement)
- Agentic layer: LangGraph-compatible session storage, tool definitions, memory persistence
- Windows `setup.bat` extension + new `setup.sh` for Linux/Mac
- `.env.example` with `NIVESH_SERVER_URL`

**Out of scope for Phase 4:**
- React UI changes (Phase 7)
- Agent LLM calls (Phase 6 — the storage layer is built here, the LLM wiring is Phase 6)
- CI/CD (Phase 8)

**Critical constraint confirmed by `schemas.py`:**
`ScoringStateSchema` in `schemas.py` (line 463) includes `logs: List[str]`, `statements_data`, `pl_results`, `bs_results`, `cf_results` — this is a **LangGraph state dict**. The existing project already uses LangGraph for fundamental scoring. The client agentic layer must store LangGraph-compatible state, not just simple chat messages.

---

## 2. What the Codebase Tells Us

Reading `models.py`, `schemas.py`, and `crud.py` surfaces five specific things that directly shape Phase 4:

| Evidence in code | Phase 4 implication |
|---|---|
| `ScoringStateSchema` with `logs`, `statements_data`, `pl_results`, `bs_results`, `cf_results` | Client agent storage must handle LangGraph state dicts — `agent_messages` stores JSON blobs, not just text strings |
| `FundMetricsResponse` has `sync_job_id`, `sync_status`, `sync_message` | The client proxy must return these fields — the React UI already renders sync status from them |
| `FundMasterListResponse` has `total`, `skip`, `limit`, `items` | The proxy router must preserve the server's pagination envelope exactly — React parses this shape |
| `ComparisonResponse` with `funds[]`, `ranking`, `warning` | Fund comparison is a server-computed response — client just caches it, doesn't recompute |
| `ScreenerFilterInput` with 20+ filter fields | Stock screener calls go through the proxy — too complex to cache meaningfully, always forwarded live |
| `StockDetailResult` with `rsi_14`, `macd_hist`, `sma_200` etc. | Stock detail is a joined response from multiple server tables — cached as a JSONB blob, TTL 1 hour |

---

## 3. Client Architecture Overview

```
User's machine
─────────────────────────────────────────────────────────
React UI (port 5173 dev / embedded in prod)
    │  calls localhost:8001 only — never the cloud server
    ▼
nivesh-client FastAPI (port 8001)
    │
    ├── /auth/*          ← Login, refresh, logout (talks to server, stores token locally)
    ├── /local/*         ← Portfolio, watchlist, transactions, prefs (pure local SQLite)
    ├── /proxy/*         ← Forwards to server with JWT injected, caches response in SQLite
    ├── /agent/*         ← Agent session management, message history, memory (local only)
    └── /status          ← Sync state, server connectivity, last synced timestamps
    │
    ├── SQLite DB  (~/.nivesh/client.db)
    │   ├── watchlist
    │   ├── portfolio_holdings
    │   ├── transactions
    │   ├── user_preferences
    │   ├── auth_tokens
    │   ├── server_config
    │   ├── cache_entries          ← key-value TTL cache for all server responses
    │   ├── agent_sessions
    │   ├── agent_messages         ← stores LangGraph state JSON + plain text
    │   └── agent_memory
    │
    └── APScheduler (background)
        ├── health_ping   — every 60s (server connectivity check)
        └── cache_cleanup — every hour (delete expired cache_entries)

                │ HTTPS + Bearer token
                ▼
        Render Server (cloud)
        └── PostgreSQL on Supabase
```

---

## 4. File Tree — Full Client

```
nivesh-client/
├── app/
│   ├── __init__.py
│   ├── main.py                  ← FastAPI app, lifespan, scheduler
│   ├── config.py                ← Settings (NIVESH_SERVER_URL, ports, paths)
│   ├── database.py              ← SQLite async engine, WAL mode, get_db
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user_data.py         ← watchlist, portfolio_holdings, transactions, user_preferences
│   │   ├── cache.py             ← cache_entries (unified TTL cache)
│   │   ├── auth.py              ← auth_tokens, server_config
│   │   └── agent.py             ← agent_sessions, agent_messages, agent_memory
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              ← /auth/login, /auth/refresh, /auth/logout
│   │   ├── local.py             ← /local/portfolio, /local/watchlist, /local/transactions
│   │   ├── proxy.py             ← /proxy/* → server with JWT + cache
│   │   ├── agent.py             ← /agent/sessions, /agent/chat, /agent/memory
│   │   └── status.py            ← /status (connectivity, last sync, cache stats)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── http_client.py       ← httpx async client: JWT injection, retry, 401 refresh
│   │   ├── cache.py             ← TTL cache read/write/invalidate against cache_entries
│   │   ├── sync.py              ← background sync: pull server data into cache
│   │   └── agent_tools.py       ← LangGraph-compatible tool definitions
│   ├── scheduler.py             ← APScheduler: health ping + cache cleanup
│   └── schemas.py               ← Client-specific Pydantic schemas (thin — reuses server shapes)
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_agent_tables.py
├── alembic.ini
├── .env.example
├── requirements.txt
└── setup/
    ├── setup.bat                ← Windows (extend existing)
    └── setup.sh                 ← Linux/Mac (new)
```

---

## Task 4.1 — Project Scaffold & Config

**Estimated time:** 1 hour

### `app/config.py`

```python
# app/config.py
from pydantic_settings import BaseSettings
from pathlib import Path
import os

# Default DB path: ~/.nivesh/client.db
# Using user home keeps it outside the project dir
# so reinstalling the client doesn't wipe data
_DEFAULT_DB_PATH = Path.home() / ".nivesh" / "client.db"


class Settings(BaseSettings):
    # ── Server connection ──────────────────────────────────────────────────────
    NIVESH_SERVER_URL: str = "http://localhost:8000"
    # In production: https://nivesh-server.onrender.com

    # ── Client app ────────────────────────────────────────────────────────────
    CLIENT_PORT: int = 8001
    SQLITE_DB_PATH: str = str(_DEFAULT_DB_PATH)
    DEBUG: bool = False

    # ── Cache TTLs (seconds) ──────────────────────────────────────────────────
    # These control how long server responses are served from local SQLite
    # before being re-fetched from the server.
    CACHE_TTL_FUND_LIST: int      = 3600       # 1 hour
    CACHE_TTL_FUND_DETAIL: int    = 3600       # 1 hour
    CACHE_TTL_FUND_NAV: int       = 86400      # 24 hours — NAV only changes once a day
    CACHE_TTL_STOCK_DETAIL: int   = 3600       # 1 hour
    CACHE_TTL_STOCK_LIST: int     = 3600       # 1 hour
    CACHE_TTL_SCREENER: int       = 900        # 15 minutes — screener results change often
    CACHE_TTL_BENCHMARKS: int     = 3600       # 1 hour
    CACHE_TTL_ETL_STATUS: int     = 300        # 5 minutes

    # ── Scheduler ─────────────────────────────────────────────────────────────
    HEALTH_PING_INTERVAL_S: int   = 60         # How often to ping /health
    CACHE_CLEANUP_INTERVAL_S: int = 3600       # How often to delete expired cache rows

    class Config:
        env_file = str(Path.home() / ".nivesh" / ".env")
        extra = "ignore"


settings = Settings()
```

### `.env.example`

```bash
# Copy this to ~/.nivesh/.env and fill in the values

# URL of the deployed Render server
NIVESH_SERVER_URL=https://nivesh-server.onrender.com

# Port for the local client API (default: 8001)
CLIENT_PORT=8001

# SQLite DB file path (default: ~/.nivesh/client.db)
# SQLITE_DB_PATH=/custom/path/client.db

# Set to true for SQL query logging
DEBUG=false
```

---

## Task 4.2 — SQLite Database & Models

**File:** `app/database.py` + `app/models/`
**Estimated time:** 2 hours

### `app/database.py`

```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import event, text
from pathlib import Path
from .config import settings

# Ensure ~/.nivesh/ exists before SQLite tries to create the file
Path(settings.SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.SQLITE_DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG,
)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(dbapi_conn, _):
    """
    Apply SQLite pragmas on every new connection.
    WAL mode: allows one writer and multiple concurrent readers —
    critical because APScheduler and FastAPI both access the DB.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")  # Faster than FULL, still safe with WAL
    cursor.close()


AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### `app/models/user_data.py`

```python
# app/models/user_data.py
from sqlalchemy import Column, Integer, String, Float, Date, Boolean, Text, TIMESTAMP
from sqlalchemy.sql import func
from ..database import Base


class Watchlist(Base):
    """
    User's personal watchlist — stocks and funds to track.
    Never sent to the server. Local only.
    """
    __tablename__ = "watchlist"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    symbol       = Column(String(50), nullable=False)
    asset_type   = Column(String(10), nullable=False)
    # asset_type: 'STOCK' | 'FUND'
    # For STOCK: symbol is the NSE symbol (e.g. 'RELIANCE')
    # For FUND:  symbol is the scheme_code (e.g. '119598')
    display_name = Column(String(255))
    notes        = Column(Text)
    alert_above  = Column(Float)      # Price/NAV alert threshold (high)
    alert_below  = Column(Float)      # Price/NAV alert threshold (low)
    added_at     = Column(TIMESTAMP,  server_default=func.now())
    updated_at   = Column(TIMESTAMP,  server_default=func.now(), onupdate=func.now())


class PortfolioHolding(Base):
    """
    User's actual holdings. Never sent to the server.
    Supports both stocks and mutual funds in one table.
    """
    __tablename__ = "portfolio_holdings"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    symbol       = Column(String(50), nullable=False)
    asset_type   = Column(String(10), nullable=False)   # 'STOCK' | 'FUND'
    quantity     = Column(Float, nullable=False)
    avg_cost     = Column(Float, nullable=False)         # Per unit cost (price or NAV)
    buy_date     = Column(Date, nullable=False)
    folio_number = Column(String(50))                    # MF folio number, if applicable
    broker       = Column(String(100))                   # Broker/AMC name
    notes        = Column(Text)
    created_at   = Column(TIMESTAMP, server_default=func.now())
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Transaction(Base):
    """
    Full transaction history — buy, sell, dividend, SIP instalment.
    Local ledger only.
    """
    __tablename__ = "transactions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    symbol       = Column(String(50), nullable=False)
    asset_type   = Column(String(10), nullable=False)
    txn_type     = Column(String(15), nullable=False)
    # txn_type: 'BUY' | 'SELL' | 'DIVIDEND' | 'SIP' | 'SWITCH_IN' | 'SWITCH_OUT'
    quantity     = Column(Float, nullable=False)
    price        = Column(Float, nullable=False)         # Price or NAV at time of txn
    txn_date     = Column(Date, nullable=False)
    amount       = Column(Float)                         # quantity × price (stored for quick calc)
    brokerage    = Column(Float, default=0.0)
    notes        = Column(Text)
    created_at   = Column(TIMESTAMP, server_default=func.now())


class UserPreference(Base):
    """
    Key-value store for all user settings.
    Using a KV table rather than a single wide row means
    adding new preferences doesn't require a schema migration.
    """
    __tablename__ = "user_preferences"

    key        = Column(String(100), primary_key=True)
    # Keys in use:
    #   'default_benchmark'     → benchmark_code string
    #   'default_plan_type'     → 'Direct' | 'Regular'
    #   'chart_interval'        → '1d' | '1w'
    #   'theme'                 → 'dark' | 'light'
    #   'server_connected'      → 'true' | 'false'
    #   'last_login_username'   → username string
    value      = Column(Text, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
```

### `app/models/cache.py`

```python
# app/models/cache.py
from sqlalchemy import Column, String, Text, Integer, TIMESTAMP
from sqlalchemy.sql import func
from ..database import Base


class CacheEntry(Base):
    """
    Unified TTL cache for all server API responses.

    A single table for all cached data avoids multiple cache_stock_xxx,
    cache_fund_xxx tables. The cache_key is a namespaced string:
      'fund_list:category=Equity&amc=SBI'
      'fund_detail:119598'
      'fund_nav:119598'
      'stock_detail:RELIANCE'
      'stock_list:page=1'
      'benchmarks:all'
      'etl_status:all'

    data_json stores the raw JSON string of the server response.
    The proxy router deserialises it and returns it to the React UI as-is —
    preserving the exact shape the UI already expects (FundMasterListResponse,
    StockDetailResult, etc.) without any client-side schema translation.
    """
    __tablename__ = "cache_entries"

    cache_key   = Column(String(500), primary_key=True)
    data_json   = Column(Text, nullable=False)
    fetched_at  = Column(TIMESTAMP, nullable=False, server_default=func.now())
    ttl_seconds = Column(Integer, nullable=False, default=3600)
    server_generated_at = Column(String(50))
    # ^ Stores the server's generated_at timestamp if present in the response.
    # Used for delta sync: we know data is fresh up to this point.
```

### `app/models/auth.py`

```python
# app/models/auth.py
from sqlalchemy import Column, String, Integer, TIMESTAMP, Text
from sqlalchemy.sql import func
from ..database import Base


class AuthToken(Base):
    """
    Stores the current JWT access and refresh tokens.
    Only one row ever exists (id=1). Replaced on each login/refresh.
    Tokens are stored in SQLite, not browser storage or env vars.
    """
    __tablename__ = "auth_tokens"

    id            = Column(Integer, primary_key=True, default=1)
    access_token  = Column(Text, nullable=False)
    refresh_token = Column(Text)
    # refresh_token is None when using cookie-based refresh (Phase 2 design)
    # Kept here for cases where the client needs to hold it explicitly
    expires_at    = Column(TIMESTAMP, nullable=False)
    username      = Column(String(50))
    created_at    = Column(TIMESTAMP, server_default=func.now())


class ServerConfig(Base):
    """
    Key-value store for server connection state.
    Single-row table updated on every health ping.
    """
    __tablename__ = "server_config"

    key   = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    # Keys:
    #   'server_url'          → from NIVESH_SERVER_URL env var
    #   'is_online'           → 'true' | 'false'
    #   'last_connected_at'   → ISO timestamp
    #   'server_version'      → from /health response
    #   'last_health_check'   → ISO timestamp of last ping
```

### `app/models/agent.py`

```python
# app/models/agent.py
"""
Client-side agentic storage.

The existing project uses LangGraph for the fundamental scoring pipeline
(confirmed by ScoringStateSchema in schemas.py). The client agent layer
uses the same pattern: state is a dict stored as JSON, not a fixed schema.

Three tables:
  agent_sessions  — one row per conversation thread
  agent_messages  — one row per message/tool call in a session
  agent_memory    — persistent facts extracted from conversations
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean
from sqlalchemy.sql import func
from sqlalchemy.dialects.sqlite import JSON   # SQLite JSON type
from ..database import Base


class AgentSession(Base):
    """One session = one focused conversation (e.g. 'Analyse RELIANCE')."""
    __tablename__ = "agent_sessions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    title        = Column(String(255))
    # Auto-generated from first user message if not provided
    context_type = Column(String(20))
    # context_type: 'stock' | 'fund' | 'portfolio' | 'screener' | 'general'
    context_id   = Column(String(50))
    # context_id: NSE symbol, scheme_code, or None for portfolio/general
    model_used   = Column(String(50), default="claude-sonnet-4-6")
    is_active    = Column(Boolean, default=True)
    started_at   = Column(TIMESTAMP, server_default=func.now())
    last_msg_at  = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class AgentMessage(Base):
    """
    One row per turn in a session.
    Stores both plain text messages and LangGraph state dicts.

    The 'role' field follows the LangGraph/LLM convention:
      'user'      — user input
      'assistant' — LLM response
      'tool'      — tool call result (JSON payload from a server API call)
      'state'     — full LangGraph state snapshot (for complex pipelines)

    content_json stores either:
      - A string (for user/assistant messages)
      - A JSON dict (for tool results and LangGraph state)
    This matches ScoringStateSchema which has nested dicts for pl_results,
    bs_results, cf_results, statements_data, and a logs list.
    """
    __tablename__ = "agent_messages"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(Integer, nullable=False)
    # FK to agent_sessions.id — not using SQLAlchemy FK to keep it simple
    sequence_num  = Column(Integer, nullable=False)
    # Order within the session — used for reconstructing conversation history
    role          = Column(String(15), nullable=False)
    content_text  = Column(Text)
    # Plain text version (for user/assistant messages — UI display)
    content_json  = Column(JSON)
    # JSON version (for tool results and LangGraph state dicts)
    tool_name     = Column(String(100))
    # Populated when role='tool' — which tool was called
    created_at    = Column(TIMESTAMP, server_default=func.now())


class AgentMemory(Base):
    """
    Persistent facts extracted across sessions.
    The agent reads these at the start of each new session to personalise responses.

    Examples:
      key='risk_tolerance',  value='conservative — prefers large-cap funds'
      key='preferred_sector', value='IT, Pharma'
      key='portfolio_size',  value='medium — 10-20 holdings'
    """
    __tablename__ = "agent_memory"

    key        = Column(String(200), primary_key=True)
    value      = Column(Text, nullable=False)
    source     = Column(String(50))
    # source: 'user_stated' | 'inferred' | 'manual'
    confidence = Column(String(10), default="high")
    # confidence: 'high' | 'medium' | 'low'
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
```

---

## Task 4.3 — Alembic for SQLite

**Estimated time:** 1 hour

### Setup

```bash
cd nivesh-client
alembic init alembic
```

### `alembic/env.py` — key changes from default

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from app.database import Base
from app.config import settings
# Import all models so Alembic can detect them
from app.models.user_data import Watchlist, PortfolioHolding, Transaction, UserPreference
from app.models.cache import CacheEntry
from app.models.auth import AuthToken, ServerConfig
from app.models.agent import AgentSession, AgentMessage, AgentMemory

config = context.config
target_metadata = Base.metadata


def run_migrations_online():
    """Run migrations in 'online' mode against the SQLite DB."""
    connectable = create_async_engine(
        f"sqlite+aiosqlite:///{settings.SQLITE_DB_PATH}",
        connect_args={"check_same_thread": False},
    )

    async def do_run():
        async with connectable.connect() as connection:
            await connection.run_sync(
                lambda conn: context.configure(
                    connection=conn,
                    target_metadata=target_metadata,
                    render_as_batch=True,  # Required for SQLite ALTER TABLE support
                )
            )
            async with connection.begin():
                await connection.run_sync(lambda conn: context.run_migrations())

    asyncio.run(do_run())
```

> **`render_as_batch=True` is critical for SQLite.** SQLite does not support `ALTER TABLE ADD COLUMN` in some cases. Alembic's batch mode rewrites the table in a temp copy. Without this, future schema migrations will fail.

### Auto-migrate on startup in `main.py`

```python
# Called once during FastAPI lifespan startup
def run_migrations():
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

---

## Task 4.4 — Server HTTP Client

**File:** `app/services/http_client.py`
**Estimated time:** 2 hours

This is the core infrastructure that every proxy call and sync operation uses. It handles JWT injection, 401 auto-refresh, retry on 5xx, and `OfflineError` on connection failure.

```python
# app/services/http_client.py
import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ..models.auth import AuthToken, ServerConfig
from ..config import settings

logger = logging.getLogger(__name__)


class OfflineError(Exception):
    """Raised when the server cannot be reached."""
    pass


class SessionExpiredError(Exception):
    """Raised when the refresh token is also expired — user must log in again."""
    pass


class ServerClient:
    """
    Async httpx client for all calls to the Render server.

    Responsibilities:
    1. Reads access_token from auth_tokens SQLite table
    2. Sets Authorization: Bearer header on every request
    3. On 401: fetches new access_token using the refresh cookie
    4. On 5xx: retries up to 3 times with 2s backoff
    5. On connection error: raises OfflineError
    6. Updates server_config.is_online on success/failure

    Usage (as async context manager):
        async with ServerClient(db) as client:
            data = await client.get("/api/funds")

    Usage (one-shot):
        data = await ServerClient.fetch(db, "GET", "/api/funds")
    """

    def __init__(self, db: AsyncSession):
        self.db  = db
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None

    async def __aenter__(self):
        self._token = await self._load_access_token()
        self._client = httpx.AsyncClient(
            base_url=settings.NIVESH_SERVER_URL,
            timeout=30,
            headers=self._auth_headers(),
        )
        return self

    async def __aexit__(self, *_):
        if self._client:
            await self._client.aclose()

    def _auth_headers(self) -> dict:
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    async def get(self, path: str, params: dict = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict = None) -> Any:
        return await self._request("POST", path, json=json)

    async def _request(
        self, method: str, path: str,
        params: dict = None, json: dict = None,
        _retry: int = 0,
    ) -> Any:
        try:
            resp = await self._client.request(
                method, path, params=params, json=json
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            await self._mark_offline()
            raise OfflineError(f"Server unreachable: {e}") from e

        # ── Token expired ──────────────────────────────────────────────────────
        if resp.status_code == 401 and _retry == 0:
            logger.info("Access token expired — refreshing")
            try:
                self._token = await self._refresh_token()
                self._client.headers["Authorization"] = f"Bearer {self._token}"
                return await self._request(method, path, params=params,
                                           json=json, _retry=1)
            except SessionExpiredError:
                raise
            except Exception as e:
                raise OfflineError(f"Token refresh failed: {e}") from e

        # ── Server errors: retry up to 3 times ────────────────────────────────
        if resp.status_code >= 500 and _retry < 3:
            import asyncio
            await asyncio.sleep(2 ** _retry)
            return await self._request(method, path, params=params,
                                       json=json, _retry=_retry + 1)

        resp.raise_for_status()
        await self._mark_online()
        return resp.json()

    async def _load_access_token(self) -> Optional[str]:
        result = await self.db.execute(
            select(AuthToken).where(AuthToken.id == 1)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        # Check expiry with 60s buffer
        if row.expires_at < datetime.now(timezone.utc) + timedelta(seconds=60):
            logger.info("Access token near expiry — will refresh on first call")
        return row.access_token

    async def _refresh_token(self) -> str:
        """
        Call /auth/refresh. The refresh_token is sent as an HttpOnly cookie
        by the browser. For the Python client app, we POST the stored refresh
        token explicitly in the request body.
        """
        result = await self.db.execute(
            select(AuthToken).where(AuthToken.id == 1)
        )
        token_row = result.scalar_one_or_none()
        if not token_row or not token_row.refresh_token:
            raise SessionExpiredError("No refresh token stored")

        async with httpx.AsyncClient(base_url=settings.NIVESH_SERVER_URL) as c:
            resp = await c.post(
                "/auth/refresh",
                json={"refresh_token": token_row.refresh_token}
            )
            if resp.status_code == 401:
                raise SessionExpiredError("Refresh token expired — please log in again")
            resp.raise_for_status()
            data = resp.json()

        # Save new access token
        expires_at = datetime.now(timezone.utc) + \
                     timedelta(seconds=data["expires_in"])
        await self.db.execute(
            update(AuthToken)
            .where(AuthToken.id == 1)
            .values(
                access_token=data["access_token"],
                expires_at=expires_at,
            )
        )
        await self.db.commit()
        return data["access_token"]

    async def _mark_online(self):
        await self._set_config("is_online", "true")
        await self._set_config("last_connected_at",
                               datetime.now(timezone.utc).isoformat())

    async def _mark_offline(self):
        await self._set_config("is_online", "false")

    async def _set_config(self, key: str, value: str):
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = sqlite_insert(ServerConfig).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(index_elements=["key"],
                                          set_={"value": value})
        await self.db.execute(stmt)
        await self.db.commit()

    @classmethod
    async def fetch(cls, db: AsyncSession, method: str,
                    path: str, **kwargs) -> Any:
        """Convenience one-shot method for simple calls."""
        async with cls(db) as client:
            return await client._request(method, path, **kwargs)
```

---

## Task 4.5 — JWT Auth Flow

**File:** `app/routers/auth.py`
**Estimated time:** 1.5 hours

```python
# app/routers/auth.py
import httpx
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import select, update, delete
from ..database import get_db
from ..models.auth import AuthToken, ServerConfig
from ..config import settings
from ..schemas import LoginRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Forward login to the Render server.
    Store the returned tokens in local SQLite.
    Return the access_token to the React UI (which holds it in memory only).

    The React UI never talks to the server directly — it calls this endpoint,
    which proxies to the server and stores the credentials locally.
    """
    try:
        async with httpx.AsyncClient(
            base_url=settings.NIVESH_SERVER_URL, timeout=15
        ) as client:
            resp = await client.post(
                "/auth/login",
                json={"username": body.username, "password": body.password}
            )
    except (httpx.ConnectError, httpx.TimeoutException):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot reach server — check NIVESH_SERVER_URL and connectivity",
        )

    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    resp.raise_for_status()
    data = resp.json()

    # Store tokens in SQLite auth_tokens table (single row, id=1)
    expires_at = datetime.now(timezone.utc) + \
                 timedelta(seconds=data["expires_in"])

    stmt = sqlite_insert(AuthToken).values(
        id=1,
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=expires_at,
        username=body.username,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "access_token":  data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_at":    expires_at,
            "username":      body.username,
        }
    )
    await db.execute(stmt)

    # Record server URL in server_config
    for key, val in [
        ("server_url", settings.NIVESH_SERVER_URL),
        ("is_online", "true"),
        ("last_connected_at", datetime.now(timezone.utc).isoformat()),
    ]:
        kv = sqlite_insert(ServerConfig).values(key=key, value=val)
        kv = kv.on_conflict_do_update(index_elements=["key"], set_={"value": val})
        await db.execute(kv)

    await db.commit()
    logger.info(f"User '{body.username}' logged in — tokens stored in SQLite")

    return TokenResponse(
        access_token=data["access_token"],
        expires_in=data["expires_in"],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(db: AsyncSession = Depends(get_db)):
    """
    Clear stored tokens from SQLite.
    Optionally notifies the server (best-effort — don't fail if offline).
    """
    # Get token for server notification
    result = await db.execute(select(AuthToken).where(AuthToken.id == 1))
    token_row = result.scalar_one_or_none()

    if token_row:
        try:
            async with httpx.AsyncClient(
                base_url=settings.NIVESH_SERVER_URL, timeout=5
            ) as client:
                await client.post(
                    "/auth/logout",
                    headers={"Authorization": f"Bearer {token_row.access_token}"},
                    json={"refresh_token": token_row.refresh_token},
                )
        except Exception:
            pass  # Best-effort — local logout still succeeds

    await db.execute(delete(AuthToken).where(AuthToken.id == 1))
    await db.commit()
```

### Client `schemas.py` — auth schemas

```python
# app/schemas.py
from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class SyncStatus(BaseModel):
    is_online: bool
    last_connected_at: Optional[str] = None
    server_url: str
    server_version: Optional[str] = None
    cached_resources: int = 0
```

---

## Task 4.6 — Cache Layer

**File:** `app/services/cache.py`
**Estimated time:** 1.5 hours

```python
# app/services/cache.py
"""
TTL cache backed by the cache_entries SQLite table.

All server API responses are stored here as raw JSON strings.
The proxy router checks the cache before making a server call.
If the cache is stale (or missing), the proxy fetches fresh data,
updates the cache, then returns the response.

If the server is offline, the proxy returns the stale cache
with an 'offline: true' flag in the response.

Cache key naming convention:
    'funds:list:{query_hash}'       — paginated fund list
    'funds:detail:{scheme_code}'    — single fund with metrics
    'funds:nav:{scheme_code}'       — NAV history
    'funds:compare:{codes_hash}'    — comparison response
    'stocks:list:{query_hash}'      — paginated stock list
    'stocks:detail:{symbol}'        — single stock detail
    'stocks:screener:{filter_hash}' — screener results
    'benchmarks:list'               — all benchmarks
    'benchmarks:detail:{code}'      — single benchmark
    'etl:status'                    — pipeline run status
"""
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from ..models.cache import CacheEntry

logger = logging.getLogger(__name__)


def make_cache_key(prefix: str, params: dict = None) -> str:
    """
    Build a deterministic cache key from a prefix and optional params dict.
    Params dict is sorted before hashing so {a:1, b:2} == {b:2, a:1}.
    """
    if not params:
        return prefix
    param_str = json.dumps(params, sort_keys=True, default=str)
    hash_suffix = hashlib.md5(param_str.encode()).hexdigest()[:8]
    return f"{prefix}:{hash_suffix}"


async def get_cached(db: AsyncSession, cache_key: str) -> tuple[Optional[Any], bool]:
    """
    Returns (data, is_fresh).
    data: parsed JSON from cache, or None if not cached at all
    is_fresh: True if within TTL, False if stale (serve anyway if offline)
    """
    result = await db.execute(
        select(CacheEntry).where(CacheEntry.cache_key == cache_key)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None, False

    age_seconds = (
        datetime.now(timezone.utc) - row.fetched_at.replace(tzinfo=timezone.utc)
    ).total_seconds()
    is_fresh = age_seconds < row.ttl_seconds

    try:
        data = json.loads(row.data_json)
    except json.JSONDecodeError:
        return None, False

    return data, is_fresh


async def set_cached(
    db: AsyncSession,
    cache_key: str,
    data: Any,
    ttl_seconds: int,
    server_generated_at: Optional[str] = None,
) -> None:
    """Write or overwrite a cache entry."""
    stmt = sqlite_insert(CacheEntry).values(
        cache_key=cache_key,
        data_json=json.dumps(data, default=str),
        fetched_at=datetime.now(timezone.utc),
        ttl_seconds=ttl_seconds,
        server_generated_at=server_generated_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["cache_key"],
        set_={
            "data_json":            json.dumps(data, default=str),
            "fetched_at":           datetime.now(timezone.utc),
            "ttl_seconds":          ttl_seconds,
            "server_generated_at":  server_generated_at,
        }
    )
    await db.execute(stmt)
    await db.commit()


async def invalidate(db: AsyncSession, prefix: str) -> int:
    """Delete all cache entries whose key starts with prefix."""
    result = await db.execute(
        delete(CacheEntry).where(CacheEntry.cache_key.like(f"{prefix}%"))
    )
    await db.commit()
    return result.rowcount


async def cleanup_expired(db: AsyncSession) -> int:
    """
    Delete all cache entries past their TTL.
    Called by the APScheduler cleanup job every hour.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    result = await db.execute(
        delete(CacheEntry).where(
            # SQLite: datetime arithmetic via strftime
            CacheEntry.fetched_at < datetime.now(timezone.utc)
        )
    )
    await db.commit()
    count = result.rowcount
    if count:
        logger.info(f"Cache cleanup: deleted {count} expired entries")
    return count
```

---

## Task 4.7 — Sync Engine

**File:** `app/services/sync.py`
**Estimated time:** 1.5 hours

```python
# app/services/sync.py
"""
Background sync: proactively refreshes stale cache entries.
Called by APScheduler and on client startup.

The sync engine is intentionally simple:
- It checks specific high-priority cache keys
- If stale, fetches from server and updates cache
- On OfflineError, leaves stale cache in place

It does NOT implement delta sync (from_date) for Phase 4.
Delta sync is Phase 5. Here we just do full refreshes within TTL windows.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .http_client import ServerClient, OfflineError
from .cache import get_cached, set_cached
from ..config import settings

logger = logging.getLogger(__name__)


async def sync_fund_list(db: AsyncSession) -> bool:
    """Refresh the main fund list cache. Returns True if refreshed."""
    cache_key = "funds:list:default"
    _, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return False

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/funds", params={"limit": 100, "is_active": True})
        await set_cached(db, cache_key, data,
                         ttl_seconds=settings.CACHE_TTL_FUND_LIST)
        logger.info("Synced fund list")
        return True
    except OfflineError:
        logger.warning("sync_fund_list: server offline — using stale cache")
        return False


async def sync_benchmark_list(db: AsyncSession) -> bool:
    """Refresh benchmark master list."""
    cache_key = "benchmarks:list"
    _, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return False

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/benchmarks", params={"is_active": True})
        await set_cached(db, cache_key, data,
                         ttl_seconds=settings.CACHE_TTL_BENCHMARKS)
        return True
    except OfflineError:
        return False


async def run_startup_sync(db: AsyncSession) -> None:
    """
    Runs once on client startup.
    Warms the cache with the most commonly accessed data.
    Runs in the background — doesn't block the FastAPI startup.
    """
    logger.info("Running startup cache warm...")
    await sync_fund_list(db)
    await sync_benchmark_list(db)
    logger.info("Startup sync complete")


async def ping_server(db: AsyncSession) -> bool:
    """
    Called by APScheduler every 60 seconds.
    Updates server_config.is_online based on /health response.
    """
    import httpx
    from ..models.auth import ServerConfig
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    try:
        async with httpx.AsyncClient(
            base_url=settings.NIVESH_SERVER_URL, timeout=10
        ) as client:
            resp = await client.get("/health")
            resp.raise_for_status()
            health = resp.json()
            is_online = health.get("status") == "ok"
    except Exception:
        is_online = False

    value = "true" if is_online else "false"
    stmt = sqlite_insert(ServerConfig).values(key="is_online", value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"], set_={"value": value}
    )
    await db.execute(stmt)
    await db.commit()
    return is_online
```

---

## Task 4.8 — Portfolio & Watchlist CRUD

**File:** `app/routers/local.py`
**Estimated time:** 2 hours

```python
# app/routers/local.py
"""
All /local/* endpoints operate exclusively on SQLite.
No server calls. No JWT needed (local machine = trusted).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from typing import Optional, List
from ..database import get_db
from ..models.user_data import Watchlist, PortfolioHolding, Transaction, UserPreference
from pydantic import BaseModel
from datetime import date

router = APIRouter(prefix="/local", tags=["local"])


# ── Watchlist ─────────────────────────────────────────────────────────────────

class WatchlistCreate(BaseModel):
    symbol: str
    asset_type: str          # 'STOCK' | 'FUND'
    display_name: Optional[str] = None
    notes: Optional[str] = None
    alert_above: Optional[float] = None
    alert_below: Optional[float] = None

class WatchlistRead(WatchlistCreate):
    id: int
    added_at: str
    class Config:
        from_attributes = True


@router.get("/watchlist", response_model=List[WatchlistRead])
async def get_watchlist(
    asset_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Watchlist)
    if asset_type:
        q = q.where(Watchlist.asset_type == asset_type.upper())
    result = await db.execute(q.order_by(Watchlist.added_at.desc()))
    return result.scalars().all()


@router.post("/watchlist", response_model=WatchlistRead, status_code=201)
async def add_to_watchlist(body: WatchlistCreate, db: AsyncSession = Depends(get_db)):
    item = Watchlist(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/watchlist/{item_id}", status_code=204)
async def remove_from_watchlist(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(Watchlist).where(Watchlist.id == item_id))
    if result.rowcount == 0:
        raise HTTPException(404, "Watchlist item not found")
    await db.commit()


# ── Portfolio Holdings ────────────────────────────────────────────────────────

class HoldingCreate(BaseModel):
    symbol: str
    asset_type: str
    quantity: float
    avg_cost: float
    buy_date: date
    folio_number: Optional[str] = None
    broker: Optional[str] = None
    notes: Optional[str] = None

class HoldingRead(HoldingCreate):
    id: int
    class Config:
        from_attributes = True


@router.get("/portfolio/holdings", response_model=List[HoldingRead])
async def get_holdings(
    asset_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(PortfolioHolding)
    if asset_type:
        q = q.where(PortfolioHolding.asset_type == asset_type.upper())
    result = await db.execute(q.order_by(PortfolioHolding.symbol))
    return result.scalars().all()


@router.post("/portfolio/holdings", response_model=HoldingRead, status_code=201)
async def add_holding(body: HoldingCreate, db: AsyncSession = Depends(get_db)):
    holding = PortfolioHolding(**body.model_dump())
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


@router.put("/portfolio/holdings/{holding_id}", response_model=HoldingRead)
async def update_holding(
    holding_id: int, body: HoldingCreate, db: AsyncSession = Depends(get_db)
):
    await db.execute(
        update(PortfolioHolding)
        .where(PortfolioHolding.id == holding_id)
        .values(**body.model_dump())
    )
    await db.commit()
    result = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
    )
    return result.scalar_one_or_none()


@router.delete("/portfolio/holdings/{holding_id}", status_code=204)
async def delete_holding(holding_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        delete(PortfolioHolding).where(PortfolioHolding.id == holding_id)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Holding not found")
    await db.commit()


# ── Transactions ──────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    symbol: str
    asset_type: str
    txn_type: str
    quantity: float
    price: float
    txn_date: date
    amount: Optional[float] = None
    brokerage: float = 0.0
    notes: Optional[str] = None

@router.get("/portfolio/transactions")
async def get_transactions(
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Transaction)
    if symbol:
        q = q.where(Transaction.symbol == symbol.upper())
    result = await db.execute(q.order_by(Transaction.txn_date.desc()))
    return result.scalars().all()


@router.post("/portfolio/transactions", status_code=201)
async def add_transaction(body: TransactionCreate, db: AsyncSession = Depends(get_db)):
    if body.amount is None:
        body = body.model_copy(update={"amount": body.quantity * body.price})
    txn = Transaction(**body.model_dump())
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


# ── Preferences ───────────────────────────────────────────────────────────────

@router.get("/preferences")
async def get_preferences(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserPreference))
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}


@router.put("/preferences/{key}")
async def set_preference(key: str, value: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    stmt = sqlite_insert(UserPreference).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"], set_={"value": value}
    )
    await db.execute(stmt)
    await db.commit()
    return {"key": key, "value": value}
```

---

## Task 4.9 — Proxy Router

**File:** `app/routers/proxy.py`
**Estimated time:** 2 hours

The proxy is the most important router. Every API call from the React UI that needs server data comes through here. It checks the local cache first, falls back to the server, and handles offline gracefully.

```python
# app/routers/proxy.py
"""
Proxy router: /proxy/* → Render server API.

Pattern for every endpoint:
  1. Build cache_key for this request
  2. Check cache — return if fresh
  3. Try server — on success, update cache, return data
  4. On OfflineError — return stale cache with offline flag, or 503

The response shapes returned are exactly what the server returns —
no transformation. The React UI already knows these shapes from
FundMasterListResponse, StockDetailResult, ScreenerResponse, etc.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..database import get_db
from ..services.http_client import ServerClient, OfflineError
from ..services.cache import get_cached, set_cached, make_cache_key
from ..config import settings

router = APIRouter(prefix="/proxy", tags=["proxy"])


def _offline_wrap(data: dict) -> dict:
    """Attach an offline flag to any cached response."""
    if isinstance(data, dict):
        return {**data, "_offline": True, "_stale": True}
    return data


# ── Mutual Funds ──────────────────────────────────────────────────────────────

@router.get("/funds")
async def proxy_fund_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Proxies GET /api/funds with all its query params.
    Caches the result keyed on the query string.
    """
    params = dict(request.query_params)
    cache_key = make_cache_key("funds:list", params)

    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/funds", params=params)
        await set_cached(db, cache_key, data, settings.CACHE_TTL_FUND_LIST)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline and no cached data available")


@router.get("/funds/{scheme_code}")
async def proxy_fund_detail(scheme_code: str, db: AsyncSession = Depends(get_db)):
    cache_key = f"funds:detail:{scheme_code}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/funds/{scheme_code}")
        await set_cached(db, cache_key, data, settings.CACHE_TTL_FUND_DETAIL)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/funds/{scheme_code}/nav")
async def proxy_fund_nav(
    scheme_code: str,
    limit: int = Query(default=365),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"funds:nav:{scheme_code}:{limit}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(
                f"/api/funds/{scheme_code}/nav",
                params={"limit": limit}
            )
        await set_cached(db, cache_key, data, settings.CACHE_TTL_FUND_NAV)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/funds/compare")
async def proxy_fund_compare(
    scheme_codes: str = Query(..., description="Comma-separated scheme codes"),
    db: AsyncSession = Depends(get_db),
):
    """
    Fund comparison — ComparisonResponse shape.
    Cached by the sorted set of scheme codes.
    """
    codes_sorted = ",".join(sorted(scheme_codes.split(",")))
    cache_key    = f"funds:compare:{codes_sorted}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(
                "/api/funds/compare",
                params={"scheme_codes": scheme_codes}
            )
        await set_cached(db, cache_key, data, settings.CACHE_TTL_FUND_DETAIL)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


# ── Benchmarks ────────────────────────────────────────────────────────────────

@router.get("/benchmarks")
async def proxy_benchmarks(request: Request, db: AsyncSession = Depends(get_db)):
    params    = dict(request.query_params)
    cache_key = make_cache_key("benchmarks:list", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/benchmarks", params=params)
        await set_cached(db, cache_key, data, settings.CACHE_TTL_BENCHMARKS)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


# ── Stocks ────────────────────────────────────────────────────────────────────

@router.get("/stocks")
async def proxy_stock_list(request: Request, db: AsyncSession = Depends(get_db)):
    params    = dict(request.query_params)
    cache_key = make_cache_key("stocks:list", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/stocks", params=params)
        await set_cached(db, cache_key, data, settings.CACHE_TTL_STOCK_LIST)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/stocks/screener")
async def proxy_screener(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Stock screener — ScreenerResponse shape.
    Short TTL (15 min) because screener results are filter-sensitive.
    Not cached by default if the filter set is too complex (hash collision risk is low).
    """
    params    = dict(request.query_params)
    cache_key = make_cache_key("stocks:screener", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/stocks/screener", params=params)
        await set_cached(db, cache_key, data, settings.CACHE_TTL_SCREENER)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/stocks/{symbol}")
async def proxy_stock_detail(symbol: str, db: AsyncSession = Depends(get_db)):
    cache_key = f"stocks:detail:{symbol.upper()}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/stocks/{symbol.upper()}")
        await set_cached(db, cache_key, data, settings.CACHE_TTL_STOCK_DETAIL)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


# ── ETL Status ────────────────────────────────────────────────────────────────

@router.get("/sync/status")
async def proxy_sync_status(db: AsyncSession = Depends(get_db)):
    """Pipeline run status — short TTL, always try server first."""
    cache_key = "etl:status"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/sync/status")
        await set_cached(db, cache_key, data, settings.CACHE_TTL_ETL_STATUS)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        return {"runs": [], "total": 0, "_offline": True}
```

---

## Task 4.10 — Agentic Layer

**File:** `app/routers/agent.py` + `app/services/agent_tools.py`
**Estimated time:** 2 hours

This phase builds the storage and tool infrastructure. The actual LLM call wiring (Anthropic API / LangGraph execution) is Phase 6. The routers and tool definitions are established here so Phase 6 only needs to add the LLM call itself.

```python
# app/routers/agent.py
"""
Agent session management endpoints.
Phase 4 builds storage + tool dispatch.
Phase 6 wires in the LLM call.

The session/message model is designed to store LangGraph state dicts
(matching ScoringStateSchema from the server schemas.py):
  - content_json stores the full state dict
  - content_text stores a human-readable summary for UI display
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List
from pydantic import BaseModel
from ..database import get_db
from ..models.agent import AgentSession, AgentMessage, AgentMemory

router = APIRouter(prefix="/agent", tags=["agent"])


class SessionCreate(BaseModel):
    title: Optional[str] = None
    context_type: str = "general"    # 'stock' | 'fund' | 'portfolio' | 'general'
    context_id: Optional[str] = None
    model_used: str = "claude-sonnet-4-6"


class MessageCreate(BaseModel):
    role: str               # 'user' | 'assistant' | 'tool' | 'state'
    content_text: Optional[str] = None
    content_json: Optional[dict] = None
    tool_name: Optional[str] = None


class ChatRequest(BaseModel):
    message: str            # User's plain text input


@router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    session = AgentSession(**body.model_dump())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, "title": session.title}


@router.get("/sessions")
async def list_sessions(
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.is_active == is_active)
        .order_by(AgentSession.last_msg_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.asc())
    )
    return result.scalars().all()


@router.post("/sessions/{session_id}/messages", status_code=201)
async def add_message(
    session_id: int, body: MessageCreate, db: AsyncSession = Depends(get_db)
):
    """
    Store a single message turn.
    Called by the Phase 6 agent runner after each LLM interaction.
    """
    # Get next sequence number
    result = await db.execute(
        select(AgentMessage.sequence_num)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.desc())
        .limit(1)
    )
    last_seq = result.scalar_one_or_none() or 0

    msg = AgentMessage(
        session_id=session_id,
        sequence_num=last_seq + 1,
        **body.model_dump(),
    )
    db.add(msg)

    # Update session last_msg_at
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(last_msg_at=AgentMessage.created_at)
    )
    await db.commit()
    return {"id": msg.id, "sequence_num": msg.sequence_num}


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: int, body: ChatRequest, db: AsyncSession = Depends(get_db)
):
    """
    Main chat endpoint. Phase 4: stores the user message, returns a placeholder.
    Phase 6: wires in the actual LLM call and tool execution.
    """
    # Store user message
    result = await db.execute(
        select(AgentMessage.sequence_num)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.desc()).limit(1)
    )
    last_seq = result.scalar_one_or_none() or 0

    user_msg = AgentMessage(
        session_id=session_id,
        sequence_num=last_seq + 1,
        role="user",
        content_text=body.message,
    )
    db.add(user_msg)
    await db.commit()

    # Phase 4: return placeholder
    # Phase 6: replace with actual LLM call
    return {
        "reply": "Agent not yet connected (Phase 6). Message stored.",
        "session_id": session_id,
    }


# ── Memory ────────────────────────────────────────────────────────────────────

@router.get("/memory")
async def get_memory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentMemory))
    rows = result.scalars().all()
    return {r.key: {"value": r.value, "confidence": r.confidence} for r in rows}


@router.put("/memory/{key}")
async def set_memory(
    key: str,
    value: str,
    confidence: str = "high",
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    stmt = sqlite_insert(AgentMemory).values(
        key=key, value=value, confidence=confidence, source="user_stated"
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"],
        set_={"value": value, "confidence": confidence}
    )
    await db.execute(stmt)
    await db.commit()
    return {"key": key, "value": value}
```

### `app/services/agent_tools.py`

```python
# app/services/agent_tools.py
"""
LangGraph-compatible tool definitions for the client agent.
Each tool fetches from the local proxy (which handles caching + JWT).

Tools are defined as async functions that return dicts.
Phase 6 wraps these in LangGraph ToolNode.
"""
import httpx
import json
from typing import Optional

CLIENT_BASE = "http://localhost:8001"


async def fetch_fund(scheme_code: str) -> dict:
    """
    Fetch fund detail + metrics from local proxy.
    Returns FundMasterRead shape (same as server response).
    """
    async with httpx.AsyncClient(base_url=CLIENT_BASE) as c:
        resp = await c.get(f"/proxy/funds/{scheme_code}")
        return resp.json()


async def fetch_stock(symbol: str) -> dict:
    """
    Fetch stock detail with technicals and fundamentals.
    Returns StockDetailResult shape.
    """
    async with httpx.AsyncClient(base_url=CLIENT_BASE) as c:
        resp = await c.get(f"/proxy/stocks/{symbol.upper()}")
        return resp.json()


async def compare_funds(scheme_codes: list[str]) -> dict:
    """
    Get side-by-side fund comparison.
    Returns ComparisonResponse shape.
    """
    codes_str = ",".join(scheme_codes[:5])   # Max 5 funds
    async with httpx.AsyncClient(base_url=CLIENT_BASE) as c:
        resp = await c.get(f"/proxy/funds/compare",
                           params={"scheme_codes": codes_str})
        return resp.json()


async def get_portfolio_summary(db) -> dict:
    """
    Read local holdings and enrich with cached prices.
    Returns a dict with holdings + current values.
    """
    async with httpx.AsyncClient(base_url=CLIENT_BASE) as c:
        holdings_resp = await c.get("/local/portfolio/holdings")
        holdings = holdings_resp.json()

    # Enrich each holding with latest cached price
    enriched = []
    async with httpx.AsyncClient(base_url=CLIENT_BASE) as c:
        for h in holdings:
            detail = {}
            if h["asset_type"] == "STOCK":
                r = await c.get(f"/proxy/stocks/{h['symbol']}")
                if r.status_code == 200:
                    detail = r.json()
                    h["current_price"]  = detail.get("latest_close")
                    h["pct_from_cost"]  = (
                        (h["current_price"] - h["avg_cost"]) / h["avg_cost"] * 100
                        if h.get("current_price") else None
                    )
            elif h["asset_type"] == "FUND":
                r = await c.get(f"/proxy/funds/{h['symbol']}")
                if r.status_code == 200:
                    detail = r.json()
                    h["current_price"] = detail.get("metrics", {}).get("current_nav")
            enriched.append(h)

    return {"holdings": enriched, "total_holdings": len(enriched)}


async def screen_stocks(filters: dict) -> dict:
    """
    Run the stock screener with given filters.
    Returns ScreenerResponse shape.
    """
    async with httpx.AsyncClient(base_url=CLIENT_BASE) as c:
        resp = await c.get("/proxy/stocks/screener", params=filters)
        return resp.json()


# Tool registry — used by Phase 6 LangGraph wiring
TOOL_REGISTRY = {
    "fetch_fund":          fetch_fund,
    "fetch_stock":         fetch_stock,
    "compare_funds":       compare_funds,
    "get_portfolio_summary": get_portfolio_summary,
    "screen_stocks":       screen_stocks,
}

# Tool definitions for LLM context (Anthropic tool_use format)
TOOL_DEFINITIONS = [
    {
        "name": "fetch_fund",
        "description": "Get full details, NAV, and performance metrics for a mutual fund",
        "input_schema": {
            "type": "object",
            "properties": {
                "scheme_code": {
                    "type": "string",
                    "description": "AMFI scheme code (e.g. '119598')"
                }
            },
            "required": ["scheme_code"],
        },
    },
    {
        "name": "fetch_stock",
        "description": "Get price, technical indicators, and fundamental ratios for a stock",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "NSE symbol (e.g. 'RELIANCE', 'INFY')"
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "compare_funds",
        "description": "Compare up to 5 mutual funds side by side on all metrics",
        "input_schema": {
            "type": "object",
            "properties": {
                "scheme_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of AMFI scheme codes to compare (max 5)",
                }
            },
            "required": ["scheme_codes"],
        },
    },
    {
        "name": "get_portfolio_summary",
        "description": "Summarise the user's current portfolio holdings with P&L",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "screen_stocks",
        "description": "Find stocks matching filter criteria like PE ratio, ROE, RSI etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": "Filter dict matching ScreenerFilterInput fields",
                }
            },
            "required": ["filters"],
        },
    },
]
```

---

## Task 4.11 — Client FastAPI Main

**File:** `app/main.py`
**Estimated time:** 1 hour

```python
# app/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text
from .database import engine, AsyncSessionLocal
from .config import settings
from .routers import auth, local, proxy, agent, status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 1. Run Alembic migrations (auto on every startup) ─────────────────────
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("SQLite migrations up to date")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

    # ── 2. Verify SQLite is writable ──────────────────────────────────────────
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info(f"SQLite DB ready: {settings.SQLITE_DB_PATH}")

    # ── 3. Register background jobs ───────────────────────────────────────────
    from .services.sync import ping_server, cleanup_expired

    async def _ping():
        async with AsyncSessionLocal() as db:
            online = await ping_server(db)
            logger.debug(f"Health ping: {'online' if online else 'offline'}")

    async def _cleanup():
        async with AsyncSessionLocal() as db:
            await cleanup_expired(db)

    scheduler.add_job(_ping,    "interval",
                      seconds=settings.HEALTH_PING_INTERVAL_S,    id="health_ping")
    scheduler.add_job(_cleanup, "interval",
                      seconds=settings.CACHE_CLEANUP_INTERVAL_S,  id="cache_cleanup")
    scheduler.start()

    # ── 4. Warm cache in background ───────────────────────────────────────────
    import asyncio
    async def _warm():
        await asyncio.sleep(2)   # Let the app finish starting first
        from .services.sync import run_startup_sync
        async with AsyncSessionLocal() as db:
            await run_startup_sync(db)
    asyncio.create_task(_warm())

    logger.info(f"Nivesh Client started — listening on port {settings.CLIENT_PORT}")
    yield

    scheduler.shutdown(wait=False)
    await engine.dispose()
    logger.info("Nivesh Client stopped")


app = FastAPI(
    title="Nivesh Client API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",    # Always available — local dev tool
)

# CORS: allow the React dev server (port 5173) and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(local.router)
app.include_router(proxy.router)
app.include_router(agent.router)

# Status endpoint (no router prefix)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db
from sqlalchemy import select, func
from .models.auth import ServerConfig
from .models.cache import CacheEntry

@app.get("/status", tags=["status"])
async def client_status(db: AsyncSession = Depends(get_db)):
    """
    Client health + connectivity summary.
    Consumed by the React UI to show the sync status bar.
    """
    # Server online status
    result = await db.execute(
        select(ServerConfig).where(ServerConfig.key.in_([
            "is_online", "last_connected_at", "server_version"
        ]))
    )
    config = {r.key: r.value for r in result.scalars().all()}

    # Cache stats
    count_result = await db.execute(select(func.count()).select_from(CacheEntry))
    cache_count = count_result.scalar() or 0

    return {
        "client_version": "0.1.0",
        "is_online": config.get("is_online") == "true",
        "last_connected_at": config.get("last_connected_at"),
        "server_url": settings.NIVESH_SERVER_URL,
        "cached_resources": cache_count,
        "db_path": settings.SQLITE_DB_PATH,
    }


@app.get("/health", tags=["status"])
async def client_health():
    return {"status": "ok", "port": settings.CLIENT_PORT}
```

---

## Task 4.12 — Install Script

**Estimated time:** 30 minutes

### `setup/setup.sh` (Linux/Mac)

```bash
#!/usr/bin/env bash
# setup.sh — Install Nivesh Client on Linux/Mac
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Nivesh Platform — Client Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Python 3.11+
PYTHON=$(which python3.11 2>/dev/null || which python3 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.11+ is required"
    exit 1
fi
echo "Using Python: $($PYTHON --version)"

# Create config directory
mkdir -p ~/.nivesh

# Install client package (editable so updates work with git pull)
echo "Installing nivesh-client..."
cd "$(dirname "$0")/.."
pip install -e ./nivesh-shared -q
pip install -e ./nivesh-client  -q

# Create .env if it doesn't exist
if [ ! -f ~/.nivesh/.env ]; then
    cp nivesh-client/.env.example ~/.nivesh/.env
    echo ""
    echo "⚠️  Created ~/.nivesh/.env — edit this file to set NIVESH_SERVER_URL"
fi

echo ""
echo "✓ Nivesh Client installed"
echo ""
echo "  Start with:"
echo "  uvicorn nivesh_client.app.main:app --port 8001"
```

### `setup/setup.bat` extension (Windows — extend existing)

```batch
:: Add to the existing setup.bat after Python detection:

echo Installing Nivesh Client dependencies...
pip install -e ..\nivesh-shared -q
pip install -e ..\nivesh-client  -q

if not exist "%USERPROFILE%\.nivesh\" mkdir "%USERPROFILE%\.nivesh"

if not exist "%USERPROFILE%\.nivesh\.env" (
    copy nivesh-client\.env.example "%USERPROFILE%\.nivesh\.env" >nul
    echo Created %USERPROFILE%\.nivesh\.env - edit to set NIVESH_SERVER_URL
)

echo.
echo Nivesh Client installed.
echo Start with: uvicorn nivesh_client.app.main:app --port 8001
```

---

## 17. Client SQLite Schema — Full DDL

Run this via Alembic (`alembic upgrade head`). Provided here as reference.

```sql
CREATE TABLE watchlist (
    id           INTEGER     PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT        NOT NULL,
    asset_type   TEXT        NOT NULL,
    display_name TEXT,
    notes        TEXT,
    alert_above  REAL,
    alert_below  REAL,
    added_at     TIMESTAMP   DEFAULT (datetime('now')),
    updated_at   TIMESTAMP   DEFAULT (datetime('now'))
);

CREATE TABLE portfolio_holdings (
    id           INTEGER     PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT        NOT NULL,
    asset_type   TEXT        NOT NULL,
    quantity     REAL        NOT NULL,
    avg_cost     REAL        NOT NULL,
    buy_date     DATE        NOT NULL,
    folio_number TEXT,
    broker       TEXT,
    notes        TEXT,
    created_at   TIMESTAMP   DEFAULT (datetime('now')),
    updated_at   TIMESTAMP   DEFAULT (datetime('now'))
);

CREATE TABLE transactions (
    id           INTEGER     PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT        NOT NULL,
    asset_type   TEXT        NOT NULL,
    txn_type     TEXT        NOT NULL,
    quantity     REAL        NOT NULL,
    price        REAL        NOT NULL,
    txn_date     DATE        NOT NULL,
    amount       REAL,
    brokerage    REAL        DEFAULT 0.0,
    notes        TEXT,
    created_at   TIMESTAMP   DEFAULT (datetime('now'))
);

CREATE TABLE user_preferences (
    key        TEXT        PRIMARY KEY,
    value      TEXT        NOT NULL,
    updated_at TIMESTAMP   DEFAULT (datetime('now'))
);

CREATE TABLE cache_entries (
    cache_key           TEXT        PRIMARY KEY,
    data_json           TEXT        NOT NULL,
    fetched_at          TIMESTAMP   NOT NULL DEFAULT (datetime('now')),
    ttl_seconds         INTEGER     NOT NULL DEFAULT 3600,
    server_generated_at TEXT
);

CREATE TABLE auth_tokens (
    id            INTEGER     PRIMARY KEY DEFAULT 1,
    access_token  TEXT        NOT NULL,
    refresh_token TEXT,
    expires_at    TIMESTAMP   NOT NULL,
    username      TEXT,
    created_at    TIMESTAMP   DEFAULT (datetime('now'))
);

CREATE TABLE server_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE agent_sessions (
    id           INTEGER     PRIMARY KEY AUTOINCREMENT,
    title        TEXT,
    context_type TEXT,
    context_id   TEXT,
    model_used   TEXT        DEFAULT 'claude-sonnet-4-6',
    is_active    INTEGER     DEFAULT 1,
    started_at   TIMESTAMP   DEFAULT (datetime('now')),
    last_msg_at  TIMESTAMP   DEFAULT (datetime('now'))
);

CREATE TABLE agent_messages (
    id           INTEGER     PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER     NOT NULL,
    sequence_num INTEGER     NOT NULL,
    role         TEXT        NOT NULL,
    content_text TEXT,
    content_json TEXT,       -- JSON stored as text in SQLite
    tool_name    TEXT,
    created_at   TIMESTAMP   DEFAULT (datetime('now'))
);
CREATE INDEX ix_agent_messages_session ON agent_messages (session_id, sequence_num);

CREATE TABLE agent_memory (
    key        TEXT        PRIMARY KEY,
    value      TEXT        NOT NULL,
    source     TEXT,
    confidence TEXT        DEFAULT 'high',
    updated_at TIMESTAMP   DEFAULT (datetime('now'))
);
```

---

## 18. Dependency Reference

```text
# requirements.txt — nivesh-client

# Core
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic-settings==2.2.1

# SQLite async
sqlalchemy[asyncio]==2.0.30
aiosqlite==0.20.0            # ← NEW (not in existing project)
alembic==1.13.1

# HTTP client (server calls)
httpx==0.27.0

# Scheduler (background health ping + cache cleanup)
apscheduler==3.10.4

# Agent layer — Phase 4 storage only; Phase 6 adds LLM calls
# anthropic==0.28.0          ← deferred to Phase 6

# Shared schemas
nivesh-shared @ ../nivesh-shared
```

**New packages vs existing project:**
- `aiosqlite` — the only genuinely new dependency. Everything else is already used in the server.
- `anthropic` is deferred to Phase 6 intentionally — Phase 4 builds the storage layer without requiring an API key.

---

## 19. Environment Variables

```bash
# ~/.nivesh/.env — client machine only

# Required: URL of the deployed Render server
NIVESH_SERVER_URL=https://nivesh-server.onrender.com

# Optional: override defaults
CLIENT_PORT=8001
SQLITE_DB_PATH=~/.nivesh/client.db
DEBUG=false

# Cache TTLs in seconds (optional — sensible defaults are in config.py)
# CACHE_TTL_FUND_LIST=3600
# CACHE_TTL_STOCK_DETAIL=3600
# CACHE_TTL_SCREENER=900
```

---

## 20. Definition of Done

Phase 4 is complete when all of the following are true:

- [ ] `uvicorn app.main:app --port 8001` starts without errors on a clean machine
- [ ] Alembic runs `upgrade head` automatically on startup and creates the SQLite DB
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `GET /status` returns `{"is_online": true/false, "cached_resources": N}`
- [ ] `POST /auth/login` with valid credentials stores token in SQLite and returns `access_token`
- [ ] `POST /auth/login` with wrong credentials returns 401
- [ ] `GET /proxy/funds` returns fund list (from server or stale cache)
- [ ] `GET /proxy/funds` with server offline returns stale cache with `_offline: true`
- [ ] `GET /proxy/stocks/{symbol}` returns stock detail
- [ ] `GET /proxy/stocks/screener?min_roe=15` returns screener results
- [ ] `POST /local/watchlist` adds an item — `GET /local/watchlist` returns it
- [ ] `POST /local/portfolio/holdings` adds a holding — `GET /local/portfolio/holdings` returns it
- [ ] `POST /local/portfolio/transactions` records a transaction
- [ ] `GET /local/preferences` returns stored preferences
- [ ] `POST /agent/sessions` creates a session — returns `session_id`
- [ ] `POST /agent/sessions/{id}/chat` stores the user message
- [ ] `GET /agent/sessions/{id}/messages` returns the message history
- [ ] `GET /agent/memory` returns stored memory facts
- [ ] APScheduler health ping runs every 60s (visible in logs)
- [ ] Setup script runs cleanly on Windows (`setup.bat`) and Linux/Mac (`setup.sh`)

---

## 21. Execution Order — Day by Day

```
Day 1 (4h)
  Task 4.1  Project scaffold, config.py, .env.example      1h
  Task 4.2  database.py + all SQLite models                2h
  Task 4.3  Alembic setup for SQLite + auto-migrate        1h

Day 2 (4h)
  Task 4.4  ServerClient (http_client.py)                  2h
  Task 4.5  JWT auth router (login, logout)                1.5h
  Task 4.6  Cache layer (cache.py service)                 0.5h

Day 3 (4h)
  Task 4.7  Sync engine (sync.py)                          1h
  Task 4.8  Portfolio + watchlist CRUD (local.py)          2h
  Task 4.9  Proxy router (proxy.py)                        1h

Day 4 (3h)
  Task 4.10 Agent storage + tools (agent.py + agent_tools) 2h
  Task 4.11 main.py + scheduler wiring                     0.5h
  Task 4.12 Install scripts (setup.sh + setup.bat update)  0.5h

Day 5 (2h)
  Full smoke test against the live Render server
  Fix any issues, confirm Definition of Done checklist
```

**Total: 4–5 working days**

---

*Phase 4 Implementation Plan · Nivesh Platform · May 2026*
*Previous: Phase 3 — Ingestion Pipeline*
*Next: Phase 5 — Client JWT Auth + Sync Engine (delta sync, offline resilience)*
