# Nivesh Platform — Server/Client Architecture Split
## High-Level Design Document · v1.0

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Server — Cloud Application](#3-server--cloud-application)
   - 3.1 [Stock Fundamentals](#31-stock-fundamentals)
   - 3.2 [Stock Technical Data](#32-stock-technical-data)
   - 3.3 [Stock Ratios](#33-stock-ratios)
   - 3.4 [Stock Historical Data](#34-stock-historical-data)
   - 3.5 [Mutual Fund Historical Data](#35-mutual-fund-historical-data)
   - 3.6 [Mutual Fund Ratios & Metrics](#36-mutual-fund-ratios--metrics)
   - 3.7 [Daily Market Data](#37-daily-market-data)
4. [Client — Local Application](#4-client--local-application)
   - 4.1 [Local SQLite Database](#41-local-sqlite-database)
   - 4.2 [Local Cache (TTL-aware)](#42-local-cache-ttl-aware)
   - 4.3 [Agentic Features](#43-agentic-features)
   - 4.4 [JWT Authentication](#44-jwt-authentication)
5. [API Contract](#5-api-contract)
   - 5.1 [Stocks API](#51-stocks-api)
   - 5.2 [Mutual Funds API](#52-mutual-funds-api)
   - 5.3 [Market Daily API](#53-market-daily-api)
   - 5.4 [Auth & System API](#54-auth--system-api)
   - 5.5 [Response Envelope](#55-response-envelope)
6. [Data Ownership Map](#6-data-ownership-map)
7. [Folder Structure](#7-folder-structure)
8. [Migration Phases](#8-migration-phases)
9. [Key Architectural Decisions](#9-key-architectural-decisions)

---

## 1. Overview

Nivesh Platform is split into two independently deployable applications sharing a common API contract:

- **`nivesh-server`** — Cloud-hosted FastAPI application. Owns all canonical financial data (stocks, mutual funds, market data). Performs all computation (technical indicators, ratios, fund metrics). Exposes a versioned REST API.
- **`nivesh-client`** — Local machine application. Thin FastAPI backend serving a React UI. Stores only user-private data and a TTL cache of server responses. Runs an agentic layer locally. Authenticates against the server via JWT.
- **`nivesh-shared`** — Pip-installable package containing shared Pydantic response schemas. Both server and client import from this. This is the API contract artifact.

**Core principle:** The server is the single source of truth for all market data. The client never computes analytics, never connects directly to the cloud PostgreSQL instance, and never stores raw time-series data permanently.

---

## 2. System Architecture

```
┌─────────────────────────────────────┐         ┌──────────────────────────────────────────┐
│         CLIENT (Local Machine)      │         │          SERVER (Cloud)                  │
│                                     │         │                                          │
│  ┌──────────────────────────────┐   │         │  ┌────────────────────────────────────┐  │
│  │       React UI (Vite)        │   │         │  │     FastAPI  :8000  (Docker)       │  │
│  │   Califino dark-mode theme   │   │         │  │   Versioned REST  ·  OpenAPI spec  │  │
│  └──────────────┬───────────────┘   │         │  └──────────────────┬─────────────────┘  │
│                 │ localhost         │         │                     │                    │
│  ┌──────────────▼───────────────┐   │  HTTPS  │  ┌──────────────────▼─────────────────┐  │
│  │    Client FastAPI  :8001     │◄──┼─────────┼──►   Analytics Engine                │  │
│  │  Portfolio · Watchlist · UI  │   │  JWT    │  │   pandas-ta · scipy · pandas       │  │
│  └──────────────┬───────────────┘   │         │  └──────────────────┬─────────────────┘  │
│                 │                   │         │                     │                    │
│  ┌──────────────▼───────────────┐   │         │  ┌──────────────────▼─────────────────┐  │
│  │       Sync Engine            │   │         │  │     Ingestion Pipeline             │  │
│  │  httpx · APScheduler         │   │         │  │  APScheduler · AMFI · NSE · BSE    │  │
│  │  Staleness detection         │   │         │  └──────────────────┬─────────────────┘  │
│  │  Delta fetch (?from_date=)   │   │         │                     │                    │
│  └──────────────┬───────────────┘   │         │  ┌──────────────────▼─────────────────┐  │
│                 │                   │         │  │     PostgreSQL 16 (TimescaleDB)    │  │
│  ┌──────────────▼───────────────┐   │         │  │  Stocks · MF · Benchmarks · Daily  │  │
│  │      SQLite (Local)          │   │         │  └────────────────────────────────────┘  │
│  │  Watchlist · Portfolio       │   │         │                                          │
│  │  Agent memory · Cache · JWT  │   │         └──────────────────────────────────────────┘
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

---

## 3. Server — Cloud Application

The server owns **all canonical financial data** and **all computation**. Nothing on this list is exposed as raw DB access — everything flows through the versioned REST API.

### 3.1 Stock Fundamentals

**Description:** Balance sheet, P&L, cash flow, management holding data, and company profile for all NSE/BSE listed companies.

**PostgreSQL Tables:**

| Table | Description |
|---|---|
| `company_master` | NSE/BSE symbol, ISIN, sector, industry, market cap bucket, listing date |
| `fundamental_snapshots` | JSONB per quarter: revenue, EBITDA, PAT, EPS, book value, face value |
| `financial_statements` | P&L / Balance Sheet / Cash Flow — structured rows with JSONB detail column |
| `management_data` | Promoter holding %, pledged %, DII/FII/retail split per quarter |

**Ingestion strategy:** Yahoo Finance / NSE API / Screener scrape — quarterly trigger via APScheduler. Stored as JSONB to accommodate varying financial statement structures across companies and reporting periods.

---

### 3.2 Stock Technical Data

**Description:** OHLCV daily data, pre-computed technical indicators, and pattern signals for all tracked symbols.

**PostgreSQL Tables:**

| Table | Description |
|---|---|
| `stock_ohlcv_daily` | Date, open, high, low, close, volume, delivery_pct — composite PK `(symbol, date)` |
| `stock_technical_indicators` | Pre-computed daily: RSI-14, MACD (12/26/9), Bollinger Bands, EMA20/50/200, ATR, VWAP |
| `pattern_signals` | Detected patterns: golden cross, death cross, breakout, support/resistance flags with confidence score |

**Ingestion strategy:** NSE bhavcopy downloaded daily at 18:30 IST via APScheduler. `pandas-ta` runs after each bhavcopy load to populate `stock_technical_indicators`. Pattern detection via `scipy`. Client **never runs pandas-ta** — it only reads pre-computed rows.

---

### 3.3 Stock Ratios

**Description:** Valuation and efficiency ratios computed server-side nightly. Includes rolling history for percentile ranking.

**PostgreSQL Tables:**

| Table | Description |
|---|---|
| `stock_ratios` | Computed daily: PE, PB, PS, EV/EBITDA, ROE, ROCE, D/E, current ratio, dividend yield |
| `ratio_history` | Rolling ratio snapshots — enables percentile ranking vs 5Y history within sector |

**Ingestion strategy:** Derived from `fundamental_snapshots` + `stock_ohlcv_daily`. Recomputed nightly as part of the EOD pipeline. Market-cap weighted sector averages also stored here for relative valuation context.

---

### 3.4 Stock Historical Data

**Description:** Full OHLCV history (10Y+) at daily, weekly, and monthly granularity. Corporate actions required for adjusted price series.

**PostgreSQL Tables:**

| Table | Description |
|---|---|
| `stock_ohlcv_daily` | Same table as §3.2 — partitioned by year for query efficiency on long date ranges |
| `stock_ohlcv_weekly` | Aggregated weekly OHLCV — derived from daily via materialized view |
| `stock_ohlcv_monthly` | Aggregated monthly OHLCV — derived from daily via materialized view |
| `corporate_actions` | Splits, bonuses, dividends with ex-date — required for adjusted close computation |
| `adjusted_close` | Split/dividend-adjusted close price series — the correct series for returns calculation |

**Ingestion strategy:** Initial bulk load from NSE historical bhavcopy archive files. Incremental daily load thereafter. `adjusted_close` recomputed whenever a new `corporate_actions` entry is added for a symbol.

> **Important:** All returns calculations (absolute, rolling, CAGR) use `adjusted_close`, not raw close. Raw close is stored for reference only.

---

### 3.5 Mutual Fund Historical Data

**Description:** NAV history for all AMFI schemes. These are the existing tables from the current platform, unchanged.

**PostgreSQL Tables:**

| Table | Description |
|---|---|
| `fund_master` | Existing: scheme code, name, AMC, category, ISIN, plan type |
| `fund_nav_history` | Existing: `(scheme_code, nav_date)` composite PK, daily NAV value |
| `benchmark_master` | Existing: index definitions, exchange tickers |
| `benchmark_nav_history` | Existing: `(benchmark_code, nav_date)` composite PK, index price history |

**Ingestion strategy:** `mftool` / AMFI `NAVAll.txt` — daily at 22:00 IST after AMFI publishes. Existing `sync.py` promoted to a proper APScheduler job rather than a manual script.

---

### 3.6 Mutual Fund Ratios & Metrics

**Description:** Risk-adjusted performance metrics for all funds. Existing `fund_metrics` table extended with category percentiles and rolling return series.

**PostgreSQL Tables:**

| Table | Description |
|---|---|
| `fund_metrics` | Existing: Sharpe, Sortino, Std Dev, Max Drawdown, Alpha, Beta, Tracking Error, Info Ratio, capture ratios |
| `fund_category_percentiles` | New: percentile rank within fund category for each metric (e.g. Sortino in top 15% of Large Cap funds) |
| `fund_rolling_returns` | New: 1Y/3Y/5Y rolling return series per scheme — enables rolling return charts without client computation |

**Ingestion strategy:** Recomputed nightly after NAV sync completes. Existing `recompute_funds_metrics.py` promoted to a scheduled APScheduler job. `fund_category_percentiles` computed as a second pass after all fund metrics are updated.

---

### 3.7 Daily Market Data

**Description:** Market-wide daily snapshot: index levels, sector performance, FII/DII flows, top movers. Pre-aggregated for fast client home screen load.

**PostgreSQL Tables:**

| Table | Description |
|---|---|
| `market_daily_snapshot` | Nifty50/Sensex/BankNifty/Nifty500 close, advance/decline ratio, total NSE volume |
| `sector_performance_daily` | Sector-wise daily returns: IT, BFSI, Pharma, Auto, FMCG, Metal, Realty, etc. |
| `fii_dii_flows` | Daily FII/DII buy/sell values from NSE — JSONB for flexibility across reporting format changes |
| `top_movers_daily` | Top 10 gainers + losers by price % and by volume — pre-computed so client home loads in one API call |
| `sync_jobs` | Existing: tracks all ingestion pipeline runs with status (`RUNNING`/`COMPLETED`/`FAILED`) and error messages |

**Ingestion strategy:** NSE daily bhavcopy + index snapshots compiled at EOD ~18:30 IST. FII/DII flows from NSE press release at ~19:00 IST. `top_movers_daily` generated as the final step of the EOD pipeline.

---

## 4. Client — Local Application

The client owns **user-private data** and a **TTL cache** of server responses. It performs no analytics. It runs the agentic layer locally with all agent data staying on-device.

### 4.1 Local SQLite Database

**Description:** Zero-install embedded database. All user-private data. Never synced to server under any circumstance.

**SQLite Tables:**

| Table | Description |
|---|---|
| `watchlist` | User's tracked stocks + funds with personal notes, target prices, alert thresholds |
| `portfolio_holdings` | Holdings: symbol, qty, avg_cost, buy_date — local ledger, never leaves device |
| `transactions` | Buy/sell/dividend/split adjustment history |
| `user_preferences` | Theme, default benchmark, chart intervals, layout config, notification settings |
| `alert_definitions` | Price alerts, ratio threshold alerts, RSI/MACD signal alerts per symbol |

**Migration tool:** Alembic with SQLite dialect. Schema migrations ship with client releases. On first run, Alembic upgrades the local DB automatically.

---

### 4.2 Local Cache (TTL-aware)

**Description:** Locally stored copies of server API responses with expiry timestamps. Drives offline mode. Cache is expendable — it can always be rebuilt from the server.

**SQLite Tables:**

| Table | TTL | Description |
|---|---|---|
| `cache_stock_summary` | 1 hour | Stock quote + today's technicals per symbol |
| `cache_fund_metrics` | 24 hours | Fund Sharpe/Sortino/Alpha/Beta per scheme code |
| `cache_market_snapshot` | 30 minutes | Index levels, sector returns, top movers |
| `cache_ohlcv` | 24 hours | Last 1 year OHLCV per symbol — for charting without re-fetching |
| `sync_state` | — | Per-symbol `last_synced_at` timestamp — drives delta fetch `?from_date=` parameter |

**Offline behaviour:** If the server is unreachable, the client serves stale cache and shows a `Last synced: X hours ago` banner in the UI. No hard dependency on connectivity for viewing previously loaded data.

---

### 4.3 Agentic Features

**Description:** Local LLM agent for financial research and portfolio analysis. All agent data (sessions, memory, tool call logs, saved analyses) is stored locally. No agent data is transmitted to the server.

**SQLite Tables:**

| Table | Description |
|---|---|
| `agent_sessions` | Session ID, start time, context type (stock/fund/portfolio/market), model used |
| `agent_messages` | Full conversation history per session — role, content, timestamp |
| `agent_tool_calls` | Tool invocation log: which server API endpoint called, params sent, response summary |
| `agent_memory` | Persistent facts the agent learns about user preferences, risk tolerance, watched sectors |
| `saved_analyses` | User-saved agent outputs: stock deep-dives, fund comparisons, portfolio reports as Markdown |

**Agent tools available locally:**
- `fetch_stock(symbol)` — calls client proxy → server API, caches result
- `compare_funds(codes[])` — parallel fetch for up to 5 schemes
- `get_portfolio_summary()` — reads local `portfolio_holdings`, enriches with cached prices
- `screen_stocks(filters)` — applies filter criteria against cached stock summaries
- `get_market_context()` — returns cached market snapshot + sector returns

---

### 4.4 JWT Authentication

**Description:** Client authenticates against the server once. Tokens stored in local SQLite. All subsequent server API calls automatically include the bearer token. Token refresh is transparent.

**SQLite Tables:**

| Table | Description |
|---|---|
| `auth_tokens` | `access_token` (15 min expiry), `refresh_token` (7 day expiry), `expires_at` |
| `server_config` | `NIVESH_SERVER_URL`, `last_connected_at`, `server_version` |

**JWT Flow:**

```
User login (username + password)
        │
        ▼
POST /api/v1/auth/login  →  { access_token, refresh_token, expires_in }
        │
        ▼
Stored in SQLite auth_tokens table (never in browser localStorage)
        │
        ▼
Every server API call:  Authorization: Bearer <access_token>
        │
        ├─ 401 Unauthorized → httpx middleware auto-calls POST /api/v1/auth/refresh
        │                      → stores new access_token → retries original request
        │
        └─ refresh_token expired → redirect user to login screen
```

**Token storage:** Stored in SQLite on the local filesystem — not in browser memory, not in environment variables. The client FastAPI process reads tokens from SQLite and injects the `Authorization` header before proxying requests to the server.

---

## 5. API Contract

All endpoints are **read-only** (`GET`) except authentication. The server never accepts financial data writes from clients — only the server's own ingestion pipeline writes to the server DB.

Base URL: `https://api.nivesh.app`  
Auth header: `Authorization: Bearer <access_token>`  
API version prefix: `/api/v1/`

---

### 5.1 Stocks API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/stocks` | Paginated stock universe with sector, market cap bucket, latest close price |
| `GET` | `/api/v1/stocks/{symbol}` | Full stock detail: company profile + latest ratios + today's technicals |
| `GET` | `/api/v1/stocks/{symbol}/ohlcv` | OHLCV history — supports `?from_date=` for delta sync, `?interval=daily\|weekly\|monthly` |
| `GET` | `/api/v1/stocks/{symbol}/technicals` | Latest computed indicators: RSI, MACD, Bollinger Bands, EMA20/50/200, ATR |
| `GET` | `/api/v1/stocks/{symbol}/fundamentals` | Latest financial statements + computed ratios |
| `GET` | `/api/v1/stocks/{symbol}/ratios/history` | Rolling PE/PB/ROE history — for percentile chart rendering |
| `GET` | `/api/v1/stocks/{symbol}/patterns` | Active pattern signals with confidence scores |

---

### 5.2 Mutual Funds API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/funds` | Paginated fund list with category, AMC, latest NAV |
| `GET` | `/api/v1/funds/{scheme_code}` | Fund detail + latest metrics |
| `GET` | `/api/v1/funds/{scheme_code}/nav` | NAV history — supports `?from_date=` for delta sync |
| `GET` | `/api/v1/funds/{scheme_code}/metrics` | Sharpe, Sortino, Alpha, Beta, Max Drawdown, capture ratios, category percentile |
| `GET` | `/api/v1/funds/{scheme_code}/rolling-returns` | 1Y/3Y/5Y rolling return series |
| `GET` | `/api/v1/funds/compare` | Side-by-side metrics for up to 5 schemes — `?codes=XXXXX,YYYYY,ZZZZZ` |

---

### 5.3 Market Daily API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/market/snapshot` | Today's index levels (Nifty50/Sensex/BankNifty), advance/decline ratio, total volume |
| `GET` | `/api/v1/market/sectors` | Sector returns for today + 1W + 1M |
| `GET` | `/api/v1/market/movers` | Top 10 gainers + losers by price % and by delivery volume |
| `GET` | `/api/v1/market/fii-dii` | FII/DII daily flow data — supports `?from_date=` for historical range |
| `GET` | `/api/v1/benchmarks/{code}/nav` | Benchmark index price history |

---

### 5.4 Auth & System API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/login` | `{ username, password }` → `{ access_token, refresh_token, expires_in }` |
| `POST` | `/api/v1/auth/refresh` | `{ refresh_token }` → `{ access_token, expires_in }` |
| `POST` | `/api/v1/auth/logout` | Invalidates refresh token server-side (token blocklist) |
| `GET` | `/api/v1/sync/status` | Last run time + status for each ingestion pipeline (bhavcopy, AMFI, fundamentals, FII/DII) |
| `GET` | `/health` | `{ status, db_status, version, uptime }` — polled by client every 60s for connectivity check |

---

### 5.5 Response Envelope

All list endpoints return a standard envelope:

```json
{
  "data": [ ... ],
  "meta": {
    "total": 500,
    "page": 1,
    "page_size": 50,
    "generated_at": "2026-05-13T18:30:00+05:30",
    "from_date": "2026-01-01"
  }
}
```

- `generated_at` — ISO 8601 timestamp of when this data was computed on the server. The client stores this in `sync_state.last_synced_at` and uses it for the next delta fetch.
- `from_date` — echoed back when a `?from_date=` parameter was sent, for logging/debugging.
- Pagination uses **cursor-based** approach for time-series data (not `OFFSET`) to avoid performance degradation on large date ranges.

---

## 6. Data Ownership Map

| Table | Owner | Rationale |
|---|---|---|
| `company_master` | Server | Canonical reference data — NSE/BSE sourced |
| `fundamental_snapshots` | Server | Quarterly financial data — server fetches and stores |
| `financial_statements` | Server | Raw P&L/BS/CF — server computes ratios from these |
| `management_data` | Server | Promoter/FII/DII holding — regulatory source data |
| `stock_ohlcv_daily` | Server | Market data — incremental daily from NSE bhavcopy |
| `stock_technical_indicators` | Server | Server-computed via pandas-ta — read-only for client |
| `pattern_signals` | Server | Server-computed via scipy — read-only for client |
| `stock_ratios` | Server | Derived from ohlcv + fundamentals — server computes nightly |
| `ratio_history` | Server | Rolling ratio snapshots for percentile ranking |
| `corporate_actions` | Server | NSE source data — affects adjusted price series |
| `adjusted_close` | Server | Derived series — server computes on corporate action events |
| `fund_master` | Server | AMFI source data — existing table |
| `fund_nav_history` | Server | AMFI daily NAV — existing table |
| `benchmark_master` | Server | Index definitions — existing table |
| `benchmark_nav_history` | Server | Index price history — existing table |
| `fund_metrics` | Server | Sharpe/Sortino/Alpha etc. — server computes nightly |
| `fund_category_percentiles` | Server | Category ranking — derived from fund_metrics |
| `fund_rolling_returns` | Server | Rolling return series — server pre-computes |
| `market_daily_snapshot` | Server | EOD aggregation — server computes |
| `sector_performance_daily` | Server | EOD sector rollup — server computes |
| `fii_dii_flows` | Server | NSE press release data — server ingests |
| `top_movers_daily` | Server | Pre-aggregated for fast home screen load |
| `sync_jobs` | Server | Ingestion pipeline state — existing table |
| `watchlist` | Client | User-private — never leaves device |
| `portfolio_holdings` | Client | User-private — never leaves device |
| `transactions` | Client | User-private — never leaves device |
| `user_preferences` | Client | User-private — never leaves device |
| `alert_definitions` | Client | User-private — never leaves device |
| `cache_stock_summary` | Client | TTL cache — expendable, rebuilt from server |
| `cache_fund_metrics` | Client | TTL cache — expendable, rebuilt from server |
| `cache_market_snapshot` | Client | TTL cache — expendable, rebuilt from server |
| `cache_ohlcv` | Client | TTL cache — expendable, rebuilt from server |
| `sync_state` | Client | Delta sync bookmarks — per-symbol `last_synced_at` |
| `agent_sessions` | Client | Agentic — local only |
| `agent_messages` | Client | Agentic — local only |
| `agent_tool_calls` | Client | Agentic — local only |
| `agent_memory` | Client | Agentic — local only |
| `saved_analyses` | Client | Agentic — local only |
| `auth_tokens` | Client | JWT storage — local SQLite |
| `server_config` | Client | Server URL + connectivity state |

---

## 7. Folder Structure

```
nivesh-platform/                        ← Monorepo root
│
├── nivesh-server/                      ← Cloud-deployed FastAPI app
│   ├── app/
│   │   ├── main.py                     ← FastAPI entry point
│   │   ├── config.py                   ← Pydantic Settings (env vars)
│   │   ├── database.py                 ← Async SQLAlchemy → PostgreSQL
│   │   ├── security.py                 ← JWT, bcrypt (existing)
│   │   ├── models/
│   │   │   ├── stocks.py               ← company_master, ohlcv, technicals, ratios
│   │   │   ├── fundamentals.py         ← financial_statements, snapshots, management
│   │   │   ├── funds.py                ← fund_master, nav_history, metrics (existing)
│   │   │   ├── market.py               ← market_daily_snapshot, sector, fii_dii, movers
│   │   │   └── system.py               ← sync_jobs
│   │   ├── routers/
│   │   │   ├── stocks.py
│   │   │   ├── funds.py
│   │   │   ├── market.py
│   │   │   └── auth.py
│   │   ├── analytics/
│   │   │   ├── technical.py            ← pandas-ta indicator computation
│   │   │   ├── ratios.py               ← PE/PB/ROE/ROCE computation
│   │   │   ├── fund_metrics.py         ← Sharpe/Sortino/Alpha (existing analytics.py)
│   │   │   └── patterns.py             ← scipy-based pattern detection
│   │   └── ingestion/
│   │       ├── scheduler.py            ← APScheduler job definitions + cron config
│   │       ├── nse_bhavcopy.py         ← Daily EOD stock OHLCV
│   │       ├── amfi_nav.py             ← MF NAV (existing sync.py promoted)
│   │       ├── fundamentals.py         ← Quarterly fundamental data fetch
│   │       └── fii_dii.py              ← FII/DII daily flows from NSE
│   ├── scripts/                        ← One-time seed scripts (existing)
│   ├── alembic/                        ← Server PostgreSQL migrations
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── nivesh-client/                      ← Local install — user's machine
│   ├── app/
│   │   ├── main.py                     ← FastAPI :8001
│   │   ├── config.py                   ← NIVESH_SERVER_URL, SQLite path
│   │   ├── database.py                 ← SQLAlchemy → SQLite
│   │   ├── models/
│   │   │   ├── user_data.py            ← watchlist, portfolio, transactions, alerts
│   │   │   ├── cache.py                ← cache_* tables + sync_state
│   │   │   ├── agent.py                ← agent_sessions, messages, memory, tool_calls
│   │   │   └── auth.py                 ← auth_tokens, server_config
│   │   ├── routers/
│   │   │   ├── portfolio.py            ← CRUD for local holdings/watchlist
│   │   │   ├── agent.py                ← Agent session management
│   │   │   ├── proxy.py                ← Pass-through to server (injects JWT header)
│   │   │   └── auth.py                 ← Login flow, token refresh
│   │   ├── sync/
│   │   │   ├── engine.py               ← Core sync orchestrator
│   │   │   ├── scheduler.py            ← APScheduler — background refresh jobs
│   │   │   ├── http_client.py          ← httpx async client, retry, exponential backoff
│   │   │   └── delta.py                ← Staleness detection, from_date computation
│   │   └── agent/
│   │       ├── runner.py               ← LLM agent execution loop
│   │       ├── tools.py                ← Agent tools: fetch_stock, compare_funds, etc.
│   │       └── memory.py               ← Read/write agent_memory table
│   ├── frontend/                       ← React UI (existing, adapted)
│   │   └── src/
│   ├── alembic/                        ← Client SQLite migrations
│   ├── .env.example                    ← NIVESH_SERVER_URL=https://api.nivesh.app
│   └── requirements.txt
│
└── nivesh-shared/                      ← Pip-installable package
    ├── schemas/
    │   ├── stocks.py                   ← StockSummary, StockDetail, OHLCVRow, TechnicalsRow
    │   ├── funds.py                    ← FundSummary, FundMetrics, NAVRow, RollingReturns
    │   └── market.py                  ← MarketSnapshot, SectorReturn, FIIDIIFlow, MoverRow
    └── pyproject.toml
```

---

## 8. Migration Phases

| Phase | Title | Duration | Risk |
|---|---|---|---|
| P0 | Repo Restructure | 1–2 days | Low |
| P1 | Server: Data Ownership Boundary | 3–5 days | Low |
| P2 | Server: API Contract Design | 3–4 days | Medium |
| P3 | Client: Local DB Design | 3–4 days | Medium |
| P4 | Client: Server Sync Layer | 4–5 days | High |
| P5 | Client: UI Adaptation | 2–3 days | Low |
| P6 | Deployment & Infrastructure | 3–5 days | Medium |

**Total estimate:** 19–28 days.

**Parallelisation:** After P0 completes, P1+P2 (server work) and P3+P4 (client work) can be developed in parallel. Realistic wall-clock time with parallel tracks: 14–18 days.

### P0 — Repo Restructure (1–2 days)

- Create `nivesh-server/`, `nivesh-client/`, `nivesh-shared/` directories
- Move existing `backend/` → `nivesh-server/app/`
- Move existing `frontend/` → `nivesh-client/frontend/`
- Extract shared Pydantic schemas → `nivesh-shared/schemas/`
- Update `.gitignore`, CI configs, root README

### P1 — Server: Data Ownership Boundary (3–5 days)

- Define all server PostgreSQL table schemas (new tables from §3.1–3.7)
- Write Alembic migrations for new tables
- Promote existing ETL scripts to proper APScheduler jobs in `ingestion/scheduler.py`
- Write `analytics/technical.py` (pandas-ta) and `analytics/patterns.py` (scipy)

### P2 — Server: API Contract Design (3–4 days)

- Implement all routers from §5.1–5.4
- Define response envelope and cursor pagination
- Add `?from_date=` delta sync parameter to all time-series endpoints
- Export OpenAPI spec as `api-contract.json` — this is the versioned contract artifact

### P3 — Client: Local DB Design (3–4 days)

- Implement all SQLite tables from §4.1–4.4
- Write Alembic migrations for SQLite
- Implement `sync_state` table and TTL logic in cache tables
- Test Alembic auto-upgrade on first run

### P4 — Client: Server Sync Layer (4–5 days)

- Implement `sync/http_client.py`: httpx async client with retry + exponential backoff
- Implement `sync/delta.py`: staleness detection, `from_date` computation from `sync_state`
- Implement `sync/scheduler.py`: background APScheduler jobs for cache refresh
- Implement JWT middleware in `http_client.py`: intercept 401, auto-refresh, retry
- Implement offline fallback: serve stale cache + UI banner when server unreachable

### P5 — Client: UI Adaptation (2–3 days)

- Update React API base URL from server direct → `http://localhost:8001`
- Add sync status indicator: last synced timestamp per data type
- Add server connectivity banner (online/offline/stale)
- Portfolio + watchlist views read/write via client local API only

### P6 — Deployment & Infrastructure (3–5 days)

- Server: Dockerfile + GitHub Actions CI/CD pipeline
- Server: Deploy to Railway / Render / Fly.io (managed PostgreSQL)
- Server: Secrets via cloud secret manager (not `.env` files)
- Client: `setup.bat` / `setup.sh` install script (extend existing Windows setup)
- Client: `.env.example` with `NIVESH_SERVER_URL=https://api.nivesh.app`
- Server health endpoint polled by client on startup

---

## 9. Key Architectural Decisions

**Client never talks directly to cloud PostgreSQL.**
All data flows through the versioned server REST API. PostgreSQL credentials exist only in the server's cloud environment. No exceptions.

**Client local DB is SQLite.**
Zero infrastructure for end users — no Docker, no PostgreSQL install. SQLAlchemy handles the ORM layer identically to the server. Alembic handles schema migrations automatically on startup.

**Server is read-only for all clients.**
Clients cannot trigger data ingestion or write to the server DB. Only the server's own APScheduler pipeline mutates server data. Client `POST` endpoints exist only for auth (`/auth/login`, `/auth/refresh`).

**`nivesh-shared/schemas/` is the API contract.**
Both server and client import the same Pydantic response models. A breaking schema change requires bumping the shared package version — a mismatched client gets a clear Pydantic validation error rather than a silent deserialization bug.

**Delta sync via `?from_date=` + `sync_state` table.**
The client stores `last_synced_at` per symbol in `sync_state`. Every time-series fetch sends `?from_date=<last_synced_at>`. The server returns only rows newer than that date. This eliminates redundant re-download of years of OHLCV and NAV history on every sync.

**Offline-first client.**
The client never shows a blank screen when the server is unreachable. Stale cache is served with a visible banner showing the last sync timestamp. The `GET /health` endpoint is polled every 60 seconds to update connectivity state.

**Analytics computation is server-only.**
`pandas-ta`, `scipy`, and the fund metrics engine (`analytics.py`) run exclusively on the server as part of the EOD pipeline. The client imports zero analytics libraries. This keeps the client install lightweight and ensures all users see the same computed values.

**Agent data is client-only.**
Agent sessions, conversation history, tool call logs, and agent memory are stored in client SQLite and never transmitted to the server. The agent uses the client proxy layer to fetch financial data (which does hit the server API), but the agent's own state is local.

**JWT tokens stored in SQLite, not browser.**
Since the client has a Python FastAPI backend, tokens are stored in the local SQLite `auth_tokens` table. The React frontend never handles tokens directly — all server-bound requests go through the client FastAPI proxy which injects the `Authorization` header.

---

*Document version: 1.0 · Generated: May 2026 · Next: Low-Level Design (sync engine, agentic layer, ingestion pipeline)*
