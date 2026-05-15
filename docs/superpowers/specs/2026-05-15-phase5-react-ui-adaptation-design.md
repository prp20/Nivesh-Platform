# Phase 5 — React UI Adaptation Design
## Nivesh Platform · JSX Implementation
### 2026-05-15

---

## Goal

Adapt the existing React frontend (JSX + axios + Redux) to talk exclusively to
`localhost:8001` (the Phase 4 client FastAPI) instead of the server directly.
Fix broken auth assumptions, add sync status indicators, add portfolio/watchlist/
agent pages, and wire all existing fund + stock views through the proxy routes.

**Phase 5 is pure React — zero backend changes.**

---

## Scope

### In scope
- Switch every axios call to use `http://localhost:8001` as base URL
- Rewrite service files to use `/proxy/*` and `/local/*` paths
- Rewrite `AuthContext.jsx` — no localStorage, session via `GET /status`
- Fix `authService.js` — JSON body login (not form-data), remove `/auth/me`
- Add `ProtectedRoute` component — replaces scattered inline guards
- Add `SyncStatusBar` component — polls `/status` every 60s
- Add `OfflineBanner` component — reads `_offline` flag from proxy responses
- Rewrite `Portfolio.jsx` — full CRUD with holdings table and P&L
- Add `Watchlist.jsx` — add/remove stocks and funds
- Add `AgentChat.jsx` — chat UI stub (LLM wired in Phase 6)
- Update `App.jsx` — ProtectedRoute wrapper, new routes
- Update `Layout.jsx` — SyncStatusBar at top
- Update navbar — Portfolio, Watchlist, Agent links

### Out of scope
- TypeScript migration (frontend stays `.jsx`)
- LLM wiring in agent (Phase 6)
- CI/CD (Phase 8)
- Any backend changes

### Constraint — preserve response shapes
Existing components parse `FundMasterListResponse`, `StockDetailResult`,
`ScreenerResponse` etc. The proxy router returns these unchanged. Phase 5
must not transform shapes — goal is a URL switch, not a data model change.

---

## Architecture

### Current state (broken)
```
React UI
  → apiClient.js (axios, baseURL = /api/v1)
  → authService: POST /auth/login (form-data) + GET /auth/me
  → fundService: GET /funds/, /navs/, /metrics/, /benchmarks/
  → stockService: GET /stocks, /screener
  → AuthContext: stores JWT in localStorage
```

### Target state
```
React UI
  → apiClient.js (axios, baseURL = http://localhost:8001)
  → authService: POST /auth/login (JSON body) — no /auth/me
  → fundService: GET /proxy/funds, /proxy/funds/{code}/nav, /proxy/benchmarks
  → stockService: GET /proxy/stocks, /proxy/stocks/screener
  → AuthContext: no localStorage — session detected via GET /status
  → portfolioService (new): GET/POST/PUT/DELETE /local/portfolio/*
  → watchlistService (new): GET/POST/DELETE /local/watchlist
  → agentService (new): POST /agent/sessions, GET /agent/sessions/{id}/messages, POST chat
  → statusService (new): GET /status
```

---

## Section 1 — API Layer

### `src/api/apiClient.js`
- `baseURL`: `http://localhost:8001`
- Remove auth header interceptor — client backend injects JWT, React never touches it
- 401 handler: dispatch `auth:session-expired` CustomEvent instead of clearing localStorage

### `src/api/services/authService.js`
- `login(username, password)`: POST `/auth/login` with `{username, password}` JSON body
- `logout()`: POST `/auth/logout`
- Remove `getMe()` — does not exist on the client

### `src/api/services/fundService.js`
Path mapping:
| Old | New |
|---|---|
| `/funds/` | `/proxy/funds` |
| `/funds/{code}` | `/proxy/funds/{code}` |
| `/navs/{code}` | `/proxy/funds/{code}/nav` |
| `/funds/compare` | `/proxy/funds/compare` |
| `/benchmarks/` | `/proxy/benchmarks` |
| `/benchmarks/{code}` | `/proxy/benchmarks/{code}` |
| `/benchmark-navs/{code}` | `/proxy/benchmarks/{code}/nav` |

Remove: `syncAllFunds`, `syncFund`, `computeMetrics`, `createFund`, `updateFund`,
`deleteFund`, `createBenchmark`, `updateBenchmark`, `deleteBenchmark`,
`uploadBenchmarkCsv` — these wrote to the server; the client is read-only.

### `src/api/services/stockService.js`
Path mapping:
| Old | New |
|---|---|
| `/stocks` | `/proxy/stocks` |
| `/stocks/{symbol}` | `/proxy/stocks/{symbol}` |
| `/screener` | `/proxy/stocks/screener` |

Remove pipeline trigger methods — server-side ingestion only.

### New service files
- `src/api/services/portfolioService.js` — `/local/portfolio/holdings`, `/local/portfolio/transactions`
- `src/api/services/watchlistService.js` — `/local/watchlist`
- `src/api/services/agentService.js` — `/agent/sessions`, `/agent/sessions/{id}/messages`, `/agent/sessions/{id}/chat`, `/agent/memory`
- `src/api/services/statusService.js` — `/status`

---

## Section 2 — Auth & Session

### `src/context/AuthContext.jsx` (rewrite)
**State:** `{ isAuthenticated, username, isLoading }` + `error`

**Session detection on mount:**
```
GET /status
  → success (any response) → check last_connected_at field
    → last_connected_at is set → user logged in before
      → GET /local/preferences → read last_login_username
      → isAuthenticated = true (token may still be valid; proxy calls test it lazily)
    → last_connected_at is null → never logged in → show login
  → client unreachable (network error) → isLoading = false, not authenticated
```

Note: `is_online` reflects server connectivity, not token validity. A user can be
authenticated while offline (stored refresh token in SQLite). Session detection
uses `last_connected_at` (set on first login, cleared on logout) not `is_online`.

**login():**
```
authService.login(username, password)
  → success → PUT /local/preferences/last_login_username
  → setState isAuthenticated = true
```

**logout():** calls `authService.logout()`, clears auth state.

**Session expiry:** `useEffect` listens for `auth:session-expired` event
(dispatched by apiClient 401 handler), clears auth state.

**No localStorage.** The client SQLite holds the JWT. React holds only
`isAuthenticated` (bool) + `username` (string) in component state.

### `src/pages/Login.jsx`
Already exists — only change is `authService.login()` now sends JSON, not form-data.
Existing UI/form stays unchanged.

### `src/components/ProtectedRoute.jsx` (new)
```
useAuth() → isLoading → spinner
           → !isAuthenticated → <Navigate to="/login" replace />
           → authenticated → <Outlet />
```
Replaces inline `user ? <Page /> : <Navigate>` in App.jsx.

---

## Section 3 — New Components & Pages

### `src/components/SyncStatusBar.jsx`
- Polls `GET /status` every 60 seconds via `statusService`
- **Online:** green dot · "Connected · last sync Xm ago · N cached"
- **Offline:** amber dot · "Offline — cached data from Xh ago"
- **Client unreachable:** red · "Client not reachable on port 8001"
- Renders above navbar, always visible when authenticated

### `src/components/OfflineBanner.jsx`
- Props: `isOffline` (bool), `lastSync` (ISO string, optional)
- Renders amber dismissible banner when `isOffline = true`
- Used inside any page that calls `/proxy/*`
- `useOfflineDetect(data)` hook: reads `data._offline` from any response

### `src/pages/Portfolio.jsx` (rewrite existing stub)
- Summary row: Invested / Current Value / P&L (enriched from `/proxy/stocks` + `/proxy/funds`)
- Holdings table: symbol, type, qty, avg cost, current price, P&L, P&L%
- "Add Holding" button → inline modal
- Delete holding with confirm dialog
- Offline-safe: shows "—" for prices when server unreachable

### `src/pages/Watchlist.jsx` (new)
- Card grid of watchlist items
- Inline add form: symbol input + asset type select + notes
- Remove button per card
- Calls `/local/watchlist` — always available, no server dependency

### `src/pages/AgentChat.jsx` (new — stub for Phase 6)
- Creates/loads session from `/agent/sessions` on mount
- Message list with user/assistant bubbles
- Optimistic UI: user message appears immediately
- Sends to `POST /agent/sessions/{id}/chat`
- Shows stub reply: "Agent not yet connected (Phase 6)"
- "New Conversation" button
- Suggestion chips: "Analyse RELIANCE", "Compare top large cap funds", etc.
- Badge: "Phase 6 — LLM not yet connected"

---

## Section 4 — Router & Navbar

### `src/App.jsx`
Replace scattered `user ? <Page /> : <Navigate to="/login" />` with:
```jsx
<Route element={<ProtectedRoute />}>
  <Route element={<Layout />}>
    {/* all authenticated routes */}
  </Route>
</Route>
```
Add routes: `/watchlist`, `/agent`. Replace Portfolio stub route.

### `src/components/Layout.jsx`
Add `<SyncStatusBar />` at the top of the layout body, above page content.

### Navbar
Add links: Portfolio (`/portfolio`), Watchlist (`/watchlist`), Agent (`/agent`).

---

## File Change Map

```
src/api/
  apiClient.js                    MODIFY — baseURL, remove auth interceptor, 401 → event
  services/authService.js         MODIFY — JSON login, remove getMe
  services/fundService.js         MODIFY — /proxy/* paths, remove write methods
  services/stockService.js        MODIFY — /proxy/* paths, remove pipeline triggers
  services/portfolioService.js    CREATE
  services/watchlistService.js    CREATE
  services/agentService.js        CREATE
  services/statusService.js       CREATE

src/context/
  AuthContext.jsx                 REWRITE — no localStorage, GET /status session check

src/components/
  ProtectedRoute.jsx              CREATE
  SyncStatusBar.jsx               CREATE
  OfflineBanner.jsx               CREATE
  Layout.jsx                      MODIFY — add SyncStatusBar

src/pages/
  Login.jsx                       MODIFY — authService call only (no UI change)
  Portfolio.jsx                   REWRITE — full holdings CRUD with P&L
  Watchlist.jsx                   CREATE
  AgentChat.jsx                   CREATE

src/
  App.jsx                         MODIFY — ProtectedRoute, new routes
```

---

## Definition of Done

- `http://localhost:5173` redirects to `/login` when not authenticated
- Login with correct credentials → fund list page
- Login with wrong credentials → error message
- All existing fund list, fund detail, comparison, benchmark pages load
- All existing stock list, stock detail, screener pages load
- SyncStatusBar shows green when online, amber when offline
- Fund/stock pages show OfflineBanner when served from stale cache
- Portfolio: add holding → visible in table with P&L
- Portfolio: delete holding → removed from table
- Watchlist: add/remove items
- AgentChat: send message → stub reply shown, message stored in SQLite
- Logout → redirected to `/login`
- Navigating to `/portfolio` when not logged in → `/login`

---

*Nivesh Platform · Phase 5 Design · 2026-05-15*
*Previous: Phase 4 — Client Application (SQLite + Local API)*
*Next: Phase 6 — Agentic Layer*
