# Phase 5 — React UI Adaptation Design Spec
**Date:** 2026-05-14
**Status:** Approved

---

## Goal

Adapt the existing React frontend so it talks exclusively to `localhost:8001` (the Phase 4 client) instead of the Render server directly. Add login, sync status bar, offline indicators, portfolio pages, watchlist, and agent chat stub. Wire all existing fund/stock views to the proxy routes.

Phase 5 is **pure React** — no backend changes.

---

## Constraints

- Codebase is **JSX** (not TypeScript) — all new files are `.jsx`
- HTTP client: **axios** via `apiClient.js` — do not introduce native fetch or replace axios
- State: **Redux Toolkit** for existing fund/stock data — unchanged
- New portfolio/watchlist/agent pages use **direct service calls** (no Redux) — these are local CRUD with no cross-page state sharing
- Styling: existing dark Tailwind theme (`bg-[#0f1419]`, `text-primary`, `backdrop-blur`, Framer Motion) — all new components match this aesthetic

---

## Section 1 — HTTP Layer & URL Switch

### `apiClient.js`

Two changes only:

1. `baseURL` → `http://localhost:8001` (drop the `/api/v1` prefix — proxy routes sit at root)
2. Remove the request interceptor that reads `localStorage` and injects `Authorization: Bearer` — the Phase 4 client backend holds tokens in SQLite and injects them server-side; React never touches them
3. Update the 401 response interceptor: instead of `localStorage.removeItem` + redirect, dispatch `new CustomEvent('auth:session-expired')` — `AuthContext` listens and clears auth state

### `.env` update

```
VITE_API_URL=http://localhost:8001
```

### Service path rewrites

All logic is unchanged — only URL prefixes change.

| File | Function | Old path | New path |
|---|---|---|---|
| `fundService.js` | `getFunds` | `/funds/` | `/proxy/funds` |
| `fundService.js` | `getFundDetail` | `/funds/{code}` | `/proxy/funds/{code}` |
| `fundService.js` | `getFundNavHistory` | `/navs/{code}` | `/proxy/funds/{code}/nav` |
| `fundService.js` | `compareFunds` | `/funds/compare?codes=` | `/proxy/funds/compare?scheme_codes=` |
| `fundService.js` | `getBenchmarks` | `/benchmarks/` | `/proxy/benchmarks` |
| `fundService.js` | `getBenchmarkDetail` | `/benchmarks/{code}` | `/proxy/benchmarks/{code}` |
| `fundService.js` | `getBenchmarkNavHistory` | `/benchmark-navs/{code}` | `/proxy/benchmarks/{code}/nav` |
| `stockService.js` | `getStocks` | `/stocks` | `/proxy/stocks` |
| `stockService.js` | `getStockDetail` | `/stocks/{sym}` | `/proxy/stocks/{sym}` |
| `stockService.js` | `getScreener` | `/screener` | `/proxy/stocks/screener` |
| `stockService.js` | `getPipelineStatus` | `/pipeline/status` | `/proxy/sync/status` |

Functions that call server-only endpoints with no proxy equivalent (pipeline triggers, metrics compute, etc.) are **removed or silenced** — they are admin-only operations not exposed through the Phase 4 proxy. The Admin page that uses them can show a "not available in client mode" message.

### `authService.js` rewrite

```js
// OLD: FormData POST to /auth/login + GET /auth/me
// NEW: JSON POST to /auth/login — no /auth/me needed
login: (username, password) =>
  apiClient.post('/auth/login', { username, password })
    .then(r => r.data),

logout: () =>
  apiClient.post('/auth/logout').then(r => r.data),
```

No `getMe` function — the client never fetches user profile from the server. Username is stored in local preferences after login.

### New service files (direct axios calls, no Redux)

**`portfolioService.js`**
- `getHoldings(assetType?)` → `GET /local/portfolio/holdings`
- `addHolding(data)` → `POST /local/portfolio/holdings`
- `updateHolding(id, data)` → `PUT /local/portfolio/holdings/{id}`
- `deleteHolding(id)` → `DELETE /local/portfolio/holdings/{id}`
- `getTransactions(symbol?)` → `GET /local/portfolio/transactions`
- `addTransaction(data)` → `POST /local/portfolio/transactions`

**`watchlistService.js`**
- `getWatchlist(assetType?)` → `GET /local/watchlist`
- `addItem(data)` → `POST /local/watchlist`
- `removeItem(id)` → `DELETE /local/watchlist/{id}`

**`agentService.js`**
- `createSession(data)` → `POST /agent/sessions`
- `listSessions()` → `GET /agent/sessions`
- `getMessages(sessionId)` → `GET /agent/sessions/{id}/messages`
- `chat(sessionId, message)` → `POST /agent/sessions/{id}/chat`
- `getMemory()` → `GET /agent/memory`

**`statusService.js`**
- `getStatus()` → `GET /status`

---

## Section 2 — Auth & State

### `AuthContext.jsx` rewrite

The token pattern changes completely — React never stores or reads a JWT.

| Concern | Old behaviour | New behaviour |
|---|---|---|
| Session check on mount | Read `localStorage.nivesh_token` → call `/auth/me` | Call `GET /status` → if `is_online: true`, already authenticated |
| Login | Store token in `localStorage` | Call `POST /auth/login` (client stores token in SQLite), store username in `PUT /local/preferences/last_login_username` |
| Logout | `localStorage.removeItem` | Call `POST /auth/logout` (client wipes its SQLite token) |
| Context shape | `{ user, login, logout, loading }` | `{ isAuthenticated, username, loading, error, login, logout }` |

Session expiry flow: `apiClient.js` 401 interceptor → `CustomEvent('auth:session-expired')` → `AuthContext` useEffect listener → sets `isAuthenticated: false` → `ProtectedRoute` redirects to `/login`.

### `ProtectedRoute.jsx` (new)

Replaces the inline ternary guards scattered in `App.jsx`. Shows a spinner during `isLoading`, then either renders `<Outlet />` or `<Navigate to="/login" replace />`.

### Redux store

Unchanged. All existing slices (funds, stocks, compare, dashboard, indices) keep working. No new slices.

---

## Section 3 — New Pages & Components

### New components

**`SyncStatusBar.jsx`**
- Fixed strip rendered **above** `TopNavBar` inside `Layout.jsx`
- Polls `GET /status` every 60s via `statusService`
- Online: green dot + "Connected · {N} cached · last sync {X}m ago"
- Offline: amber dot + "Offline — showing cached data"
- Client unreachable: red dot + "Client not running on port 8001"
- Hidden until first status response arrives

**`OfflineBanner.jsx`**
- Inline banner, rendered inside any page receiving `_offline: true` in response data
- Styled as a dismissible warning strip matching existing error states
- Props: `isOffline: bool`, `onDismiss?: fn`

### Rewritten pages

**`Portfolio.jsx`** → replaced with real data

The current `Portfolio.jsx` uses mock/random values from the Redux fund store. It is replaced with a page that:
1. Fetches real holdings from `portfolioService.getHoldings()`
2. Enriches each with current price via proxy (best-effort, falls back to "—" on offline)
3. Shows P&L summary cards (invested, current value, gain/loss ₹ and %)
4. Links to `/portfolio/holdings` and `/portfolio/transactions`
5. Keeps the existing premium dark Tailwind styling

### New pages

**`WatchlistPage.jsx`** (`/watchlist`)
- Grid of cards, each showing symbol, asset type, display name, notes, alert levels
- Inline add-form (symbol, type, notes) toggled by "+ Add" button
- Remove (×) button on each card
- Empty state for zero items

**`AgentChatPage.jsx`** (`/agent`)
- Loads most-recent active session on mount (or creates a new one)
- Message bubbles for user / assistant roles
- Optimistic UI: user message shown immediately before server responds
- Phase 6 badge: "LLM not yet connected" shown in header
- Suggestion chips when chat is empty ("Analyse RELIANCE", etc.)
- "New Conversation" button
- Auto-scroll to bottom on new messages

**`HoldingsPage.jsx`** (`/portfolio/holdings`)
- Table: symbol, type, qty, avg cost, buy date, broker, actions
- "Add Holding" button → `AddHoldingModal.jsx`
- Delete with confirm

**`TransactionsPage.jsx`** (`/portfolio/transactions`)
- Table: symbol, type, txn_type, qty, price, date, amount
- "Add Transaction" button → `AddTransactionModal.jsx`

**`AddHoldingModal.jsx`** / **`AddTransactionModal.jsx`**
- Modal overlays matching the existing modal style in the codebase
- Controlled form, validation, error display

### Layout changes

**`Layout.jsx`** (`TopNavBar` + `MobileMenu`):
- Add `<SyncStatusBar />` above the `<header>` element
- Add "Watchlist" link (icon: `bookmarks`) to desktop nav and mobile drawer
- Add "Agent" link (icon: `smart_toy`) to desktop nav and mobile drawer

**`App.jsx`**:
- Import and use `ProtectedRoute` wrapper
- Replace inline `user ? <Page/> : <Navigate/>` ternaries with clean route structure
- Add new routes: `/watchlist`, `/agent`, `/portfolio/holdings`, `/portfolio/transactions`

---

## Files Changed / Created

### Modified
| File | Change |
|---|---|
| `frontend/.env` | VITE_API_URL → `http://localhost:8001` |
| `src/api/apiClient.js` | baseURL + interceptors |
| `src/api/services/authService.js` | JSON body, remove getMe |
| `src/api/services/fundService.js` | Proxy path prefixes |
| `src/api/services/stockService.js` | Proxy path prefixes |
| `src/context/AuthContext.jsx` | Full rewrite — /status check, no localStorage |
| `src/pages/Portfolio.jsx` | Replace mock data with real holdings |
| `src/components/Layout.jsx` | Add SyncStatusBar, Watchlist, Agent nav links |
| `src/App.jsx` | ProtectedRoute + new routes |

### Created
| File | Purpose |
|---|---|
| `src/api/services/portfolioService.js` | /local/portfolio/* calls |
| `src/api/services/watchlistService.js` | /local/watchlist calls |
| `src/api/services/agentService.js` | /agent/* calls |
| `src/api/services/statusService.js` | GET /status |
| `src/components/ProtectedRoute.jsx` | Auth guard with loading spinner |
| `src/components/SyncStatusBar.jsx` | Online/offline indicator |
| `src/components/OfflineBanner.jsx` | Stale data banner |
| `src/pages/WatchlistPage.jsx` | Watchlist CRUD |
| `src/pages/AgentChatPage.jsx` | Chat UI stub |
| `src/pages/portfolio/HoldingsPage.jsx` | Holdings CRUD table |
| `src/pages/portfolio/TransactionsPage.jsx` | Transactions table |
| `src/pages/portfolio/AddHoldingModal.jsx` | Add holding form |
| `src/pages/portfolio/AddTransactionModal.jsx` | Add transaction form |

---

## Out of Scope

- LLM wiring (Phase 6)
- Admin page proxy equivalents (pipeline triggers have no Phase 4 proxy — Admin page shows "not available in client mode")
- TypeScript migration
- Any backend changes
- `searchStocks` in stockService (no `/proxy/stocks/search` route in Phase 4 — search bar falls back to fund-only or is silenced gracefully)

---

## Definition of Done

- `http://localhost:5173` redirects to `/login` when not authenticated
- Login with correct credentials succeeds and redirects to dashboard
- Login with wrong credentials shows error
- All existing fund list, detail, comparison, benchmark pages load data from proxy
- All existing stock list, detail, screener pages load data from proxy
- `SyncStatusBar` shows green/amber/red state correctly
- Pages with stale cache show `OfflineBanner`
- Portfolio page shows real holdings with P&L
- Holdings CRUD (add + delete) works
- Transactions CRUD (add + view) works
- Watchlist add/remove works
- Agent chat sends message and shows stub reply
- Logout clears auth and redirects to `/login`
- Navigating to `/portfolio` when not logged in redirects to `/login`
