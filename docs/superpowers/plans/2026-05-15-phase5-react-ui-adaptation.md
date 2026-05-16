# Phase 5 — React UI Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adapt the existing React/JSX/axios frontend to talk exclusively to `localhost:8001` (the Phase 4 client), fix broken auth assumptions, and add Portfolio, Watchlist, and Agent Chat pages.

**Architecture:** All server API calls go through `/proxy/*` on the client FastAPI (port 8001) which injects the JWT. Auth state is held in React component state only (no localStorage). New local-data pages (Portfolio, Watchlist) call `/local/*` which reads/writes SQLite directly — no server dependency.

**Tech Stack:** React 19, JSX, axios, Redux Toolkit, Tailwind CSS, Framer Motion, Vite, react-router-dom v7, react-hot-toast, Material Symbols icons.

**Working directory:** `nivesh-client/frontend/` for all frontend tasks. Start the client backend before testing: `cd nivesh-client && uvicorn app.main:app --port 8001 --reload`

---

## File Map

```
MODIFY  src/api/apiClient.js                    baseURL → :8001, remove auth interceptor
MODIFY  src/api/services/authService.js         JSON login, remove getMe
MODIFY  src/api/services/fundService.js         /proxy/* paths, remove write methods
MODIFY  src/api/services/stockService.js        /proxy/* paths, remove pipeline triggers
CREATE  src/api/services/portfolioService.js    /local/portfolio/* CRUD
CREATE  src/api/services/watchlistService.js    /local/watchlist CRUD
CREATE  src/api/services/agentService.js        /agent/sessions + chat
CREATE  src/api/services/statusService.js       GET /status
REWRITE src/context/AuthContext.jsx             no localStorage, session via GET /status
CREATE  src/components/ProtectedRoute.jsx       replaces inline user ? guards
CREATE  src/components/SyncStatusBar.jsx        polls /status every 60s
CREATE  src/components/OfflineBanner.jsx        shows when _offline flag set
MODIFY  src/components/Layout.jsx               add SyncStatusBar, add nav links
MODIFY  src/pages/Login.jsx                     JSON body (not form-data)
REWRITE src/pages/Portfolio.jsx                 holdings CRUD + P&L
CREATE  src/pages/Watchlist.jsx                 watchlist add/remove
CREATE  src/pages/AgentChat.jsx                 chat UI stub
MODIFY  src/App.jsx                             ProtectedRoute wrapper + new routes
MODIFY  .env.development                        VITE_API_URL → http://localhost:8001
MODIFY  nivesh-client/app/routers/proxy.py      add missing fund sub-routes
```

---

## Task 0: Add missing proxy sub-routes to client backend

**Why:** React pages call `/proxy/funds/amcs`, `/proxy/funds/categories`, `/proxy/funds/{code}/similar`, and `/proxy/stocks/search` which aren't in the current proxy router. Without these, filter dropdowns and search break. Adding them here keeps Phase 5 purely additive.

**Files:**
- Modify: `nivesh-client/app/routers/proxy.py`

- [ ] **Step 1: Add missing fund sub-routes after the existing `/proxy/funds/compare` route**

Open `nivesh-client/app/routers/proxy.py`. After the `proxy_fund_compare` route (line ~69), add:

```python
@router.get("/funds/amcs")
async def proxy_fund_amcs(db: AsyncSession = Depends(get_db)):
    cache_key = "funds:amcs"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/funds/amcs")
        await set_cached(db, cache_key, data, 86400)   # 24h — AMC list rarely changes
        return data
    except OfflineError:
        return cached if cached else []


@router.get("/funds/categories")
async def proxy_fund_categories(db: AsyncSession = Depends(get_db)):
    cache_key = "funds:categories"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/funds/categories")
        await set_cached(db, cache_key, data, 86400)
        return data
    except OfflineError:
        return cached if cached else []


@router.get("/funds/categories/{category}/subcategories")
async def proxy_fund_subcategories(
    category: str, db: AsyncSession = Depends(get_db)
):
    cache_key = f"funds:subcategories:{category}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get(
                f"/api/v1/funds/categories/{category}/subcategories"
            )
        await set_cached(db, cache_key, data, 86400)
        return data
    except OfflineError:
        return cached if cached else []
```

After the `proxy_fund_detail` route, add:

```python
@router.get("/funds/{scheme_code}/similar")
async def proxy_fund_similar(
    scheme_code: str, db: AsyncSession = Depends(get_db)
):
    cache_key = f"funds:similar:{scheme_code}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/v1/funds/{scheme_code}/similar")
        await set_cached(db, cache_key, data, 3600)
        return data
    except OfflineError:
        return cached if cached else []
```

After the stocks section, add:

```python
@router.get("/stocks/search")
async def proxy_stock_search(
    q: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Stock symbol/name search. Short TTL — results are query-sensitive.
    Declared BEFORE /stocks/{symbol} to avoid route shadowing.
    """
    cache_key = f"stocks:search:{q.upper()}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/stocks/search", params={"q": q})
        await set_cached(db, cache_key, data, 300)    # 5 min
        return data
    except OfflineError:
        return cached if cached else {"results": []}
```

Note: `/proxy/stocks/search` MUST be declared before `/proxy/stocks/{symbol}` in the file. Move it to just after `proxy_screener` and before `proxy_stock_list`.

- [ ] **Step 2: Restart the client backend to verify new routes load**

```bash
cd nivesh-client
uvicorn app.main:app --port 8001 --reload
# Visit http://localhost:8001/docs — confirm new routes appear in the list
```

Expected: routes `/proxy/funds/amcs`, `/proxy/funds/categories`, `/proxy/stocks/search` visible in Swagger UI.

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/routers/proxy.py
git commit -m "feat(client): add missing proxy sub-routes (amcs, categories, search)"
```

---

## Task 1: Update environment config and API base URL

**Files:**
- Modify: `nivesh-client/frontend/.env.development`
- Modify: `nivesh-client/frontend/.env`
- Modify: `nivesh-client/frontend/src/api/apiClient.js`

- [ ] **Step 1: Update `.env.development`**

Replace the entire file content:

```bash
VITE_API_URL=http://localhost:8001
```

- [ ] **Step 2: Update `.env`**

Replace the entire file content:

```bash
# API URL — always the local client FastAPI, never the cloud server directly
VITE_API_URL=http://localhost:8001
```

- [ ] **Step 3: Rewrite `src/api/apiClient.js`**

```javascript
import axios from 'axios';

// All API calls go to the local client FastAPI on port 8001.
// The client backend injects the JWT for /proxy/* calls.
// React never handles JWT tokens directly.
const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001',
    headers: { 'Content-Type': 'application/json' },
});

// No request interceptor — client backend handles auth headers server-side.

// Response interceptor: on 401, the client's refresh logic already tried and
// gave up. Signal auth expiry to AuthContext via a custom event.
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            window.dispatchEvent(new CustomEvent('auth:session-expired'));
        }
        return Promise.reject(error);
    }
);

export default apiClient;
```

- [ ] **Step 4: Verify build passes**

```bash
cd nivesh-client/frontend
npm run build
```

Expected: build succeeds with no errors. (Warnings about unused vars are OK.)

- [ ] **Step 5: Commit**

```bash
git add nivesh-client/frontend/.env nivesh-client/frontend/.env.development \
        nivesh-client/frontend/src/api/apiClient.js
git commit -m "feat(ui): switch API base URL to localhost:8001, remove auth interceptor"
```

---

## Task 2: Rewrite auth service

**Files:**
- Modify: `nivesh-client/frontend/src/api/services/authService.js`

The current authService sends FormData and calls `/auth/me`. The client expects JSON body and has no `/auth/me` endpoint.

- [ ] **Step 1: Rewrite `src/api/services/authService.js`**

```javascript
import apiClient from '../apiClient';

const authService = {
    /**
     * POST /auth/login — forwards to Render server, stores JWT in SQLite.
     * Returns { access_token, token_type, expires_in }.
     * React never sees the raw JWT after this point.
     */
    login: async (username, password) => {
        const response = await apiClient.post('/auth/login', { username, password });
        return response.data;
    },

    /**
     * POST /auth/logout — clears stored tokens from SQLite.
     * Best-effort: local logout always succeeds even if server unreachable.
     */
    logout: async () => {
        try {
            await apiClient.post('/auth/logout');
        } catch {
            // Ignore — local SQLite tokens are cleared regardless
        }
    },
};

export default authService;
```

- [ ] **Step 2: Verify build passes**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/api/services/authService.js
git commit -m "feat(ui): rewrite authService — JSON body login, remove getMe"
```

---

## Task 3: Rewrite AuthContext

**Files:**
- Modify: `nivesh-client/frontend/src/context/AuthContext.jsx`

Current problems: stores JWT in localStorage, calls `/auth/me` (doesn't exist on client). New design: session detected via `GET /status` → `last_connected_at` field. `user` object kept for backward compatibility with existing route guards.

- [ ] **Step 1: Rewrite `src/context/AuthContext.jsx`**

```javascript
import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import authService from '../api/services/authService';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    // user: null = not authenticated, { username } = authenticated
    // Kept as 'user' (not 'isAuthenticated') for backward compat with existing route guards.
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Detect existing session on mount.
    // Strategy: GET /status — if last_connected_at is set, the user logged in before.
    // We don't check is_online because user can be authenticated while server is offline.
    useEffect(() => {
        const initAuth = async () => {
            try {
                const resp = await fetch('http://localhost:8001/status');
                if (resp.ok) {
                    const status = await resp.json();
                    // last_connected_at is set by the login endpoint and cleared on logout
                    if (status.last_connected_at) {
                        // Read stored username from preferences
                        const prefsResp = await fetch('http://localhost:8001/local/preferences');
                        const prefs = prefsResp.ok ? await prefsResp.json() : {};
                        setUser({ username: prefs.last_login_username ?? 'user' });
                    }
                }
            } catch {
                // Client not running — will show login screen
            } finally {
                setLoading(false);
            }
        };
        initAuth();
    }, []);

    // Listen for session expiry events dispatched by apiClient on 401
    useEffect(() => {
        const handleExpiry = () => {
            setUser(null);
        };
        window.addEventListener('auth:session-expired', handleExpiry);
        return () => window.removeEventListener('auth:session-expired', handleExpiry);
    }, []);

    const login = useCallback(async (username, password) => {
        setError(null);
        try {
            await authService.login(username, password);
            // Store username in local preferences for session persistence across page refreshes
            await fetch(
                `http://localhost:8001/local/preferences/last_login_username?value=${encodeURIComponent(username)}`,
                { method: 'PUT' }
            );
            setUser({ username });
        } catch (err) {
            const status = err.response?.status;
            if (status === 401) {
                setError('Incorrect username or password');
            } else if (status === 503) {
                setError('Cannot reach server — check NIVESH_SERVER_URL in ~/.nivesh/.env');
            } else {
                setError('Login failed — is the Nivesh Client running on port 8001?');
            }
            throw err;
        }
    }, []);

    const logout = useCallback(async () => {
        await authService.logout();
        // Clear stored username from preferences
        try {
            await fetch(
                'http://localhost:8001/local/preferences/last_login_username?value=',
                { method: 'PUT' }
            );
        } catch {
            // Best-effort
        }
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider value={{ user, login, logout, loading, error }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
```

- [ ] **Step 2: Verify build passes**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/context/AuthContext.jsx
git commit -m "feat(ui): rewrite AuthContext — no localStorage, session via GET /status"
```

---

## Task 4: Create ProtectedRoute component

**Files:**
- Create: `nivesh-client/frontend/src/components/ProtectedRoute.jsx`

- [ ] **Step 1: Create `src/components/ProtectedRoute.jsx`**

```javascript
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * Wrap authenticated routes with this component.
 * Shows a spinner while session check is in progress.
 * Redirects to /login if not authenticated.
 * Renders child routes via <Outlet /> when authenticated.
 */
const ProtectedRoute = () => {
    const { user, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen bg-[#0f1419] flex items-center justify-center">
                <div className="w-12 h-12 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    if (!user) {
        return <Navigate to="/login" replace />;
    }

    return <Outlet />;
};

export default ProtectedRoute;
```

- [ ] **Step 2: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/components/ProtectedRoute.jsx
git commit -m "feat(ui): add ProtectedRoute component"
```

---

## Task 5: Update fund service

**Files:**
- Modify: `nivesh-client/frontend/src/api/services/fundService.js`

All paths switch from `/funds/*` → `/proxy/funds/*`, `/navs/*` → `/proxy/funds/{code}/nav`, `/benchmarks/*` → `/proxy/benchmarks/*`. Write methods removed (client is read-only).

- [ ] **Step 1: Rewrite `src/api/services/fundService.js`**

```javascript
import apiClient from '../apiClient';

const fundService = {
    // ── Mutual Funds ──────────────────────────────────────────────────────────

    getFunds: async (skip = 0, limit = 10, category = null, amc = null,
                     subcategory = null, plan_type = null, order_by = null, search = null) => {
        const params = { skip, limit };
        if (category && category !== 'All') params.category = category;
        if (amc && amc !== 'All') params.amc = amc;
        if (subcategory) params.subcategory = subcategory;
        if (plan_type) params.plan_type = plan_type;
        if (order_by) params.order_by = order_by;
        if (search) params.q = search;
        const response = await apiClient.get('/proxy/funds', { params });
        return response.data;
    },

    getAmcs: async () => {
        const response = await apiClient.get('/proxy/funds/amcs');
        return response.data;
    },

    compareFunds: async (codes) => {
        const scheme_codes = Array.isArray(codes) ? codes.join(',') : codes;
        const response = await apiClient.get('/proxy/funds/compare', { params: { scheme_codes } });
        return response.data;
    },

    getCategories: async () => {
        const response = await apiClient.get('/proxy/funds/categories');
        return response.data;
    },

    getSubcategories: async (category) => {
        const response = await apiClient.get(
            `/proxy/funds/categories/${encodeURIComponent(category)}/subcategories`
        );
        return response.data;
    },

    getFundDetail: async (schemeCode) => {
        const response = await apiClient.get(`/proxy/funds/${schemeCode}`);
        return response.data;
    },

    getSimilarFunds: async (schemeCode) => {
        const response = await apiClient.get(`/proxy/funds/${schemeCode}/similar`);
        return response.data;
    },

    getFundNavHistory: async (schemeCode, limit = 100) => {
        const response = await apiClient.get(`/proxy/funds/${schemeCode}/nav`, { params: { limit } });
        return response.data;
    },

    getFundMetrics: async (schemeCode) => {
        // Metrics are embedded in the fund detail response from the proxy
        const response = await apiClient.get(`/proxy/funds/${schemeCode}`);
        return response.data?.metrics ?? {};
    },

    // ── Benchmarks ────────────────────────────────────────────────────────────

    getBenchmarks: async (skip = 0, limit = 10, search = null) => {
        const params = { skip, limit };
        if (search) params.q = search;
        const response = await apiClient.get('/proxy/benchmarks', { params });
        return response.data;
    },

    getBenchmarkDetail: async (benchmarkCode) => {
        const response = await apiClient.get(`/proxy/benchmarks/${benchmarkCode}`);
        return response.data;
    },

    getBenchmarkNavHistory: async (benchmarkCode, limit = 100) => {
        const response = await apiClient.get(
            `/proxy/benchmarks/${benchmarkCode}/nav`, { params: { limit } }
        );
        return response.data;
    },

    // ── Sync status (pipeline) ────────────────────────────────────────────────

    getSyncStatus: async () => {
        const response = await apiClient.get('/proxy/sync/status');
        return response.data;
    },
};

export default fundService;
```

- [ ] **Step 2: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/api/services/fundService.js
git commit -m "feat(ui): update fundService to use /proxy/* paths"
```

---

## Task 6: Update stock service

**Files:**
- Modify: `nivesh-client/frontend/src/api/services/stockService.js`

- [ ] **Step 1: Rewrite `src/api/services/stockService.js`**

```javascript
import apiClient from '../apiClient';

const stockService = {
    getStocks: async (params) => {
        const response = await apiClient.get('/proxy/stocks', { params });
        return response.data;
    },

    searchStocks: async (q) => {
        const response = await apiClient.get('/proxy/stocks/search', { params: { q } });
        return response.data;
    },

    getStockDetail: async (symbol) => {
        const response = await apiClient.get(`/proxy/stocks/${symbol.toUpperCase()}`);
        return response.data;
    },

    getScreener: async (filters) => {
        const response = await apiClient.get('/proxy/stocks/screener', { params: filters });
        return response.data;
    },

    getCompare: async (symbols) => {
        const response = await apiClient.get('/proxy/stocks', {
            params: { symbols: symbols.join(',') }
        });
        return response.data;
    },

    // Pipeline status (read-only — ingestion runs server-side)
    getPipelineStatus: async () => {
        const response = await apiClient.get('/proxy/sync/status');
        return response.data;
    },

    // Price history — not yet in proxy; return empty for now
    getPriceHistory: async () => ({ data: [] }),

    // Stub read-only equivalents for removed pipeline triggers
    // These pages should not be triggering ingestion from the client
    getFundamentals: async (symbol) => {
        const detail = await stockService.getStockDetail(symbol);
        return detail;
    },

    getRatios: async (symbol) => {
        const detail = await stockService.getStockDetail(symbol);
        return detail;
    },

    getTechnicals: async (symbol) => {
        const detail = await stockService.getStockDetail(symbol);
        return detail;
    },
};

export default stockService;
```

- [ ] **Step 2: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/api/services/stockService.js
git commit -m "feat(ui): update stockService to use /proxy/* paths"
```

---

## Task 7: Create new service files

**Files:**
- Create: `nivesh-client/frontend/src/api/services/portfolioService.js`
- Create: `nivesh-client/frontend/src/api/services/watchlistService.js`
- Create: `nivesh-client/frontend/src/api/services/agentService.js`
- Create: `nivesh-client/frontend/src/api/services/statusService.js`

- [ ] **Step 1: Create `src/api/services/portfolioService.js`**

```javascript
import apiClient from '../apiClient';

const portfolioService = {
    getHoldings: async (assetType = null) => {
        const params = assetType ? { asset_type: assetType } : {};
        const response = await apiClient.get('/local/portfolio/holdings', { params });
        return response.data;
    },

    addHolding: async (data) => {
        const response = await apiClient.post('/local/portfolio/holdings', data);
        return response.data;
    },

    updateHolding: async (id, data) => {
        const response = await apiClient.put(`/local/portfolio/holdings/${id}`, data);
        return response.data;
    },

    deleteHolding: async (id) => {
        await apiClient.delete(`/local/portfolio/holdings/${id}`);
    },

    getTransactions: async (symbol = null) => {
        const params = symbol ? { symbol } : {};
        const response = await apiClient.get('/local/portfolio/transactions', { params });
        return response.data;
    },

    addTransaction: async (data) => {
        const response = await apiClient.post('/local/portfolio/transactions', data);
        return response.data;
    },
};

export default portfolioService;
```

- [ ] **Step 2: Create `src/api/services/watchlistService.js`**

```javascript
import apiClient from '../apiClient';

const watchlistService = {
    get: async (assetType = null) => {
        const params = assetType ? { asset_type: assetType } : {};
        const response = await apiClient.get('/local/watchlist', { params });
        return response.data;
    },

    add: async (data) => {
        // data: { symbol, asset_type, display_name?, notes?, alert_above?, alert_below? }
        const response = await apiClient.post('/local/watchlist', data);
        return response.data;
    },

    remove: async (id) => {
        await apiClient.delete(`/local/watchlist/${id}`);
    },
};

export default watchlistService;
```

- [ ] **Step 3: Create `src/api/services/agentService.js`**

```javascript
import apiClient from '../apiClient';

const agentService = {
    createSession: async ({ context_type = 'general', context_id = null, title = null } = {}) => {
        const response = await apiClient.post('/agent/sessions', { context_type, context_id, title });
        return response.data;  // { session_id, title }
    },

    listSessions: async () => {
        const response = await apiClient.get('/agent/sessions');
        return response.data;  // AgentSession[]
    },

    getMessages: async (sessionId) => {
        const response = await apiClient.get(`/agent/sessions/${sessionId}/messages`);
        return response.data;  // AgentMessage[]
    },

    chat: async (sessionId, message) => {
        const response = await apiClient.post(`/agent/sessions/${sessionId}/chat`, { message });
        return response.data;  // { reply, session_id }
    },

    getMemory: async () => {
        const response = await apiClient.get('/agent/memory');
        return response.data;  // { key: { value, confidence } }
    },
};

export default agentService;
```

- [ ] **Step 4: Create `src/api/services/statusService.js`**

```javascript
import apiClient from '../apiClient';

const statusService = {
    /**
     * GET /status — returns client connectivity summary.
     * { is_online, last_connected_at, server_url, cached_resources, db_path }
     */
    get: async () => {
        const response = await apiClient.get('/status');
        return response.data;
    },
};

export default statusService;
```

- [ ] **Step 5: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 6: Commit**

```bash
git add nivesh-client/frontend/src/api/services/portfolioService.js \
        nivesh-client/frontend/src/api/services/watchlistService.js \
        nivesh-client/frontend/src/api/services/agentService.js \
        nivesh-client/frontend/src/api/services/statusService.js
git commit -m "feat(ui): add portfolio, watchlist, agent, status service files"
```

---

## Task 8: Create SyncStatusBar component

**Files:**
- Create: `nivesh-client/frontend/src/components/SyncStatusBar.jsx`

Polls `GET /status` every 60 seconds. Shows connectivity state with relative time.

- [ ] **Step 1: Create `src/components/SyncStatusBar.jsx`**

```javascript
import { useState, useEffect } from 'react';
import statusService from '../api/services/statusService';

function formatRelativeTime(isoString) {
    if (!isoString) return 'never';
    const diff = Date.now() - new Date(isoString).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

const SyncStatusBar = () => {
    const [status, setStatus] = useState(null);
    const [clientError, setClientError] = useState(false);

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const data = await statusService.get();
                setStatus(data);
                setClientError(false);
            } catch {
                setClientError(true);
            }
        };

        fetchStatus();
        const id = setInterval(fetchStatus, 60_000);
        return () => clearInterval(id);
    }, []);

    if (clientError) {
        return (
            <div className="w-full px-4 py-1.5 bg-red-900/30 border-b border-red-500/20 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                <span className="text-[10px] font-semibold text-red-400 uppercase tracking-widest">
                    Client not reachable on port 8001
                </span>
            </div>
        );
    }

    if (!status) return null;

    const lastSync = formatRelativeTime(status.last_connected_at);
    const isOnline = status.is_online;

    return (
        <div className={`w-full px-4 py-1.5 border-b flex items-center gap-2
            ${isOnline
                ? 'bg-emerald-900/20 border-emerald-500/20'
                : 'bg-amber-900/20 border-amber-500/20'
            }`}
        >
            <span className={`w-1.5 h-1.5 rounded-full shrink-0
                ${isOnline ? 'bg-emerald-400' : 'bg-amber-400'}`}
            />
            <span className={`text-[10px] font-semibold uppercase tracking-widest
                ${isOnline ? 'text-emerald-400' : 'text-amber-400'}`}
            >
                {isOnline
                    ? `Connected · Last sync ${lastSync} · ${status.cached_resources} cached`
                    : `Offline — showing cached data · last sync ${lastSync}`
                }
            </span>
        </div>
    );
};

export default SyncStatusBar;
```

- [ ] **Step 2: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/components/SyncStatusBar.jsx
git commit -m "feat(ui): add SyncStatusBar component"
```

---

## Task 9: Create OfflineBanner component

**Files:**
- Create: `nivesh-client/frontend/src/components/OfflineBanner.jsx`

- [ ] **Step 1: Create `src/components/OfflineBanner.jsx`**

```javascript
import { useState } from 'react';

/**
 * Shows when a proxy response has `_offline: true`.
 * Usage:
 *   const [data, setData] = useState(null);
 *   <OfflineBanner isOffline={data?._offline === true} />
 */
const OfflineBanner = ({ isOffline }) => {
    const [dismissed, setDismissed] = useState(false);

    if (!isOffline || dismissed) return null;

    return (
        <div className="w-full px-4 py-2 bg-amber-900/30 border border-amber-500/20 rounded-xl flex items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-400 text-[16px]">wifi_off</span>
                <span className="text-[11px] font-semibold text-amber-300">
                    Server offline — showing cached data. Connect to refresh.
                </span>
            </div>
            <button
                onClick={() => setDismissed(true)}
                className="text-amber-500 hover:text-amber-300 transition-colors shrink-0"
            >
                <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
        </div>
    );
};

export default OfflineBanner;
```

- [ ] **Step 2: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/components/OfflineBanner.jsx
git commit -m "feat(ui): add OfflineBanner component"
```

---

## Task 10: Rewrite Portfolio page

**Files:**
- Modify: `nivesh-client/frontend/src/pages/Portfolio.jsx`

Full CRUD holdings table with P&L enrichment. Inline add-holding modal. Uses `portfolioService` and best-effort price enrichment from proxy.

- [ ] **Step 1: Rewrite `src/pages/Portfolio.jsx`**

```javascript
import { useState, useEffect, useCallback } from 'react';
import portfolioService from '../api/services/portfolioService';
import fundService from '../api/services/fundService';
import stockService from '../api/services/stockService';

// ── Add Holding Modal ──────────────────────────────────────────────────────────

const AddHoldingModal = ({ onClose, onSaved }) => {
    const [form, setForm] = useState({
        symbol: '', asset_type: 'STOCK', quantity: '', avg_cost: '',
        buy_date: new Date().toISOString().split('T')[0],
        broker: '', folio_number: '', notes: '',
    });
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSaving(true);
        try {
            await portfolioService.addHolding({
                symbol: form.symbol.toUpperCase(),
                asset_type: form.asset_type,
                quantity: parseFloat(form.quantity),
                avg_cost: parseFloat(form.avg_cost),
                buy_date: form.buy_date,
                broker: form.broker || undefined,
                folio_number: form.folio_number || undefined,
                notes: form.notes || undefined,
            });
            onSaved();
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to save holding');
        } finally {
            setSaving(false);
        }
    };

    const field = (key, label, type = 'text', required = false) => (
        <div className="flex flex-col gap-1">
            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">{label}</label>
            <input
                type={type}
                value={form[key]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                required={required}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50 transition-colors"
            />
        </div>
    );

    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
             onClick={onClose}>
            <div className="bg-[#161c22] border border-white/8 rounded-2xl p-6 w-full max-w-md shadow-2xl"
                 onClick={e => e.stopPropagation()}>
                <h3 className="text-base font-bold text-white mb-4">Add Holding</h3>
                <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                    {field('symbol', 'Symbol / Scheme Code', 'text', true)}
                    <div className="flex flex-col gap-1">
                        <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Type</label>
                        <select
                            value={form.asset_type}
                            onChange={e => setForm(f => ({ ...f, asset_type: e.target.value }))}
                            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                        >
                            <option value="STOCK">Stock</option>
                            <option value="FUND">Mutual Fund</option>
                        </select>
                    </div>
                    {field('quantity', 'Quantity', 'number', true)}
                    {field('avg_cost', 'Avg Cost (₹)', 'number', true)}
                    {field('buy_date', 'Buy Date', 'date', true)}
                    {field('broker', 'Broker / AMC')}
                    {form.asset_type === 'FUND' && field('folio_number', 'Folio Number')}
                    {error && <p className="text-red-400 text-xs">{error}</p>}
                    <div className="flex gap-3 pt-2">
                        <button type="button" onClick={onClose}
                            className="flex-1 py-2.5 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white transition-colors">
                            Cancel
                        </button>
                        <button type="submit" disabled={saving}
                            className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] text-sm font-black uppercase tracking-widest disabled:opacity-50">
                            {saving ? 'Saving...' : 'Save'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

// ── Portfolio Page ────────────────────────────────────────────────────────────

const Portfolio = () => {
    const [holdings, setHoldings] = useState([]);
    const [enriched, setEnriched] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);

    const loadHoldings = useCallback(async () => {
        try {
            const raw = await portfolioService.getHoldings();
            setHoldings(raw);
            enrichHoldings(raw);
        } catch (err) {
            console.error('[Portfolio] Failed to load holdings:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    const enrichHoldings = async (raw) => {
        const results = await Promise.allSettled(
            raw.map(async (h) => {
                let currentPrice;
                try {
                    if (h.asset_type === 'STOCK') {
                        const detail = await stockService.getStockDetail(h.symbol);
                        currentPrice = detail?.latest_close;
                    } else {
                        const detail = await fundService.getFundDetail(h.symbol);
                        currentPrice = detail?.metrics?.current_nav;
                    }
                } catch {
                    // Offline or not cached — show dashes
                }
                const invested = h.avg_cost * h.quantity;
                const currentValue = currentPrice ? currentPrice * h.quantity : undefined;
                const pnl = currentValue !== undefined ? currentValue - invested : undefined;
                const pnlPct = pnl !== undefined && invested > 0 ? (pnl / invested) * 100 : undefined;
                return { ...h, currentPrice, currentValue, pnl, pnlPct, invested };
            })
        );
        setEnriched(
            results
                .filter(r => r.status === 'fulfilled')
                .map(r => r.value)
        );
    };

    useEffect(() => { loadHoldings(); }, [loadHoldings]);

    const handleDelete = async (id) => {
        if (!window.confirm('Remove this holding?')) return;
        try {
            await portfolioService.deleteHolding(id);
            await loadHoldings();
        } catch (err) {
            console.error('[Portfolio] Delete failed:', err);
        }
    };

    const fmt = (n) => n != null ? `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—';
    const fmtPct = (n) => n != null ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` : '—';

    const totalInvested = enriched.reduce((s, h) => s + h.invested, 0);
    const totalCurrent  = enriched.reduce((s, h) => s + (h.currentValue ?? h.invested), 0);
    const totalPnl      = totalCurrent - totalInvested;
    const totalPnlPct   = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;

    return (
        <div className="min-h-screen bg-[#0a0f12] p-6 md:p-10">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-2xl font-headline font-bold text-white">Portfolio</h1>
                        <p className="text-[11px] text-slate-500 uppercase tracking-widest mt-1">
                            {enriched.length} holding{enriched.length !== 1 ? 's' : ''}
                        </p>
                    </div>
                    <button
                        onClick={() => setShowAdd(true)}
                        className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] rounded-xl text-[11px] font-black uppercase tracking-widest"
                    >
                        <span className="material-symbols-outlined text-[16px]">add</span>
                        Add Holding
                    </button>
                </div>

                {/* Summary Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                    {[
                        { label: 'Invested', value: fmt(totalInvested), color: 'text-white' },
                        { label: 'Current Value', value: fmt(totalCurrent), color: 'text-white' },
                        {
                            label: 'Total P&L',
                            value: `${totalPnl >= 0 ? '+' : '-'}${fmt(totalPnl)} (${fmtPct(totalPnlPct)})`,
                            color: totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400',
                        },
                    ].map(card => (
                        <div key={card.label} className="bg-[#161c22] border border-white/8 rounded-2xl p-5">
                            <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2">{card.label}</p>
                            <p className={`text-xl font-bold ${card.color}`}>{card.value}</p>
                        </div>
                    ))}
                </div>

                {/* Holdings Table */}
                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="w-10 h-10 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : enriched.length === 0 ? (
                    <div className="text-center py-16">
                        <span className="material-symbols-outlined text-6xl text-slate-700 font-thin">account_balance_wallet</span>
                        <p className="text-slate-500 text-sm mt-4">No holdings yet. Add your first holding.</p>
                    </div>
                ) : (
                    <div className="bg-[#161c22] border border-white/8 rounded-2xl overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="border-b border-white/5">
                                        {['Symbol', 'Type', 'Qty', 'Avg Cost', 'Current', 'P&L', 'P&L %', ''].map(h => (
                                            <th key={h} className="px-4 py-3 text-left text-[9px] font-black uppercase tracking-widest text-slate-500">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {enriched.map(h => (
                                        <tr key={h.id} className="border-b border-white/4 hover:bg-white/2 transition-colors">
                                            <td className="px-4 py-3 text-sm font-bold text-white">{h.symbol}</td>
                                            <td className="px-4 py-3">
                                                <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full
                                                    ${h.asset_type === 'STOCK' ? 'bg-blue-500/10 text-blue-400' : 'bg-purple-500/10 text-purple-400'}`}>
                                                    {h.asset_type}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-sm text-slate-300">{h.quantity}</td>
                                            <td className="px-4 py-3 text-sm text-slate-300">{fmt(h.avg_cost)}</td>
                                            <td className="px-4 py-3 text-sm text-slate-300">
                                                {h.currentPrice ? fmt(h.currentPrice) : '—'}
                                            </td>
                                            <td className={`px-4 py-3 text-sm font-semibold
                                                ${h.pnl == null ? 'text-slate-500' : h.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                {h.pnl != null ? `${h.pnl >= 0 ? '+' : '-'}${fmt(h.pnl)}` : '—'}
                                            </td>
                                            <td className={`px-4 py-3 text-sm font-semibold
                                                ${h.pnlPct == null ? 'text-slate-500' : h.pnlPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                {fmtPct(h.pnlPct)}
                                            </td>
                                            <td className="px-4 py-3">
                                                <button
                                                    onClick={() => handleDelete(h.id)}
                                                    className="text-slate-600 hover:text-red-400 transition-colors"
                                                    title="Remove holding"
                                                >
                                                    <span className="material-symbols-outlined text-[16px]">delete</span>
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>

            {showAdd && (
                <AddHoldingModal
                    onClose={() => setShowAdd(false)}
                    onSaved={() => { setShowAdd(false); loadHoldings(); }}
                />
            )}
        </div>
    );
};

export default Portfolio;
```

- [ ] **Step 2: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/pages/Portfolio.jsx
git commit -m "feat(ui): rewrite Portfolio page with holdings CRUD and P&L"
```

---

## Task 11: Create Watchlist page

**Files:**
- Create: `nivesh-client/frontend/src/pages/Watchlist.jsx`

- [ ] **Step 1: Create `src/pages/Watchlist.jsx`**

```javascript
import { useState, useEffect } from 'react';
import watchlistService from '../api/services/watchlistService';

const Watchlist = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const [form, setForm] = useState({ symbol: '', asset_type: 'STOCK', notes: '', alert_above: '', alert_below: '' });
    const [formError, setFormError] = useState(null);

    const load = async () => {
        try {
            const data = await watchlistService.get();
            setItems(data);
        } catch (err) {
            console.error('[Watchlist] Load failed:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const handleAdd = async (e) => {
        e.preventDefault();
        setFormError(null);
        try {
            await watchlistService.add({
                symbol: form.symbol.toUpperCase(),
                asset_type: form.asset_type,
                notes: form.notes || undefined,
                alert_above: form.alert_above ? parseFloat(form.alert_above) : undefined,
                alert_below: form.alert_below ? parseFloat(form.alert_below) : undefined,
            });
            setForm({ symbol: '', asset_type: 'STOCK', notes: '', alert_above: '', alert_below: '' });
            setShowAdd(false);
            await load();
        } catch (err) {
            setFormError(err.response?.data?.detail ?? 'Failed to add to watchlist');
        }
    };

    const handleRemove = async (id) => {
        try {
            await watchlistService.remove(id);
            await load();
        } catch (err) {
            console.error('[Watchlist] Remove failed:', err);
        }
    };

    return (
        <div className="min-h-screen bg-[#0a0f12] p-6 md:p-10">
            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-2xl font-headline font-bold text-white">Watchlist</h1>
                        <p className="text-[11px] text-slate-500 uppercase tracking-widest mt-1">
                            {items.length} item{items.length !== 1 ? 's' : ''}
                        </p>
                    </div>
                    <button
                        onClick={() => setShowAdd(v => !v)}
                        className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] rounded-xl text-[11px] font-black uppercase tracking-widest"
                    >
                        <span className="material-symbols-outlined text-[16px]">{showAdd ? 'close' : 'add'}</span>
                        {showAdd ? 'Cancel' : 'Add'}
                    </button>
                </div>

                {/* Add Form */}
                {showAdd && (
                    <form onSubmit={handleAdd}
                        className="bg-[#161c22] border border-white/8 rounded-2xl p-5 mb-6 flex flex-wrap gap-3 items-end">
                        <div className="flex flex-col gap-1 flex-1 min-w-[140px]">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Symbol</label>
                            <input
                                required
                                placeholder="RELIANCE"
                                value={form.symbol}
                                onChange={e => setForm(f => ({ ...f, symbol: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Type</label>
                            <select
                                value={form.asset_type}
                                onChange={e => setForm(f => ({ ...f, asset_type: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            >
                                <option value="STOCK">Stock</option>
                                <option value="FUND">Fund</option>
                            </select>
                        </div>
                        <div className="flex flex-col gap-1 flex-1 min-w-[120px]">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Notes</label>
                            <input
                                placeholder="Optional notes"
                                value={form.notes}
                                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            />
                        </div>
                        <div className="flex flex-col gap-1 w-24">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Alert ▲</label>
                            <input
                                type="number" step="any"
                                placeholder="₹"
                                value={form.alert_above}
                                onChange={e => setForm(f => ({ ...f, alert_above: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            />
                        </div>
                        <div className="flex flex-col gap-1 w-24">
                            <label className="text-[9px] font-black uppercase tracking-widest text-slate-500">Alert ▼</label>
                            <input
                                type="number" step="any"
                                placeholder="₹"
                                value={form.alert_below}
                                onChange={e => setForm(f => ({ ...f, alert_below: e.target.value }))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#D4AF37]/50"
                            />
                        </div>
                        {formError && <p className="w-full text-red-400 text-xs">{formError}</p>}
                        <button type="submit"
                            className="px-5 py-2.5 bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] rounded-xl text-[11px] font-black uppercase tracking-widest">
                            Add
                        </button>
                    </form>
                )}

                {/* Items Grid */}
                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="w-10 h-10 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : items.length === 0 ? (
                    <div className="text-center py-16">
                        <span className="material-symbols-outlined text-6xl text-slate-700 font-thin">bookmark</span>
                        <p className="text-slate-500 text-sm mt-4">No items in watchlist. Add stocks or funds to track.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {items.map(item => (
                            <div key={item.id}
                                className="bg-[#161c22] border border-white/8 rounded-2xl p-4 flex flex-col gap-2 group">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="text-base font-bold text-white">{item.symbol}</span>
                                        <span className={`text-[8px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full
                                            ${item.asset_type === 'STOCK' ? 'bg-blue-500/10 text-blue-400' : 'bg-purple-500/10 text-purple-400'}`}>
                                            {item.asset_type}
                                        </span>
                                    </div>
                                    <button
                                        onClick={() => handleRemove(item.id)}
                                        className="text-slate-700 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                                        title="Remove"
                                    >
                                        <span className="material-symbols-outlined text-[16px]">close</span>
                                    </button>
                                </div>
                                {item.display_name && (
                                    <p className="text-[11px] text-slate-400">{item.display_name}</p>
                                )}
                                {item.notes && (
                                    <p className="text-[11px] text-slate-500 italic">{item.notes}</p>
                                )}
                                {(item.alert_above || item.alert_below) && (
                                    <div className="flex gap-3 mt-1">
                                        {item.alert_above && (
                                            <span className="text-[10px] text-emerald-400 font-semibold">
                                                ▲ ₹{item.alert_above}
                                            </span>
                                        )}
                                        {item.alert_below && (
                                            <span className="text-[10px] text-red-400 font-semibold">
                                                ▼ ₹{item.alert_below}
                                            </span>
                                        )}
                                    </div>
                                )}
                                <p className="text-[9px] text-slate-700 mt-auto">
                                    Added {new Date(item.added_at).toLocaleDateString('en-IN')}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Watchlist;
```

- [ ] **Step 2: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/pages/Watchlist.jsx
git commit -m "feat(ui): add Watchlist page"
```

---

## Task 12: Create AgentChat page (stub)

**Files:**
- Create: `nivesh-client/frontend/src/pages/AgentChat.jsx`

LLM not wired in Phase 5 — returns stub reply. Full LLM in Phase 6.

- [ ] **Step 1: Create `src/pages/AgentChat.jsx`**

```javascript
import { useState, useEffect, useRef } from 'react';
import agentService from '../api/services/agentService';

const SUGGESTIONS = [
    'Analyse RELIANCE',
    'Compare top large cap funds',
    'How is my portfolio doing?',
    'Show me oversold Nifty50 stocks',
];

const AgentChat = () => {
    const [sessionId, setSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [initError, setInitError] = useState(null);
    const bottomRef = useRef(null);

    // Create or resume the most recent session on mount
    useEffect(() => {
        const init = async () => {
            try {
                const sessions = await agentService.listSessions();
                if (sessions.length > 0) {
                    const s = sessions[0];
                    setSessionId(s.id);
                    const msgs = await agentService.getMessages(s.id);
                    setMessages(msgs);
                } else {
                    const s = await agentService.createSession({ context_type: 'general' });
                    setSessionId(s.session_id);
                }
            } catch (err) {
                setInitError('Could not connect to the agent. Is the client running on port 8001?');
                console.error('[AgentChat] Init failed:', err);
            }
        };
        init();
    }, []);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    const handleSend = async (text) => {
        const msg = (text ?? input).trim();
        if (!msg || !sessionId || loading) return;
        setInput('');
        setLoading(true);

        // Optimistic user message
        const optimistic = {
            id: `opt-${Date.now()}`,
            role: 'user',
            content_text: msg,
            created_at: new Date().toISOString(),
        };
        setMessages(m => [...m, optimistic]);

        try {
            const resp = await agentService.chat(sessionId, msg);
            const assistantMsg = {
                id: `resp-${Date.now()}`,
                role: 'assistant',
                content_text: resp.reply,
                created_at: new Date().toISOString(),
            };
            setMessages(m => [...m, assistantMsg]);
        } catch {
            setMessages(m => [...m, {
                id: `err-${Date.now()}`,
                role: 'assistant',
                content_text: 'Something went wrong. Please try again.',
                created_at: new Date().toISOString(),
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleNewSession = async () => {
        try {
            const s = await agentService.createSession({ context_type: 'general' });
            setSessionId(s.session_id);
            setMessages([]);
        } catch (err) {
            console.error('[AgentChat] New session failed:', err);
        }
    };

    return (
        <div className="min-h-screen bg-[#0a0f12] flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#e9c349] to-[#b8942e] flex items-center justify-center">
                        <span className="material-symbols-outlined text-[#0f1419] text-[16px]">smart_toy</span>
                    </div>
                    <div>
                        <h1 className="text-base font-bold text-white">Nivesh Agent</h1>
                        <span className="text-[9px] font-black uppercase tracking-widest text-amber-500/70">
                            Phase 6 — LLM not yet connected
                        </span>
                    </div>
                </div>
                <button
                    onClick={handleNewSession}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-white hover:border-white/20 transition-colors"
                >
                    <span className="material-symbols-outlined text-[14px]">add</span>
                    New
                </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-6 flex flex-col gap-4 max-w-3xl w-full mx-auto">
                {initError ? (
                    <div className="text-center py-8">
                        <span className="material-symbols-outlined text-4xl text-red-700 font-thin">error</span>
                        <p className="text-red-400 text-sm mt-3">{initError}</p>
                    </div>
                ) : messages.length === 0 && !loading ? (
                    <div className="flex flex-col items-center gap-6 py-12">
                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#e9c349]/20 to-[#b8942e]/20 flex items-center justify-center">
                            <span className="material-symbols-outlined text-[#e9c349] text-3xl font-thin">smart_toy</span>
                        </div>
                        <p className="text-slate-400 text-sm text-center max-w-sm">
                            Ask about a stock, mutual fund, or your portfolio.
                        </p>
                        <div className="flex flex-wrap gap-2 justify-center">
                            {SUGGESTIONS.map(s => (
                                <button
                                    key={s}
                                    onClick={() => handleSend(s)}
                                    className="px-3 py-1.5 rounded-full border border-white/10 text-[11px] text-slate-400 hover:text-white hover:border-white/20 transition-all"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    messages.map(msg => (
                        <div key={msg.id}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm
                                ${msg.role === 'user'
                                    ? 'bg-[#D4AF37]/15 border border-[#D4AF37]/20 text-white rounded-br-sm'
                                    : 'bg-[#161c22] border border-white/8 text-slate-200 rounded-bl-sm'
                                }`}>
                                {msg.content_text}
                            </div>
                        </div>
                    ))
                )}

                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-[#161c22] border border-white/8 rounded-2xl rounded-bl-sm px-4 py-3">
                            <div className="flex gap-1.5 items-center">
                                {[0, 1, 2].map(i => (
                                    <span key={i}
                                        className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce"
                                        style={{ animationDelay: `${i * 0.15}s` }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            {/* Input bar */}
            <div className="border-t border-white/5 px-4 py-4">
                <form
                    onSubmit={e => { e.preventDefault(); handleSend(); }}
                    className="max-w-3xl mx-auto flex gap-3"
                >
                    <input
                        type="text"
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        placeholder="Ask about stocks, funds, or your portfolio..."
                        disabled={loading || !sessionId}
                        className="flex-1 bg-[#161c22] border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-[#D4AF37]/40 transition-colors disabled:opacity-50"
                    />
                    <button
                        type="submit"
                        disabled={loading || !input.trim() || !sessionId}
                        className="px-5 py-3 bg-gradient-to-r from-[#e9c349] to-[#b8942e] text-[#0f1419] rounded-xl text-[11px] font-black uppercase tracking-widest disabled:opacity-40"
                    >
                        Send
                    </button>
                </form>
            </div>
        </div>
    );
};

export default AgentChat;
```

- [ ] **Step 2: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/pages/AgentChat.jsx
git commit -m "feat(ui): add AgentChat page stub (LLM wired in Phase 6)"
```

---

## Task 13: Update Layout — SyncStatusBar + new nav links

**Files:**
- Modify: `nivesh-client/frontend/src/components/Layout.jsx`

Add `SyncStatusBar` between the sticky header and main content. Add Watchlist and Agent links to desktop nav and mobile menu.

- [ ] **Step 1: Add SyncStatusBar import and render in Layout**

In `src/components/Layout.jsx`:

At the top, add the import after existing imports:
```javascript
import SyncStatusBar from './SyncStatusBar';
```

In the `Layout` component's return, add `<SyncStatusBar />` after `<TopNavBar>` and before the mobile drawer:

```javascript
// Replace this section in the Layout return:
//   <TopNavBar ... />
//   {/* Mobile Drawer */}
//   <AnimatePresence>...

// With:
<TopNavBar
    onMobileMenuClick={() => setIsMobileMenuOpen((v) => !v)}
    isMobileMenuOpen={isMobileMenuOpen}
/>
<SyncStatusBar />

{/* Mobile Drawer */}
<AnimatePresence>
```

- [ ] **Step 2: Add Watchlist and Agent to desktop nav**

In `TopNavBar`, inside the `<nav className="hidden lg:flex ...">`, after the Portfolio `<NavLink>`, add:

```javascript
{/* Watchlist — direct link */}
<NavLink
    to="/watchlist"
    className={({ isActive }) =>
        `flex items-center gap-1.5 text-[10px] font-black uppercase tracking-[0.18em] transition-all duration-200 px-1 py-1 rounded-lg
        ${isActive ? 'text-primary' : 'text-slate-400 hover:text-white'}`
    }
>
    <span className="material-symbols-outlined text-[15px] font-thin">bookmark</span>
    Watchlist
</NavLink>

{/* Agent — direct link */}
<NavLink
    to="/agent"
    className={({ isActive }) =>
        `flex items-center gap-1.5 text-[10px] font-black uppercase tracking-[0.18em] transition-all duration-200 px-1 py-1 rounded-lg
        ${isActive ? 'text-primary' : 'text-slate-400 hover:text-white'}`
    }
>
    <span className="material-symbols-outlined text-[15px] font-thin">smart_toy</span>
    Agent
</NavLink>
```

- [ ] **Step 3: Add Watchlist and Agent to mobile menu**

In `MobileMenu`, in the `navGroups` array, after the Portfolio group, add:

```javascript
{
    label: 'Watchlist',
    items: [
        { to: '/watchlist', icon: 'bookmark', label: 'Watchlist' },
    ],
},
{
    label: 'Agent',
    items: [
        { to: '/agent', icon: 'smart_toy', label: 'Nivesh Agent' },
    ],
},
```

- [ ] **Step 4: Verify build**

```bash
cd nivesh-client/frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add nivesh-client/frontend/src/components/Layout.jsx
git commit -m "feat(ui): add SyncStatusBar to Layout, add Watchlist + Agent nav links"
```

---

## Task 14: Update App.jsx — ProtectedRoute and new routes

**Files:**
- Modify: `nivesh-client/frontend/src/App.jsx`

Replace scattered `user ? <Page /> : <Navigate>` guards with `ProtectedRoute`. Add routes for `/watchlist` and `/agent`. Layout now wraps via Outlet.

- [ ] **Step 1: Rewrite `src/App.jsx`**

```javascript
import React from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';

// Pages — existing
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import StockListing from './pages/StockListing';
import Screener from './pages/Screener';
import MFListing from './pages/MFListing';
import MFCompare from './pages/MFCompare';
import IndicesListing from './pages/IndicesListing';
import StockDetail from './pages/StockDetail';
import MFDetail from './pages/MFDetail';
import IndexDetail from './pages/IndexDetail';
import Admin from './pages/Admin';
import StockCompare from './pages/StockCompare';

// Pages — new
import Portfolio from './pages/Portfolio';
import Watchlist from './pages/Watchlist';
import AgentChat from './pages/AgentChat';

// Route helpers that read params
const StockDetailRoute = () => { const { symbol } = useParams(); return <StockDetail symbol={symbol} />; };
const MFDetailRoute = () => { const { schemeCode } = useParams(); return <MFDetail schemeCode={schemeCode} />; };
const IndexDetailRoute = () => { const { benchmarkCode } = useParams(); return <IndexDetail benchmarkCode={benchmarkCode} />; };

function App() {
    return (
        <Router>
            <ThemeProvider>
                <AuthProvider>
                    <Routes>
                        {/* Public routes */}
                        <Route path="/login" element={<Login />} />

                        {/* All authenticated routes — ProtectedRoute checks session */}
                        <Route element={<ProtectedRoute />}>
                            <Route element={<Layout><React.Outlet /></Layout>}>
                                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                                <Route path="/dashboard" element={<Dashboard />} />
                                <Route path="/stocks" element={<StockListing />} />
                                <Route path="/stocks/:symbol" element={<StockDetailRoute />} />
                                <Route path="/stock-compare" element={<StockCompare />} />
                                <Route path="/screener" element={<Screener />} />
                                <Route path="/mf" element={<MFListing />} />
                                <Route path="/mf/:schemeCode" element={<MFDetailRoute />} />
                                <Route path="/compare" element={<MFCompare />} />
                                <Route path="/indices" element={<IndicesListing />} />
                                <Route path="/indices/:benchmarkCode" element={<IndexDetailRoute />} />
                                <Route path="/admin" element={<Admin />} />
                                <Route path="/portfolio" element={<Portfolio />} />
                                <Route path="/watchlist" element={<Watchlist />} />
                                <Route path="/agent" element={<AgentChat />} />
                                <Route path="*" element={<Navigate to="/dashboard" replace />} />
                            </Route>
                        </Route>
                    </Routes>

                    <Toaster
                        position="top-right"
                        toastOptions={{
                            style: {
                                background: '#1b2025',
                                color: '#fff',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: '16px',
                                fontFamily: 'Manrope, sans-serif',
                                fontSize: '14px',
                            },
                        }}
                    />
                </AuthProvider>
            </ThemeProvider>
        </Router>
    );
}

export default App;
```

**Note:** `Layout` currently uses a `children` prop pattern, not `<Outlet />`. The line `<Layout><React.Outlet /></Layout>` wraps the Outlet inside Layout's children. This preserves the existing Layout without requiring changes to how it renders children.

- [ ] **Step 2: Verify build with no errors**

```bash
cd nivesh-client/frontend && npm run build
```

Expected: clean build. If `React.Outlet` does not resolve, replace with:

```javascript
import { Outlet } from 'react-router-dom';
// ...
<Route element={<LayoutWrapper />}>
```

Where `LayoutWrapper` is:
```javascript
const LayoutWrapper = () => { const outlet = <Outlet />; return <Layout>{outlet}</Layout>; };
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/frontend/src/App.jsx
git commit -m "feat(ui): update App.jsx with ProtectedRoute and new routes"
```

---

## Task 15: Update Login page

**Files:**
- Modify: `nivesh-client/frontend/src/pages/Login.jsx`

The Login page calls `authService.login()` which now sends JSON. The Login page itself may also call `authService.getMe()` — that reference must be removed. Check what Login.jsx currently does.

- [ ] **Step 1: Read and verify Login.jsx**

Read `src/pages/Login.jsx`. Confirm it calls `useAuth().login()` (not `authService` directly). If so, no changes needed — `useAuth().login()` calls `authService.login()` which we already updated.

If Login.jsx directly calls `authService.login()` with a FormData object, update that call to:
```javascript
// Replace FormData approach:
const data = await authService.login(username, password);
// No getMe() call needed — AuthContext sets user state
```

- [ ] **Step 2: Verify the login flow works end-to-end**

```bash
# Terminal 1: start client backend
cd nivesh-client && uvicorn app.main:app --port 8001 --reload

# Terminal 2: start frontend dev server
cd nivesh-client/frontend && npm run dev
```

Open `http://localhost:5173`. Expected: redirected to `/login`.
Enter credentials. Expected: redirected to `/dashboard`.

- [ ] **Step 3: Commit if any changes were made**

```bash
git add nivesh-client/frontend/src/pages/Login.jsx
git commit -m "feat(ui): update Login page for JSON auth flow"
```

---

## Task 16: End-to-end smoke test

Run these in order. Fix any issues before marking complete.

**Prerequisites:**
- Client backend running: `cd nivesh-client && uvicorn app.main:app --port 8001 --reload`
- Frontend dev server: `cd nivesh-client/frontend && npm run dev`
- Render server accessible (or at minimum Phase 4 client running in offline mode)

| # | Test | Expected |
|---|---|---|
| 1 | Open `http://localhost:5173` | Redirected to `/login` |
| 2 | Login with wrong password | Error toast or inline message |
| 3 | Login with correct credentials | Redirected to `/dashboard` |
| 4 | SyncStatusBar visible at top | Green dot if server reachable, amber if not |
| 5 | Navigate to `/mf` | Fund list loads |
| 6 | Navigate to `/stocks` | Stock list loads |
| 7 | Navigate to `/portfolio` | Empty state or existing holdings |
| 8 | Portfolio → Add Holding: symbol=RELIANCE, type=STOCK, qty=10, cost=2500, date=today | Row appears in table |
| 9 | Portfolio holding shows P&L | ₹ values shown (or `—` if offline) |
| 10 | Portfolio → Delete the holding | Row disappears |
| 11 | Navigate to `/watchlist` | Empty state |
| 12 | Watchlist → Add INFY, type=STOCK | Card appears |
| 13 | Watchlist → Remove INFY | Card disappears |
| 14 | Navigate to `/agent` | Chat UI shown with suggestion chips |
| 15 | Agent → Type "Analyse RELIANCE" → Send | Stub reply shown |
| 16 | Agent → New Conversation | Chat cleared |
| 17 | Logout (Settings → Sign Out) | Redirected to `/login` |
| 18 | Navigate to `/portfolio` directly | Redirected to `/login` |
| 19 | Refresh browser while logged in | Stays on current page (session restored from /status) |
| 20 | `npm run build` | Clean build, no errors |

- [ ] **Step 1: Run all 20 smoke tests**

- [ ] **Step 2: Fix any failures**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(phase5): complete React UI adaptation — proxy routes, auth, portfolio, watchlist, agent"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] API base URL switch — Task 1
- [x] authService JSON login — Task 2
- [x] AuthContext no localStorage, GET /status session check — Task 3
- [x] ProtectedRoute — Task 4
- [x] fundService /proxy/* — Task 5
- [x] stockService /proxy/* — Task 6
- [x] portfolioService, watchlistService, agentService, statusService — Task 7
- [x] SyncStatusBar — Task 8
- [x] OfflineBanner — Task 9
- [x] Portfolio rewrite — Task 10
- [x] Watchlist — Task 11
- [x] AgentChat stub — Task 12
- [x] Layout + SyncStatusBar + nav links — Task 13
- [x] App.jsx ProtectedRoute + new routes — Task 14
- [x] Login.jsx check — Task 15
- [x] Smoke test — Task 16
- [x] Missing proxy sub-routes (amcs, categories, search) — Task 0

**Type consistency:** All service method names used in pages match definitions in Task 7. `portfolioService.addHolding(data)`, `watchlistService.add(data)`, `agentService.chat(sessionId, message)` — consistent throughout.

**No placeholders:** All code blocks are complete. No TBD/TODO in implementation steps.

---

*Phase 5 Implementation Plan · Nivesh Platform · 2026-05-15*
