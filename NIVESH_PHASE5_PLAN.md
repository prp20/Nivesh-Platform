# Nivesh Platform — Phase 5: React UI Adaptation
## Low-Level Implementation Plan · Grounded in dev branch code
### Version 1.0 · May 2026

---

## Table of Contents

1. [Phase 5 Goal & Scope](#1-phase-5-goal--scope)
2. [What Phase 4 Built — Exact Contract](#2-what-phase-4-built--exact-contract)
3. [What Phase 5 Changes in the React App](#3-what-phase-5-changes-in-the-react-app)
4. [File-by-File Change Map](#4-file-by-file-change-map)
5. [Task 5.1 — API Base URL Switch](#task-51--api-base-url-switch)
6. [Task 5.2 — Axios / Fetch Client Centralisation](#task-52--axios--fetch-client-centralisation)
7. [Task 5.3 — Auth Context & Login Screen](#task-53--auth-context--login-screen)
8. [Task 5.4 — Token Lifecycle Management](#task-54--token-lifecycle-management)
9. [Task 5.5 — Sync Status Bar Component](#task-55--sync-status-bar-component)
10. [Task 5.6 — Offline Banner & Stale Data Indicators](#task-56--offline-banner--stale-data-indicators)
11. [Task 5.7 — Portfolio Pages (New)](#task-57--portfolio-pages-new)
12. [Task 5.8 — Watchlist Page (New)](#task-58--watchlist-page-new)
13. [Task 5.9 — Fund Pages — Wire to Proxy](#task-59--fund-pages--wire-to-proxy)
14. [Task 5.10 — Stock Pages — Wire to Proxy](#task-510--stock-pages--wire-to-proxy)
15. [Task 5.11 — Agent Chat Page (Stub)](#task-511--agent-chat-page-stub)
16. [Task 5.12 — React Router Updates](#task-512--react-router-updates)
17. [Task 5.13 — End-to-End Smoke Test](#task-513--end-to-end-smoke-test)
18. [Response Shape Compatibility Reference](#18-response-shape-compatibility-reference)
19. [Dependency Changes](#19-dependency-changes)
20. [Definition of Done](#20-definition-of-done)
21. [Execution Order — Day by Day](#21-execution-order--day-by-day)

---

## 1. Phase 5 Goal & Scope

**Goal:** Adapt the existing React frontend so it talks exclusively to
`localhost:8001` (the Phase 4 client) instead of the server directly.
Add a login screen, a sync status bar, offline indicators, portfolio
pages, and a watchlist page. Wire all existing fund and stock views
to the proxy routes. The agent chat page is stubbed for Phase 6.

**In scope:**
- Switch every `fetch`/`axios` base URL to `http://localhost:8001`
- Centralise the HTTP client so the switch is a one-line change in one file
- Add an `AuthContext` with login/logout state
- Build a `LoginPage` component that calls `POST /auth/login`
- Add a `SyncStatusBar` showing server connectivity and last-synced time
- Add an offline banner shown whenever a proxy response has `_offline: true`
- Build `PortfolioPage`, `HoldingsPage`, `TransactionsPage`,
  `WatchlistPage` backed by `/local/*` endpoints
- Wire existing fund list, fund detail, fund comparison, benchmark,
  stock list, stock detail, and screener pages to `/proxy/*` routes
- Stub `AgentChatPage` with a message input that calls `POST
  /agent/sessions/{id}/chat` (LLM reply wired in Phase 6)
- Update React Router with new routes and a protected route wrapper

**Out of scope for Phase 5:**
- LLM wiring in the agent (Phase 6)
- CI/CD (Phase 8)
- Any backend changes — Phase 5 is pure React

**Constraint: preserve existing component shapes.**
The existing React components already parse `FundMasterListResponse`
(`total`, `skip`, `limit`, `items`), `StockDetailResult`, and
`ScreenerResponse`. The proxy router (Phase 4) returns these shapes
unchanged. Phase 5 must not introduce any transformation that breaks
this contract — the goal is a URL swap, not a data model change.

---

## 2. What Phase 4 Built — Exact Contract

Phase 5 depends on these Phase 4 endpoints. This is the contract.

### Auth

| Method | Path | Request body | Response |
|---|---|---|---|
| `POST` | `/auth/login` | `{username, password}` | `{access_token, token_type, expires_in}` |
| `POST` | `/auth/logout` | — | 204 |

### Local (no auth needed from React — local only)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/local/watchlist` | `?asset_type=STOCK\|FUND` |
| `POST` | `/local/watchlist` | `{symbol, asset_type, display_name, notes, alert_above, alert_below}` |
| `DELETE` | `/local/watchlist/{id}` | |
| `GET` | `/local/portfolio/holdings` | `?asset_type=STOCK\|FUND` |
| `POST` | `/local/portfolio/holdings` | `{symbol, asset_type, quantity, avg_cost, buy_date, ...}` |
| `PUT` | `/local/portfolio/holdings/{id}` | |
| `DELETE` | `/local/portfolio/holdings/{id}` | |
| `GET` | `/local/portfolio/transactions` | `?symbol=` |
| `POST` | `/local/portfolio/transactions` | |
| `GET` | `/local/preferences` | Returns `{key: value}` dict |
| `PUT` | `/local/preferences/{key}` | Query param `?value=` |

### Proxy (server data, JWT injected by client)

| Method | Path | Server shape returned |
|---|---|---|
| `GET` | `/proxy/funds` | `FundMasterListResponse` → `{total, skip, limit, items[]}` |
| `GET` | `/proxy/funds/{scheme_code}` | `FundMasterRead` |
| `GET` | `/proxy/funds/{scheme_code}/nav` | `[FundNavHistoryRead]` |
| `GET` | `/proxy/funds/compare` | `ComparisonResponse` → `{funds[], ranking, warning}` |
| `GET` | `/proxy/benchmarks` | `BenchmarkPaginated` → `{items[], total}` |
| `GET` | `/proxy/benchmarks/{code}` | `BenchmarkMasterRead` |
| `GET` | `/proxy/stocks` | `StockListResponse` → `{results[], total, page, limit}` |
| `GET` | `/proxy/stocks/{symbol}` | `StockDetailResult` |
| `GET` | `/proxy/stocks/screener` | `ScreenerResponse` → `{results[], total, page, limit, filters_applied}` |
| `GET` | `/proxy/sync/status` | `{runs[], total}` |

### Status

| Method | Path | Response |
|---|---|---|
| `GET` | `/status` | `{is_online, last_connected_at, server_url, cached_resources, db_path}` |
| `GET` | `/health` | `{status, port}` |

### Agent

| Method | Path | Notes |
|---|---|---|
| `POST` | `/agent/sessions` | `{title?, context_type, context_id?}` → `{session_id}` |
| `GET` | `/agent/sessions` | List of sessions |
| `GET` | `/agent/sessions/{id}/messages` | Ordered message list |
| `POST` | `/agent/sessions/{id}/chat` | `{message}` → `{reply, session_id}` |
| `GET` | `/agent/memory` | `{key: {value, confidence}}` |

---

## 3. What Phase 5 Changes in the React App

### Changes to existing files

| File | Change type | What changes |
|---|---|---|
| `src/config.ts` (or `api.ts`) | **Modify** | `API_BASE` → `http://localhost:8001` |
| `src/services/api.ts` | **Modify** | All endpoint paths: `/api/funds` → `/proxy/funds` etc. |
| `src/App.tsx` | **Modify** | Wrap in `AuthProvider`, add routes, add `SyncStatusBar` |
| `src/main.tsx` | **Modify** | Wrap in `AuthProvider` |
| Fund list/detail/comparison pages | **Modify** | URL switch only — shapes unchanged |
| Benchmark pages | **Modify** | URL switch only |
| Stock list/detail/screener pages | **Modify** | URL switch only |

### New files

| File | Purpose |
|---|---|
| `src/context/AuthContext.tsx` | Login state, token storage, logout |
| `src/pages/LoginPage.tsx` | Login form |
| `src/components/SyncStatusBar.tsx` | Online/offline/last-synced indicator |
| `src/components/OfflineBanner.tsx` | Shows when `_offline: true` in response |
| `src/components/ProtectedRoute.tsx` | Redirects to `/login` if not authenticated |
| `src/pages/portfolio/PortfolioPage.tsx` | Holdings + P&L summary |
| `src/pages/portfolio/HoldingsPage.tsx` | Holdings CRUD table |
| `src/pages/portfolio/TransactionsPage.tsx` | Transaction history |
| `src/pages/portfolio/AddHoldingModal.tsx` | Form to add a holding |
| `src/pages/portfolio/AddTransactionModal.tsx` | Form to add a transaction |
| `src/pages/WatchlistPage.tsx` | Watchlist with add/remove |
| `src/pages/AgentChatPage.tsx` | Chat UI stub (Phase 6 wires LLM) |
| `src/hooks/useClientStatus.ts` | Polls `/status` every 60s |
| `src/hooks/useOfflineDetect.ts` | Reads `_offline` flag from any response |

---

## 4. File-by-File Change Map

```
nivesh-client/frontend/src/
│
├── config.ts                      ← MODIFY: API_BASE → localhost:8001
├── services/
│   └── api.ts                     ← MODIFY: all paths /api/* → /proxy/*
│                                           add /local/* + /agent/* calls
├── context/
│   └── AuthContext.tsx             ← CREATE
├── hooks/
│   ├── useClientStatus.ts          ← CREATE: polls /status every 60s
│   └── useOfflineDetect.ts         ← CREATE: reads _offline from responses
├── components/
│   ├── SyncStatusBar.tsx           ← CREATE
│   ├── OfflineBanner.tsx           ← CREATE
│   └── ProtectedRoute.tsx          ← CREATE
├── pages/
│   ├── LoginPage.tsx               ← CREATE
│   ├── WatchlistPage.tsx           ← CREATE
│   ├── AgentChatPage.tsx           ← CREATE (stub)
│   └── portfolio/
│       ├── PortfolioPage.tsx       ← CREATE
│       ├── HoldingsPage.tsx        ← CREATE
│       ├── TransactionsPage.tsx    ← CREATE
│       ├── AddHoldingModal.tsx     ← CREATE
│       └── AddTransactionModal.tsx ← CREATE
├── App.tsx                         ← MODIFY: AuthProvider, routes, SyncStatusBar
└── main.tsx                        ← MODIFY: AuthProvider wrapper
```

---

## Task 5.1 — API Base URL Switch

**File:** `src/config.ts`
**Estimated time:** 15 minutes

This is the foundational change. Everything else in Phase 5 depends on this being correct.

```typescript
// src/config.ts

// BEFORE (pointed directly at the Render server or local backend):
// export const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// AFTER: always points to the local Phase 4 client — never the cloud server
export const API_BASE = "http://localhost:8001";

// The React UI never holds a JWT token. Auth is handled by the client backend.
// All server calls go through /proxy/* — the client injects the Bearer header.
```

Add to `.env.development` (Vite):
```bash
# .env.development
VITE_CLIENT_URL=http://localhost:8001
```

If the project uses a `.env`-based `VITE_API_URL`, ensure it is no longer used:
```bash
# .env (remove or replace)
# VITE_API_URL=https://nivesh-server.onrender.com  ← REMOVE THIS
```

---

## Task 5.2 — Axios / Fetch Client Centralisation

**File:** `src/services/api.ts`
**Estimated time:** 1 hour

This file centralises all HTTP calls. Phase 5 rewrites the path prefixes from `/api/*` to `/proxy/*` and adds new sections for `/local/*` and `/agent/*`. The response shapes do not change — only the URL prefixes.

```typescript
// src/services/api.ts
import { API_BASE } from "../config";

// ── Core fetcher ──────────────────────────────────────────────────────────────
// All API calls go through this function.
// No auth headers needed — the client backend (port 8001) handles JWT.

async function request<T>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  options: {
    params?: Record<string, string | number | boolean | undefined>;
    body?: unknown;
  } = {}
): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);

  if (options.params) {
    Object.entries(options.params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) {
        url.searchParams.set(k, String(v));
      }
    });
  }

  const resp = await fetch(url.toString(), {
    method,
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
    credentials: "include",     // Sends the HttpOnly refresh_token cookie automatically
  });

  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new ApiError(resp.status, error.detail ?? "Request failed");
  }

  // 204 No Content — return empty object
  if (resp.status === 204) return {} as T;

  return resp.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}


// ── Auth ──────────────────────────────────────────────────────────────────────
// React calls /auth/* on the CLIENT (port 8001).
// The client handles talking to the server and storing tokens.
// React never sees or stores the JWT.

export const authApi = {
  login: (username: string, password: string) =>
    request<{ access_token: string; token_type: string; expires_in: number }>(
      "POST", "/auth/login", { body: { username, password } }
    ),

  logout: () => request<void>("POST", "/auth/logout"),
};


// ── Proxy — Mutual Funds ──────────────────────────────────────────────────────
// Paths changed: /api/funds → /proxy/funds
// Shapes unchanged — server returns same FundMasterListResponse, FundMasterRead etc.

export const fundsApi = {
  list: (params?: {
    is_active?: boolean;
    category?: string;
    amc?: string;
    plan_type?: string;
    search?: string;
    skip?: number;
    limit?: number;
    order_by?: string;
  }) => request<FundListResponse>("GET", "/proxy/funds", { params }),

  detail: (schemeCode: string) =>
    request<FundDetail>("GET", `/proxy/funds/${schemeCode}`),

  nav: (schemeCode: string, limit = 365) =>
    request<NavHistoryItem[]>("GET", `/proxy/funds/${schemeCode}/nav`,
      { params: { limit } }),

  compare: (schemeCodes: string[]) =>
    request<ComparisonResponse>("GET", "/proxy/funds/compare",
      { params: { scheme_codes: schemeCodes.join(",") } }),
};


// ── Proxy — Benchmarks ───────────────────────────────────────────────────────

export const benchmarksApi = {
  list: (params?: { is_active?: boolean; search?: string; skip?: number; limit?: number }) =>
    request<BenchmarkListResponse>("GET", "/proxy/benchmarks", { params }),

  detail: (code: string) =>
    request<BenchmarkDetail>("GET", `/proxy/benchmarks/${code}`),
};


// ── Proxy — Stocks ────────────────────────────────────────────────────────────
// Paths changed: /api/stocks → /proxy/stocks

export const stocksApi = {
  list: (params?: {
    page?: number;
    limit?: number;
    sector?: string;
    market_cap_cat?: string;
    search?: string;
    sort_by?: string;
    order?: string;
  }) => request<StockListResponse>("GET", "/proxy/stocks", { params }),

  detail: (symbol: string) =>
    request<StockDetail>("GET", `/proxy/stocks/${symbol.toUpperCase()}`),

  screener: (filters: ScreenerFilters) =>
    request<ScreenerResponse>("GET", "/proxy/stocks/screener", { params: filters as any }),
};


// ── Proxy — Sync Status ───────────────────────────────────────────────────────

export const syncApi = {
  status: (pipelineName?: string) =>
    request<{ runs: EtlRun[]; total: number }>(
      "GET", "/proxy/sync/status",
      { params: pipelineName ? { pipeline_name: pipelineName } : undefined }
    ),
};


// ── Local — Portfolio & Watchlist ─────────────────────────────────────────────
// /local/* routes talk to SQLite — never leave the machine.
// No server round-trip. No JWT needed.

export const portfolioApi = {
  getHoldings: (assetType?: "STOCK" | "FUND") =>
    request<Holding[]>("GET", "/local/portfolio/holdings",
      { params: assetType ? { asset_type: assetType } : undefined }),

  addHolding: (data: HoldingCreate) =>
    request<Holding>("POST", "/local/portfolio/holdings", { body: data }),

  updateHolding: (id: number, data: HoldingCreate) =>
    request<Holding>("PUT", `/local/portfolio/holdings/${id}`, { body: data }),

  deleteHolding: (id: number) =>
    request<void>("DELETE", `/local/portfolio/holdings/${id}`),

  getTransactions: (symbol?: string) =>
    request<Transaction[]>("GET", "/local/portfolio/transactions",
      { params: symbol ? { symbol } : undefined }),

  addTransaction: (data: TransactionCreate) =>
    request<Transaction>("POST", "/local/portfolio/transactions", { body: data }),
};

export const watchlistApi = {
  get: (assetType?: "STOCK" | "FUND") =>
    request<WatchlistItem[]>("GET", "/local/watchlist",
      { params: assetType ? { asset_type: assetType } : undefined }),

  add: (data: WatchlistCreate) =>
    request<WatchlistItem>("POST", "/local/watchlist", { body: data }),

  remove: (id: number) =>
    request<void>("DELETE", `/local/watchlist/${id}`),
};

export const preferencesApi = {
  get: () => request<Record<string, string>>("GET", "/local/preferences"),

  set: (key: string, value: string) =>
    request<{ key: string; value: string }>(
      "PUT", `/local/preferences/${key}`, { params: { value } }
    ),
};


// ── Status ────────────────────────────────────────────────────────────────────

export const statusApi = {
  get: () =>
    request<ClientStatus>("GET", "/status"),
};


// ── Agent ─────────────────────────────────────────────────────────────────────

export const agentApi = {
  createSession: (data: { context_type: string; context_id?: string; title?: string }) =>
    request<{ session_id: number; title: string }>(
      "POST", "/agent/sessions", { body: data }
    ),

  listSessions: () =>
    request<AgentSession[]>("GET", "/agent/sessions"),

  getMessages: (sessionId: number) =>
    request<AgentMessage[]>("GET", `/agent/sessions/${sessionId}/messages`),

  chat: (sessionId: number, message: string) =>
    request<{ reply: string; session_id: number }>(
      "POST", `/agent/sessions/${sessionId}/chat`, { body: { message } }
    ),

  getMemory: () =>
    request<Record<string, { value: string; confidence: string }>>(
      "GET", "/agent/memory"
    ),
};


// ── TypeScript interfaces ─────────────────────────────────────────────────────
// These mirror the server Pydantic schemas exactly.
// Phase 5 does not transform shapes — they pass through from proxy unchanged.

export interface FundListResponse {
  total: number;
  skip: number;
  limit: number;
  items: FundDetail[];
}

export interface FundDetail {
  scheme_code: string;
  scheme_name: string;
  amc_name: string;
  inception_date: string;
  plan_type: string;
  scheme_category: string;
  scheme_subcategory?: string;
  benchmark_index_code?: string;
  isin?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  metrics?: FundMetrics;
  // Offline flag — present when served from stale cache
  _offline?: boolean;
  _stale?: boolean;
}

export interface FundMetrics {
  scheme_code: string;
  current_nav: number;
  nav_date: string;
  aum_in_crores?: number;
  expense_ratio?: number;
  fund_rating?: number;
  cagr_3year?: number;
  cagr_5year?: number;
  absolute_return_1y?: number;
  absolute_return_3y?: number;
  absolute_return_5y?: number;
  sortino_ratio?: number;
  sharpe_ratio?: number;
  alpha?: number;
  beta?: number;
  maximum_drawdown?: number;
  final_verdict?: string;
  metrics_calculated_at: string;
  updated_at: string;
}

export interface NavHistoryItem {
  scheme_code: string;
  nav_date: string;
  nav_value: number;
}

export interface ComparisonResponse {
  funds: { scheme_code: string; fund_info?: FundDetail; metrics?: FundMetrics }[];
  ranking?: {
    rankings: Array<{
      scheme_code: string;
      rank: number;
      composite_score: number;
      group_scores: Record<string, number>;
      wins: string[];
      is_recommended: boolean;
      recommendation_reason?: string;
    }>;
    comparison_summary: string;
  };
  warning?: string;
}

export interface BenchmarkListResponse {
  items: BenchmarkDetail[];
  total: number;
}

export interface BenchmarkDetail {
  benchmark_code: string;
  benchmark_name: string;
  ticker: string;
  benchmark_type?: string;
  asset_class?: string;
  is_active: boolean;
  metrics?: BenchmarkMetrics;
  latest_close?: number;
  change_percent?: number;
}

export interface BenchmarkMetrics {
  benchmark_code: string;
  current_nav: number;
  nav_date: string;
  cagr_3year?: number;
  cagr_5year?: number;
  sortino_ratio?: number;
  sharpe_ratio?: number;
  standard_deviation?: number;
  maximum_drawdown?: number;
}

export interface StockListResponse {
  results: StockListItem[];
  total: number;
  page: number;
  limit: number;
}

export interface StockListItem {
  id: number;
  symbol: string;
  company_name: string;
  sector?: string;
  market_cap_cat?: string;
  latest_close?: number;
  latest_date?: string;
  rating_label?: string;
  total_score?: number;
}

export interface StockDetail {
  id: number;
  symbol: string;
  company_name: string;
  sector?: string;
  industry?: string;
  market_cap_cat?: string;
  latest_close?: number;
  latest_high?: number;
  latest_low?: number;
  latest_volume?: number;
  latest_date?: string;
  change_pct?: number;
  rating_label?: string;
  total_score?: number;
  fundamental_score?: number;
  technical_score?: number;
  rsi_14?: number;
  macd_hist?: number;
  sma_200?: number;
  sma_50?: number;
  pe_ratio?: number;
  pb_ratio?: number;
  roe?: number;
  roce?: number;
  debt_equity?: number;
  pct_from_52w_high?: number;
  pct_from_52w_low?: number;
  _offline?: boolean;
}

export interface ScreenerFilters {
  min_pe?: number; max_pe?: number;
  min_pb?: number; max_pb?: number;
  min_roe?: number; min_roce?: number;
  min_pat_margin?: number; min_ebitda_margin?: number;
  min_revenue_growth?: number; min_pat_growth?: number;
  max_debt_equity?: number; min_interest_cov?: number;
  min_cfo_to_pat?: number; min_roic?: number;
  min_ev_ebitda?: number; max_ev_ebitda?: number;
  min_piotroski?: number; min_fcf_yield?: number;
  min_beta?: number; max_beta?: number;
  min_rs_6m?: number; min_volume_ratio?: number;
  page?: number; limit?: number;
  sort_by?: string; order?: string;
}

export interface ScreenerResponse {
  results: ScreenerResult[];
  total: number;
  page: number;
  limit: number;
  filters_applied: Record<string, unknown>;
}

export interface ScreenerResult {
  symbol: string;
  company_name: string;
  sector?: string;
  latest_close?: number;
  pe_ratio?: number;
  pb_ratio?: number;
  roe?: number;
  roce?: number;
  debt_equity?: number;
  rating_label?: string;
  total_score?: number;
}

export interface ClientStatus {
  is_online: boolean;
  last_connected_at?: string;
  server_url: string;
  cached_resources: number;
  db_path: string;
}

export interface EtlRun {
  id: number;
  pipeline_name: string;
  entity_id?: string;
  status: string;
  triggered_by: string;
  started_at: string;
  ended_at?: string;
  records_in: number;
  records_out: number;
  error_msg?: string;
}

export interface Holding {
  id: number;
  symbol: string;
  asset_type: string;
  quantity: number;
  avg_cost: number;
  buy_date: string;
  folio_number?: string;
  broker?: string;
  notes?: string;
}

export interface HoldingCreate {
  symbol: string;
  asset_type: "STOCK" | "FUND";
  quantity: number;
  avg_cost: number;
  buy_date: string;
  folio_number?: string;
  broker?: string;
  notes?: string;
}

export interface Transaction {
  id: number;
  symbol: string;
  asset_type: string;
  txn_type: string;
  quantity: number;
  price: number;
  txn_date: string;
  amount?: number;
  brokerage?: number;
  notes?: string;
}

export interface TransactionCreate {
  symbol: string;
  asset_type: "STOCK" | "FUND";
  txn_type: "BUY" | "SELL" | "DIVIDEND" | "SIP" | "SWITCH_IN" | "SWITCH_OUT";
  quantity: number;
  price: number;
  txn_date: string;
  brokerage?: number;
  notes?: string;
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  asset_type: string;
  display_name?: string;
  notes?: string;
  alert_above?: number;
  alert_below?: number;
  added_at: string;
}

export interface WatchlistCreate {
  symbol: string;
  asset_type: "STOCK" | "FUND";
  display_name?: string;
  notes?: string;
  alert_above?: number;
  alert_below?: number;
}

export interface AgentSession {
  id: number;
  title?: string;
  context_type: string;
  context_id?: string;
  model_used: string;
  is_active: boolean;
  started_at: string;
  last_msg_at: string;
}

export interface AgentMessage {
  id: number;
  session_id: number;
  sequence_num: number;
  role: "user" | "assistant" | "tool" | "state";
  content_text?: string;
  content_json?: Record<string, unknown>;
  tool_name?: string;
  created_at: string;
}
```

---

## Task 5.3 — Auth Context & Login Screen

**Files:** `src/context/AuthContext.tsx`, `src/pages/LoginPage.tsx`
**Estimated time:** 1.5 hours

### `src/context/AuthContext.tsx`

```typescript
// src/context/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { authApi, ApiError } from "../services/api";

interface AuthState {
  isAuthenticated: boolean;
  username: string | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  error: string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    username: null,
    isLoading: true,     // true on mount — check if already logged in
  });
  const [error, setError] = useState<string | null>(null);

  // On mount: check if the client already has a valid token by calling /status.
  // If the client returns is_online=true, the stored token is working.
  // We don't store the token in React — the client holds it in SQLite.
  useEffect(() => {
    async function checkSession() {
      try {
        const resp = await fetch("http://localhost:8001/status");
        if (resp.ok) {
          const status = await resp.json();
          // If the client is online, a token must exist (login was done previously).
          // Read the last_login_username from preferences to show the username.
          if (status.is_online) {
            const prefsResp = await fetch("http://localhost:8001/local/preferences");
            const prefs = prefsResp.ok ? await prefsResp.json() : {};
            setState({
              isAuthenticated: true,
              username: prefs["last_login_username"] ?? "user",
              isLoading: false,
            });
            return;
          }
        }
      } catch {
        // Client not running or no stored session — show login
      }
      setState(s => ({ ...s, isLoading: false }));
    }
    checkSession();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    try {
      await authApi.login(username, password);
      // Store username in preferences so we can show it after restart
      await fetch(`http://localhost:8001/local/preferences/last_login_username?value=${encodeURIComponent(username)}`, {
        method: "PUT",
      });
      setState({ isAuthenticated: true, username, isLoading: false });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Incorrect username or password");
      } else if (err instanceof ApiError && err.status === 503) {
        setError("Cannot reach server — check NIVESH_SERVER_URL in ~/.nivesh/.env");
      } else {
        setError("Login failed — is the client running on port 8001?");
      }
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Best-effort
    }
    setState({ isAuthenticated: false, username: null, isLoading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, error }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

### `src/pages/LoginPage.tsx`

```typescript
// src/pages/LoginPage.tsx
import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { login, error } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch {
      // error is set in AuthContext
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">N</div>
        <h1>Nivesh Platform</h1>
        <p className="login-subtitle">Sign in to continue</p>

        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>

          <div className="form-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error && <p className="login-error">{error}</p>}

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="login-hint">
          Make sure the Nivesh Client is running:
          <code>uvicorn app.main:app --port 8001</code>
        </p>
      </div>
    </div>
  );
}
```

---

## Task 5.4 — Token Lifecycle Management

**File:** `src/components/ProtectedRoute.tsx`
**Estimated time:** 30 minutes

React never handles tokens directly. The only token lifecycle logic in React is:
1. Show `LoginPage` if not authenticated
2. After `authApi.login()` succeeds — mark authenticated
3. After `authApi.logout()` succeeds — mark unauthenticated

The 401 auto-refresh happens entirely in the Python client's `ServerClient` class (Phase 4, Task 4.4). React never sees a 401 from proxy routes because the client handles the refresh transparently before responding.

```typescript
// src/components/ProtectedRoute.tsx
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  // Still checking stored session — show nothing to avoid flash
  if (isLoading) {
    return <div className="loading-screen">Loading...</div>;
  }

  // Not authenticated — redirect to login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
```

**Note on 401 handling:** If the stored token is fully expired (refresh token also expired), the client returns a 401 to React. Add this global handler in `api.ts`:

```typescript
// Add to the request() function in api.ts, after resp.raise_for_status():

if (resp.status === 401) {
  // Session fully expired — client could not auto-refresh
  // Clear auth state and redirect to login
  window.dispatchEvent(new CustomEvent("auth:session-expired"));
  throw new ApiError(401, "Session expired — please log in again");
}
```

And listen in `AuthContext`:

```typescript
// In AuthProvider useEffect:
useEffect(() => {
  const handleExpiry = () => {
    setState({ isAuthenticated: false, username: null, isLoading: false });
  };
  window.addEventListener("auth:session-expired", handleExpiry);
  return () => window.removeEventListener("auth:session-expired", handleExpiry);
}, []);
```

---

## Task 5.5 — Sync Status Bar Component

**Files:** `src/hooks/useClientStatus.ts`, `src/components/SyncStatusBar.tsx`
**Estimated time:** 1 hour

### `src/hooks/useClientStatus.ts`

```typescript
// src/hooks/useClientStatus.ts
import { useState, useEffect } from "react";
import { statusApi, ClientStatus } from "../services/api";

export function useClientStatus(intervalMs = 60_000) {
  const [status, setStatus] = useState<ClientStatus | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const data = await statusApi.get();
        setStatus(data);
        setError(false);
      } catch {
        setError(true);
      }
    }

    fetch();                                  // Run immediately
    const id = setInterval(fetch, intervalMs); // Then on interval
    return () => clearInterval(id);
  }, [intervalMs]);

  return { status, error };
}
```

### `src/components/SyncStatusBar.tsx`

```typescript
// src/components/SyncStatusBar.tsx
import { useClientStatus } from "../hooks/useClientStatus";

export function SyncStatusBar() {
  const { status, error } = useClientStatus(60_000);

  if (error) {
    return (
      <div className="sync-bar sync-bar--error">
        ⚠ Client not reachable on port 8001
      </div>
    );
  }

  if (!status) return null;

  const lastSync = status.last_connected_at
    ? formatRelativeTime(status.last_connected_at)
    : "never";

  return (
    <div className={`sync-bar sync-bar--${status.is_online ? "online" : "offline"}`}>
      {status.is_online ? (
        <>
          <span className="sync-dot sync-dot--green" />
          Connected · Last sync {lastSync} · {status.cached_resources} cached
        </>
      ) : (
        <>
          <span className="sync-dot sync-dot--amber" />
          Offline — showing cached data (last sync {lastSync})
        </>
      )}
    </div>
  );
}

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
```

---

## Task 5.6 — Offline Banner & Stale Data Indicators

**File:** `src/hooks/useOfflineDetect.ts`, `src/components/OfflineBanner.tsx`
**Estimated time:** 45 minutes

The Phase 4 proxy router adds `_offline: true` and `_stale: true` to any response served from stale cache. React reads these flags and shows a banner.

### `src/hooks/useOfflineDetect.ts`

```typescript
// src/hooks/useOfflineDetect.ts
// Generic hook — pass any API response, returns whether it came from stale cache.

export function useOfflineDetect(data: { _offline?: boolean; _stale?: boolean } | null) {
  return {
    isOffline: data?._offline === true,
    isStale:   data?._stale   === true,
  };
}
```

### `src/components/OfflineBanner.tsx`

```typescript
// src/components/OfflineBanner.tsx
interface OfflineBannerProps {
  isOffline: boolean;
  lastSync?: string;    // ISO timestamp from server_generated_at
}

export function OfflineBanner({ isOffline, lastSync }: OfflineBannerProps) {
  if (!isOffline) return null;

  const syncAge = lastSync
    ? `Data from ${formatRelativeTime(lastSync)}`
    : "Cached data";

  return (
    <div className="offline-banner">
      ⚡ Server offline — {syncAge}. Connect to refresh.
    </div>
  );
}

function formatRelativeTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3_600_000);
  return hours < 1 ? "less than an hour ago" : `${hours}h ago`;
}
```

### Usage in any page component

```typescript
// Example: FundListPage.tsx
const [data, setData] = useState<FundListResponse | null>(null);
const { isOffline } = useOfflineDetect(data);

// In render:
<OfflineBanner isOffline={isOffline} />
```

---

## Task 5.7 — Portfolio Pages (New)

**Files:** `src/pages/portfolio/`
**Estimated time:** 2 hours

### `PortfolioPage.tsx`

Top-level portfolio summary: total invested, current value, P&L. Fetches holdings from `/local/portfolio/holdings` and enriches with current prices from `/proxy/stocks/{symbol}` and `/proxy/funds/{scheme_code}`.

```typescript
// src/pages/portfolio/PortfolioPage.tsx
import { useEffect, useState } from "react";
import { portfolioApi, fundsApi, stocksApi, Holding } from "../../services/api";
import { Link } from "react-router-dom";

interface EnrichedHolding extends Holding {
  current_price?: number;
  current_value?: number;
  pnl?: number;
  pnl_pct?: number;
}

export function PortfolioPage() {
  const [holdings, setHoldings] = useState<EnrichedHolding[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const raw = await portfolioApi.getHoldings();
      const enriched = await Promise.allSettled(
        raw.map(async h => {
          let current_price: number | undefined;
          try {
            if (h.asset_type === "STOCK") {
              const detail = await stocksApi.detail(h.symbol);
              current_price = detail.latest_close ?? undefined;
            } else {
              const detail = await fundsApi.detail(h.symbol);
              current_price = detail.metrics?.current_nav ?? undefined;
            }
          } catch {
            // Price unavailable — offline or not cached
          }
          const current_value = current_price ? current_price * h.quantity : undefined;
          const invested = h.avg_cost * h.quantity;
          const pnl = current_value !== undefined ? current_value - invested : undefined;
          const pnl_pct = pnl !== undefined ? (pnl / invested) * 100 : undefined;
          return { ...h, current_price, current_value, pnl, pnl_pct };
        })
      );

      setHoldings(
        enriched
          .filter(r => r.status === "fulfilled")
          .map(r => (r as PromiseFulfilledResult<EnrichedHolding>).value)
      );
      setLoading(false);
    }
    load();
  }, []);

  if (loading) return <div>Loading portfolio...</div>;

  const totalInvested = holdings.reduce((s, h) => s + h.avg_cost * h.quantity, 0);
  const totalCurrent  = holdings.reduce((s, h) => s + (h.current_value ?? h.avg_cost * h.quantity), 0);
  const totalPnl      = totalCurrent - totalInvested;
  const totalPnlPct   = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;

  return (
    <div className="portfolio-page">
      <h1>Portfolio</h1>

      <div className="portfolio-summary">
        <div className="summary-card">
          <div className="summary-label">Invested</div>
          <div className="summary-value">₹{totalInvested.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="summary-card">
          <div className="summary-label">Current Value</div>
          <div className="summary-value">₹{totalCurrent.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</div>
        </div>
        <div className={`summary-card ${totalPnl >= 0 ? "positive" : "negative"}`}>
          <div className="summary-label">P&L</div>
          <div className="summary-value">
            {totalPnl >= 0 ? "+" : ""}₹{Math.abs(totalPnl).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            <span className="pnl-pct"> ({totalPnlPct.toFixed(2)}%)</span>
          </div>
        </div>
      </div>

      <div className="portfolio-nav">
        <Link to="/portfolio/holdings">Holdings</Link>
        <Link to="/portfolio/transactions">Transactions</Link>
      </div>

      <div className="holdings-table">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Type</th>
              <th>Qty</th>
              <th>Avg Cost</th>
              <th>Current</th>
              <th>P&L</th>
              <th>P&L %</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map(h => (
              <tr key={h.id} className={h.pnl !== undefined && h.pnl >= 0 ? "row-positive" : "row-negative"}>
                <td><strong>{h.symbol}</strong></td>
                <td>{h.asset_type}</td>
                <td>{h.quantity}</td>
                <td>₹{h.avg_cost.toFixed(2)}</td>
                <td>{h.current_price ? `₹${h.current_price.toFixed(2)}` : "—"}</td>
                <td>{h.pnl !== undefined ? `₹${h.pnl.toFixed(0)}` : "—"}</td>
                <td>{h.pnl_pct !== undefined ? `${h.pnl_pct.toFixed(2)}%` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### `HoldingsPage.tsx`

Full CRUD table with add/edit/delete. Delegates to `AddHoldingModal`.

```typescript
// src/pages/portfolio/HoldingsPage.tsx
import { useEffect, useState } from "react";
import { portfolioApi, Holding } from "../../services/api";
import { AddHoldingModal } from "./AddHoldingModal";

export function HoldingsPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [showAdd, setShowAdd] = useState(false);

  async function load() {
    setHoldings(await portfolioApi.getHoldings());
  }
  useEffect(() => { load(); }, []);

  async function handleDelete(id: number) {
    if (!confirm("Remove this holding?")) return;
    await portfolioApi.deleteHolding(id);
    await load();
  }

  return (
    <div className="holdings-page">
      <div className="page-header">
        <h2>Holdings</h2>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>
          + Add Holding
        </button>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Symbol</th><th>Type</th><th>Qty</th>
            <th>Avg Cost</th><th>Buy Date</th><th>Broker</th><th></th>
          </tr>
        </thead>
        <tbody>
          {holdings.map(h => (
            <tr key={h.id}>
              <td>{h.symbol}</td>
              <td>{h.asset_type}</td>
              <td>{h.quantity}</td>
              <td>₹{h.avg_cost.toFixed(2)}</td>
              <td>{h.buy_date}</td>
              <td>{h.broker ?? "—"}</td>
              <td>
                <button className="btn-danger-sm" onClick={() => handleDelete(h.id)}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showAdd && (
        <AddHoldingModal
          onClose={() => setShowAdd(false)}
          onSaved={() => { setShowAdd(false); load(); }}
        />
      )}
    </div>
  );
}
```

### `AddHoldingModal.tsx`

```typescript
// src/pages/portfolio/AddHoldingModal.tsx
import { useState, FormEvent } from "react";
import { portfolioApi, HoldingCreate } from "../../services/api";

interface Props {
  onClose: () => void;
  onSaved: () => void;
}

export function AddHoldingModal({ onClose, onSaved }: Props) {
  const [form, setForm] = useState<HoldingCreate>({
    symbol: "", asset_type: "STOCK", quantity: 0,
    avg_cost: 0, buy_date: new Date().toISOString().split("T")[0],
  });
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await portfolioApi.addHolding({
        ...form,
        symbol: form.symbol.toUpperCase(),
      });
      onSaved();
    } catch (err: any) {
      setError(err.message ?? "Failed to save");
    }
  }

  const field = (key: keyof HoldingCreate, label: string, type = "text") => (
    <div className="form-field">
      <label>{label}</label>
      <input
        type={type}
        value={String(form[key] ?? "")}
        onChange={e => setForm(f => ({ ...f, [key]: type === "number" ? Number(e.target.value) : e.target.value }))}
        required={["symbol", "quantity", "avg_cost", "buy_date"].includes(key)}
      />
    </div>
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3>Add Holding</h3>
        <form onSubmit={handleSubmit}>
          {field("symbol", "Symbol (e.g. RELIANCE or scheme code)")}
          <div className="form-field">
            <label>Type</label>
            <select value={form.asset_type}
              onChange={e => setForm(f => ({ ...f, asset_type: e.target.value as "STOCK" | "FUND" }))}>
              <option value="STOCK">Stock</option>
              <option value="FUND">Mutual Fund</option>
            </select>
          </div>
          {field("quantity",  "Quantity",  "number")}
          {field("avg_cost",  "Avg Cost (₹)", "number")}
          {field("buy_date",  "Buy Date", "date")}
          {field("broker",    "Broker / AMC")}
          {field("folio_number", "Folio Number (MF only)")}
          {error && <p className="error">{error}</p>}
          <div className="modal-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary">Save</button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

---

## Task 5.8 — Watchlist Page (New)

**File:** `src/pages/WatchlistPage.tsx`
**Estimated time:** 1 hour

```typescript
// src/pages/WatchlistPage.tsx
import { useEffect, useState } from "react";
import { watchlistApi, WatchlistItem, WatchlistCreate } from "../services/api";

export function WatchlistPage() {
  const [items, setItems]   = useState<WatchlistItem[]>([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm]     = useState<WatchlistCreate>({
    symbol: "", asset_type: "STOCK",
  });

  async function load() { setItems(await watchlistApi.get()); }
  useEffect(() => { load(); }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    await watchlistApi.add({ ...form, symbol: form.symbol.toUpperCase() });
    setAdding(false);
    setForm({ symbol: "", asset_type: "STOCK" });
    load();
  }

  async function handleRemove(id: number) {
    await watchlistApi.remove(id);
    load();
  }

  return (
    <div className="watchlist-page">
      <div className="page-header">
        <h1>Watchlist</h1>
        <button className="btn-primary" onClick={() => setAdding(a => !a)}>
          {adding ? "Cancel" : "+ Add"}
        </button>
      </div>

      {adding && (
        <form onSubmit={handleAdd} className="add-form">
          <input
            placeholder="Symbol / Scheme code"
            value={form.symbol}
            onChange={e => setForm(f => ({ ...f, symbol: e.target.value }))}
            required
          />
          <select
            value={form.asset_type}
            onChange={e => setForm(f => ({ ...f, asset_type: e.target.value as "STOCK" | "FUND" }))}>
            <option value="STOCK">Stock</option>
            <option value="FUND">Mutual Fund</option>
          </select>
          <input
            placeholder="Notes (optional)"
            value={form.notes ?? ""}
            onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
          />
          <button type="submit" className="btn-primary">Add</button>
        </form>
      )}

      <div className="watchlist-grid">
        {items.length === 0 && (
          <p className="empty-state">No items in watchlist. Add stocks or funds to track.</p>
        )}
        {items.map(item => (
          <div key={item.id} className="watchlist-card">
            <div className="watchlist-card-header">
              <strong>{item.symbol}</strong>
              <span className="asset-badge">{item.asset_type}</span>
              <button
                className="btn-icon-danger"
                onClick={() => handleRemove(item.id)}
                title="Remove from watchlist"
              >×</button>
            </div>
            {item.display_name && (
              <div className="watchlist-name">{item.display_name}</div>
            )}
            {item.notes && <div className="watchlist-notes">{item.notes}</div>}
            {(item.alert_above || item.alert_below) && (
              <div className="watchlist-alerts">
                {item.alert_above && <span>▲ {item.alert_above}</span>}
                {item.alert_below && <span>▼ {item.alert_below}</span>}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Task 5.9 — Fund Pages — Wire to Proxy

**Estimated time:** 1 hour

All fund pages already work. The only change is the URL prefix. Find every occurrence of `/api/funds` and replace with `/proxy/funds` via the centralised `fundsApi` object in `api.ts`.

```bash
# Run this search to find every file that needs updating:
grep -rn "api/funds\|api/benchmarks" src/ --include="*.ts" --include="*.tsx"
```

For each file found, replace direct `fetch` calls with the `fundsApi` / `benchmarksApi` functions from `api.ts`.

**Specific pattern to find and fix:**

```typescript
// BEFORE: direct fetch to the server
const resp = await fetch(`${API_BASE}/api/funds/${schemeCode}`);

// AFTER: through the centralised api.ts (which uses /proxy/)
import { fundsApi } from "../../services/api";
const fund = await fundsApi.detail(schemeCode);
```

**Add offline banner to each fund page:**

```typescript
// In FundDetailPage.tsx (example):
const [data, setData] = useState<FundDetail | null>(null);
const { isOffline } = useOfflineDetect(data);

// In render:
<OfflineBanner isOffline={isOffline} />
```

---

## Task 5.10 — Stock Pages — Wire to Proxy

**Estimated time:** 1 hour

Same pattern as Task 5.9. Stock pages use `stocksApi` from `api.ts`.

```bash
grep -rn "api/stocks" src/ --include="*.ts" --include="*.tsx"
```

**Screener page — important detail:**

The screener filter state is built from `ScreenerFilterInput` (20+ fields). The `stocksApi.screener()` function passes all fields as query params. Ensure the filter form in the existing screener page maps field names exactly to `ScreenerFilters` in `api.ts` — they match `ScreenerFilterInput` from the server schema.

```typescript
// ScreenerPage.tsx — replace existing fetch:

// BEFORE:
const resp = await fetch(`${API_BASE}/api/stocks/screener?${queryString}`);

// AFTER:
import { stocksApi, ScreenerFilters } from "../../services/api";
const results = await stocksApi.screener(filters as ScreenerFilters);
```

---

## Task 5.11 — Agent Chat Page (Stub)

**File:** `src/pages/AgentChatPage.tsx`
**Estimated time:** 1 hour

Phase 5 builds the full UI. Phase 6 wires the LLM response. For now, the
reply comes from the Phase 4 stub (`"Agent not yet connected (Phase 6)"`).

```typescript
// src/pages/AgentChatPage.tsx
import { useState, useEffect, useRef } from "react";
import { agentApi, AgentMessage } from "../services/api";

export function AgentChatPage() {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages]   = useState<AgentMessage[]>([]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const bottomRef                 = useRef<HTMLDivElement>(null);

  // Create or load a session on mount
  useEffect(() => {
    async function init() {
      // Use the most recent active session, or create a new one
      const sessions = await agentApi.listSessions();
      if (sessions.length > 0) {
        const s = sessions[0];
        setSessionId(s.id);
        setMessages(await agentApi.getMessages(s.id));
      } else {
        const s = await agentApi.createSession({ context_type: "general" });
        setSessionId(s.session_id);
      }
    }
    init();
  }, []);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!sessionId || !input.trim() || loading) return;

    const userMsg = input.trim();
    setInput("");
    setLoading(true);

    // Optimistic UI: show user message immediately
    const optimistic: AgentMessage = {
      id: Date.now(), session_id: sessionId, sequence_num: messages.length + 1,
      role: "user", content_text: userMsg, created_at: new Date().toISOString(),
    };
    setMessages(m => [...m, optimistic]);

    try {
      const resp = await agentApi.chat(sessionId, userMsg);
      const assistantMsg: AgentMessage = {
        id: Date.now() + 1, session_id: sessionId,
        sequence_num: messages.length + 2, role: "assistant",
        content_text: resp.reply, created_at: new Date().toISOString(),
      };
      setMessages(m => [...m, assistantMsg]);
    } catch {
      const errMsg: AgentMessage = {
        id: Date.now() + 1, session_id: sessionId,
        sequence_num: messages.length + 2, role: "assistant",
        content_text: "Something went wrong. Please try again.",
        created_at: new Date().toISOString(),
      };
      setMessages(m => [...m, errMsg]);
    } finally {
      setLoading(false);
    }
  }

  async function handleNewSession() {
    const s = await agentApi.createSession({ context_type: "general" });
    setSessionId(s.session_id);
    setMessages([]);
  }

  return (
    <div className="agent-chat-page">
      <div className="chat-header">
        <h2>Nivesh Agent</h2>
        <span className="chat-badge">Phase 6 — LLM not yet connected</span>
        <button className="btn-secondary" onClick={handleNewSession}>
          New Conversation
        </button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask about a stock, fund, or your portfolio.</p>
            <div className="chat-suggestions">
              {[
                "Analyse RELIANCE",
                "Compare top large cap funds",
                "How is my portfolio doing?",
                "Show me oversold Nifty50 stocks",
              ].map(s => (
                <button key={s} className="suggestion-chip"
                  onClick={() => setInput(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id}
            className={`chat-bubble chat-bubble--${msg.role}`}>
            <div className="bubble-role">{msg.role}</div>
            <div className="bubble-content">
              {msg.content_text ?? JSON.stringify(msg.content_json)}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-bubble chat-bubble--assistant">
            <div className="bubble-content chat-thinking">Thinking...</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="chat-input-bar" onSubmit={handleSend}>
        <input
          type="text"
          placeholder="Ask about stocks, funds, or your portfolio..."
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading || !sessionId}
        />
        <button type="submit" disabled={loading || !input.trim() || !sessionId}
          className="btn-primary">
          Send
        </button>
      </form>
    </div>
  );
}
```

---

## Task 5.12 — React Router Updates

**File:** `src/App.tsx`
**Estimated time:** 30 minutes

```typescript
// src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { SyncStatusBar } from "./components/SyncStatusBar";
import { LoginPage } from "./pages/LoginPage";
import { PortfolioPage } from "./pages/portfolio/PortfolioPage";
import { HoldingsPage } from "./pages/portfolio/HoldingsPage";
import { TransactionsPage } from "./pages/portfolio/TransactionsPage";
import { WatchlistPage } from "./pages/WatchlistPage";
import { AgentChatPage } from "./pages/AgentChatPage";
// Existing pages — keep imports as-is
import { FundListPage } from "./pages/FundListPage";
import { FundDetailPage } from "./pages/FundDetailPage";
import { FundComparisonPage } from "./pages/FundComparisonPage";
import { BenchmarkListPage } from "./pages/BenchmarkListPage";
import { StockListPage } from "./pages/StockListPage";
import { StockDetailPage } from "./pages/StockDetailPage";
import { ScreenerPage } from "./pages/ScreenerPage";
import { Navbar } from "./components/Navbar";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/* SyncStatusBar renders outside routes — always visible */}
        <SyncStatusBar />

        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected — all authenticated routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<Navbar />}>
              {/* Existing fund routes */}
              <Route path="/"           element={<FundListPage />} />
              <Route path="/funds"      element={<FundListPage />} />
              <Route path="/funds/:schemeCode" element={<FundDetailPage />} />
              <Route path="/funds/compare"     element={<FundComparisonPage />} />
              <Route path="/benchmarks"        element={<BenchmarkListPage />} />

              {/* Existing stock routes */}
              <Route path="/stocks"            element={<StockListPage />} />
              <Route path="/stocks/:symbol"    element={<StockDetailPage />} />
              <Route path="/stocks/screener"   element={<ScreenerPage />} />

              {/* New Phase 5 routes */}
              <Route path="/portfolio"                element={<PortfolioPage />} />
              <Route path="/portfolio/holdings"       element={<HoldingsPage />} />
              <Route path="/portfolio/transactions"   element={<TransactionsPage />} />
              <Route path="/watchlist"                element={<WatchlistPage />} />
              <Route path="/agent"                    element={<AgentChatPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

### Navbar update — add new links

```typescript
// src/components/Navbar.tsx — add to existing nav links:
<Link to="/portfolio">Portfolio</Link>
<Link to="/watchlist">Watchlist</Link>
<Link to="/agent">Agent</Link>
```

---

## Task 5.13 — End-to-End Smoke Test

**Estimated time:** 1 hour

Run these in order after the UI is deployed. Every step must pass.

```bash
# Prerequisites:
# 1. Render server is running (Phase 2)
# 2. Ingestion has run at least once (Phase 3)
# 3. Client is running: uvicorn app.main:app --port 8001
# 4. React dev server: npm run dev (port 5173)
```

| # | Test | Expected |
|---|---|---|
| 1 | Open `http://localhost:5173` | Redirected to `/login` |
| 2 | Login with wrong password | Error: "Incorrect username or password" |
| 3 | Login with correct credentials | Redirected to `/` (fund list page) |
| 4 | Fund list loads | Table of funds with metrics |
| 5 | Fund detail page | Fund with NAV chart and metrics |
| 6 | Fund comparison | Side-by-side comparison with ranking |
| 7 | Stock list loads | Grid of stocks with ratings |
| 8 | Stock detail page | Price, technicals, fundamentals |
| 9 | Screener with `min_roe=15` | Filtered stock list |
| 10 | Sync status bar shows "Connected" | Green dot, last sync time |
| 11 | Stop Render server (kill or network off) | Offline banner appears |
| 12 | Fund list still loads (stale cache) | Data shown with `⚡ Server offline` banner |
| 13 | Portfolio → Add holding (RELIANCE, 10 units, ₹2500) | Holding saved |
| 14 | Portfolio page shows the holding with P&L | ₹ value and % shown |
| 15 | Watchlist → Add INFY | Card appears in watchlist |
| 16 | Watchlist → Remove INFY | Card disappears |
| 17 | Agent → Type "Analyse RELIANCE" | Stub reply received, message stored |
| 18 | Agent → New Conversation | Empty chat |
| 19 | Logout | Redirected to `/login` |
| 20 | Attempt to access `/portfolio` directly | Redirected to `/login` |

---

## 18. Response Shape Compatibility Reference

This table confirms the proxy response shapes are the same as before.
React components don't need to be rewritten — only the URL prefix changes.

| Component | Old path | New path | Shape changes |
|---|---|---|---|
| FundListPage | `/api/funds` | `/proxy/funds` | None — `FundMasterListResponse` unchanged |
| FundDetailPage | `/api/funds/{code}` | `/proxy/funds/{code}` | None + optional `_offline` flag |
| FundComparisonPage | `/api/funds/compare` | `/proxy/funds/compare` | None — `ComparisonResponse` unchanged |
| BenchmarkListPage | `/api/benchmarks` | `/proxy/benchmarks` | None — `BenchmarkPaginated` unchanged |
| StockListPage | `/api/stocks` | `/proxy/stocks` | None — `StockListResponse` unchanged |
| StockDetailPage | `/api/stocks/{sym}` | `/proxy/stocks/{sym}` | None — `StockDetailResult` unchanged |
| ScreenerPage | `/api/stocks/screener` | `/proxy/stocks/screener` | None — `ScreenerResponse` unchanged |
| — | — | `/local/portfolio/holdings` | New — `Holding[]` |
| — | — | `/local/watchlist` | New — `WatchlistItem[]` |
| — | — | `/agent/sessions/{id}/chat` | New — `{reply, session_id}` |

---

## 19. Dependency Changes

```json
// package.json — no new dependencies required.
// All Phase 5 work uses:
// - react (already installed)
// - react-router-dom (already installed — confirm v6+)
// - native fetch API (no axios needed — centralised in api.ts)

// The only version check needed:
// react-router-dom must be v6+ for <Outlet /> and <Navigate /> to work.
// Check: cat package.json | grep react-router-dom
```

If the project uses `axios` instead of `fetch`, no change is needed — just update the base URL in the axios instance config.

---

## 20. Definition of Done

Phase 5 is complete when all of the following are true:

- [ ] `http://localhost:5173` redirects to `/login` when not authenticated
- [ ] Login with correct credentials succeeds and redirects to fund list
- [ ] Login with wrong credentials shows an error message
- [ ] All existing fund list, fund detail, comparison, benchmark pages load
- [ ] All existing stock list, stock detail, screener pages load
- [ ] `SyncStatusBar` shows green "Connected" state when online
- [ ] `SyncStatusBar` shows amber "Offline" state when server unreachable
- [ ] Fund/stock pages show `OfflineBanner` when served from stale cache
- [ ] `POST /local/portfolio/holdings` adds a holding visible in the table
- [ ] `DELETE /local/portfolio/holdings/{id}` removes it
- [ ] `POST /local/portfolio/transactions` records a transaction
- [ ] `TransactionsPage` renders the transaction history
- [ ] `WatchlistPage` adds and removes items correctly
- [ ] `AgentChatPage` sends a message and shows the stub reply
- [ ] Agent session persists after page refresh (session stored in SQLite)
- [ ] Logout clears authentication and redirects to `/login`
- [ ] Navigating to `/portfolio` when not logged in redirects to `/login`
- [ ] All 20 smoke tests in Task 5.13 pass

---

## 21. Execution Order — Day by Day

```
Day 1 (4h)
  Task 5.1  API base URL switch (config.ts)                15 min
  Task 5.2  Centralise api.ts — all paths + TypeScript     1h
  Task 5.3  AuthContext + LoginPage                        1.5h
  Task 5.4  ProtectedRoute + session expiry handler        0.5h
  Task 5.5  SyncStatusBar + useClientStatus hook           1h

Day 2 (4h)
  Task 5.6  OfflineBanner + useOfflineDetect hook          45 min
  Task 5.7  PortfolioPage + HoldingsPage + AddHoldingModal 2h
  Task 5.8  WatchlistPage                                  1h
            TransactionsPage + AddTransactionModal         15 min

Day 3 (3h)
  Task 5.9  Wire fund pages to proxy                       1h
  Task 5.10 Wire stock + screener pages to proxy           1h
  Task 5.11 AgentChatPage stub                             1h

Day 4 (2h)
  Task 5.12 React Router updates + Navbar links            30 min
  Task 5.13 Full smoke test — fix issues                   1.5h
```

**Total: 4 working days**

---

*Phase 5 Implementation Plan · Nivesh Platform · May 2026*
*Previous: Phase 4 — Client Application (SQLite + Local API)*
*Next: Phase 6 — Agentic Layer (LLM wiring via Anthropic API + LangGraph)*
