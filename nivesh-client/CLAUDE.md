# nivesh-client — Local Machine Application

## Purpose

Local application that runs on the user's machine. Thin FastAPI backend serving a React UI. Stores only user-private data (portfolio, watchlist, transactions) and a TTL cache of server responses. Runs an agentic layer locally. Authenticates against `nivesh-server` via JWT.

## Stack

- **FastAPI** + **Uvicorn** — local API on port 8001
- **SQLAlchemy (async)** + **aiosqlite** — ORM → SQLite
- **Alembic** — SQLite schema migrations (auto-run on startup)
- **APScheduler** — background sync scheduler (health_ping, cache_cleanup, token_refresh, portfolio_sync)
- **pytz** — IST-aware APScheduler cron triggers (portfolio_sync market-hours job)
- **httpx** + **tenacity** — async HTTP client with retry for server calls
- **React** (Vite) — UI in `frontend/src/`
- **ChatGroq** (`langchain-groq`) + **LangGraph** — agentic layer: supervisor + 3 specialist ReAct agents

## Directory Structure

```
nivesh-client/
├── app/
│   ├── main.py           ← FastAPI :8001, lifespan (Alembic upgrade + scheduler)
│   ├── config.py         ← NIVESH_SERVER_URL, CLIENT_PORT, SQLITE_DB_PATH
│   ├── database.py       ← SQLAlchemy → SQLite (~/.nivesh/nivesh_client.db)
│   ├── models/
│   │   ├── user_data.py  ← watchlist, portfolio_holdings, transactions
│   │   ├── cache.py      ← cache_* tables + sync_state
│   │   ├── agent.py      ← agent_sessions, messages, tool_calls, memory
│   │   └── auth.py       ← auth_tokens, server_config
│   ├── routers/
│   │   ├── portfolio.py  ← CRUD for local holdings/watchlist
│   │   ├── proxy.py      ← Pass-through to server (injects JWT)
│   │   ├── agent.py      ← Agent session management
│   │   └── auth.py       ← Login flow, token refresh
│   ├── sync/
│   │   ├── engine.py     ← Sync orchestrator
│   │   ├── scheduler.py  ← APScheduler background jobs
│   │   ├── http_client.py← httpx client, JWT injection, auto-refresh, retry
│   │   └── delta.py      ← Staleness detection, from_date computation
│   └── agent/
│       ├── runner.py     ← run_turn(): LangGraph graph invocation + SQLite persistence
│       ├── supervisor.py ← LangGraph StateGraph: supervisor → stock/fund/portfolio agents
│       ├── agents.py     ← build_stock/fund/portfolio_agent() ReAct agents
│       ├── tools.py      ← 7 @tool async functions (STOCK_TOOLS, FUND_TOOLS, PORTFOLIO_TOOLS)
│       └── memory.py     ← Read/write agent_memory table
├── frontend/             ← React UI (copied from original project)
│   └── src/
├── alembic/              ← SQLite migrations
└── alembic.ini
```

## SQLite Database

- Location: `~/.nivesh/nivesh_client.db` (outside project dir — survives reinstalls)
- WAL mode enabled for concurrent reads
- Alembic `upgrade head` runs automatically on every startup
- **NEVER** commit `.db` files to git

## Environment Variables (`~/.nivesh/.env`)

| Variable | Value |
|---|---|
| `NIVESH_SERVER_URL` | `https://nivesh-server.onrender.com` |
| `CLIENT_PORT` | `8001` |
| `SQLITE_DB_PATH` | `~/.nivesh/nivesh_client.db` |
| `GROQ_API_KEY` | `gsk_...` — required for agentic chat (`/agent/sessions/<id>/chat`) |

## JWT Auth Pattern

The React UI **never** handles JWT tokens. Flow:
1. UI calls `POST /auth/login` → client FastAPI
2. Client FastAPI forwards to server, stores tokens in SQLite
3. All subsequent UI calls go to `/proxy/*` → client injects `Authorization: Bearer` header
4. Auto-refresh on 401 is transparent to the UI

## Sync / Cache Rules

- TTL cache: `cache_stock_summary` (1h), `cache_fund_metrics` (24h), `cache_market_snapshot` (30m)
- `sync_state` table tracks `last_synced_at` per resource key
- All server fetches use `?from_date=<last_synced_at>` for delta sync
- Offline mode: serve stale cache + `offline: true` flag in response meta

## Running Locally

```bash
cd nivesh-client
pip install -r requirements.txt
cp .env.example .env  # set NIVESH_SERVER_URL
uvicorn app.main:app --port 8001 --reload
# UI available at http://localhost:8001
```

## Frontend Dev

```bash
cd nivesh-client/frontend
npm install
npm run dev  # proxied to port 8001
```
