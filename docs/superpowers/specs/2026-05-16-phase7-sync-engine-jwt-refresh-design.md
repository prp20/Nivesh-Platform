# Phase 7 — Sync Engine + JWT Refresh Design Spec

**Goal:** Make the Nivesh client robust for real daily use — token always fresh, portfolio prices pre-loaded, sync problems recoverable via a single force-sync call.

**Architecture:** Three focused service modules + one new router, all following the existing pattern in `services/sync.py` and `services/http_client.py`. The APScheduler gets two new jobs. No new SQLite tables — everything uses existing `auth_tokens`, `cache_entries`, `portfolio_holdings`, and `watchlist` rows.

**Tech Stack:** Existing — FastAPI, SQLAlchemy async, aiosqlite, APScheduler, httpx, pytz (IST scheduling).

---

## Scope

### In scope

- **Proactive JWT refresh** — APScheduler checks every 5 minutes; refreshes access token if `expires_at` is within 5 minutes
- **Auth status endpoint** — `GET /auth/status` returns login state, username, and token expiry without a server round-trip
- **Portfolio price enrichment** — On startup and every 30 minutes (market hours Mon–Fri 09:00–16:00 IST), pre-warm the cache for every holding and watchlist symbol
- **Force-sync endpoint** — `POST /sync/force` clears cache by resource type and re-fetches immediately
- **Client sync status endpoint** — `GET /sync/client-status` returns cache health stats consumed by the React SyncStatusBar

### Out of scope

- Server-side portfolio/watchlist storage (Phase 8+)
- Multi-device sync
- Delta sync for OHLCV history (server already handles this)
- Push notifications on price alerts

---

## File Map

```
nivesh-client/app/
├── services/
│   ├── sync.py              ← MODIFY: expand run_startup_sync to call portfolio + watchlist sync
│   ├── token_refresh.py     ← NEW: refresh_if_expiring_soon()
│   └── portfolio_sync.py    ← NEW: sync_portfolio_prices(), sync_watchlist_prices()
├── routers/
│   ├── auth.py              ← MODIFY: add GET /auth/status
│   └── sync.py              ← NEW: GET /sync/client-status, POST /sync/force
└── main.py                  ← MODIFY: register token_refresh + portfolio_sync scheduler jobs,
                                        include sync router
```

---

## Component Design

### 1. `services/token_refresh.py`

**Responsibility:** Proactive JWT access token refresh before expiry.

**Interface:**
```python
async def refresh_if_expiring_soon(db: AsyncSession, window_seconds: int = 300) -> bool
```

**Logic:**
1. Read `auth_tokens` row id=1. If no row or no `refresh_token` → return `False` (not logged in).
2. Compute `time_remaining = expires_at - now(UTC)` in seconds.
3. If `time_remaining > window_seconds` → return `False` (still fresh, skip).
4. POST to `/api/v1/auth/refresh` with the stored `refresh_token`.
5. On HTTP 401 → raise `SessionExpiredError` (refresh token itself expired — user must re-login).
6. On success → UPDATE `auth_tokens` id=1 with new `access_token` and `expires_at`.
7. Return `True`.

**Error handling:**
- `SessionExpiredError` → caller logs a warning; scheduler does NOT crash.
- `httpx.ConnectError` / `httpx.TimeoutException` → log warning, return `False` (server offline — try again in 5 min).
- Any other exception → log error, return `False`.

**Scheduler job (in `main.py`):**
```
interval: every 5 minutes
id: "token_refresh"
```

---

### 2. `services/portfolio_sync.py`

**Responsibility:** Pre-warm the TTL cache for all portfolio holdings and watchlist items.

**Interfaces:**
```python
async def sync_portfolio_prices(db: AsyncSession) -> int  # returns count refreshed
async def sync_watchlist_prices(db: AsyncSession) -> int  # returns count refreshed
```

**Logic for `sync_portfolio_prices`:**
1. `SELECT * FROM portfolio_holdings` — all rows.
2. For each holding:
   - Build `cache_key`: `stocks:detail:{symbol}` (STOCK) or `funds:detail:{symbol}` (FUND).
   - Check if cache is already fresh with `get_cached()` — skip if fresh (avoid redundant fetches).
   - Call `ServerClient.get()` to fetch `/api/v1/stocks/{symbol}` or `/api/v1/funds/{symbol}`.
   - On success → `set_cached(db, cache_key, data, ttl)` using the appropriate TTL from settings.
   - On `OfflineError` → `break` immediately. Don't hammer an offline server.
3. Return count of symbols successfully refreshed.

**Logic for `sync_watchlist_prices`:** Identical pattern, reads from `watchlist` table instead.

**Scheduler job (in `main.py`):**
```
cron: Mon–Fri, hour=9–16 IST, minute=*/30
id: "portfolio_sync"
```
Also called once from `run_startup_sync()` (non-blocking, best-effort).

**Error handling:**
- `OfflineError` → break loop, log warning, return partial count.
- Per-symbol exceptions (bad symbol, 404) → log and continue to next symbol.

---

### 3. `GET /auth/status` (added to `routers/auth.py`)

**Responsibility:** Let React know whether the user is currently logged in, without hitting the server.

**Response shape:**
```json
{
  "logged_in": true,
  "username": "prasad",
  "expires_at": "2026-05-16T14:30:00+00:00",
  "expires_in_seconds": 720
}
```
If no auth row:
```json
{ "logged_in": false, "username": null, "expires_at": null, "expires_in_seconds": null }
```

**Logic:** Single `SELECT` from `auth_tokens` where `id=1`. Compute `expires_in_seconds = (expires_at - now).total_seconds()`. No server call. Always fast.

---

### 4. `routers/sync.py` — Two endpoints

#### `GET /sync/client-status`

Returns cache health stats for the React SyncStatusBar. No server call.

**Response shape:**
```json
{
  "is_online": true,
  "last_connected_at": "2026-05-16T13:00:00+00:00",
  "token_expires_in_seconds": 720,
  "cache_entries_total": 142,
  "cache_entries_fresh": 138,
  "holdings_cached": 5,
  "holdings_total": 5,
  "watchlist_cached": 8,
  "watchlist_total": 10
}
```

**Logic:**
- `is_online` / `last_connected_at` → read from `server_config` table.
- `token_expires_in_seconds` → read `auth_tokens.expires_at`, compute delta.
- `cache_entries_total` / `cache_entries_fresh` → COUNT from `cache_entries` total vs non-expired.
- `holdings_cached` → COUNT holdings where `stocks:detail:{symbol}` or `funds:detail:{symbol}` has a fresh cache row.
- `watchlist_cached` → same for watchlist items.

#### `POST /sync/force`

Clears cache by resource type and immediately re-fetches.

**Request body:**
```json
{ "resource": "funds" | "stocks" | "benchmarks" | "portfolio" | "watchlist" | "all" }
```

**Response:**
```json
{ "cleared": 23, "refreshed": 18, "message": "Sync complete" }
```

**Logic per resource:**
- `"funds"` → DELETE cache rows where `key LIKE 'funds:%'` → call `sync_fund_list()`
- `"stocks"` → DELETE `stocks:%` → no active re-fetch (on-demand via proxy)
- `"benchmarks"` → DELETE `benchmarks:%` → call `sync_benchmark_list()`
- `"portfolio"` → DELETE portfolio holding cache keys → call `sync_portfolio_prices()`
- `"watchlist"` → DELETE watchlist cache keys → call `sync_watchlist_prices()`
- `"all"` → DELETE everything → call `run_startup_sync()` + `sync_portfolio_prices()` + `sync_watchlist_prices()`

---

### 5. `main.py` changes

**New scheduler jobs:**
```python
scheduler.add_job(
    _token_refresh, "interval",
    minutes=5,
    id="token_refresh",
    replace_existing=True,
)

scheduler.add_job(
    _portfolio_sync,
    CronTrigger(day_of_week="mon-fri", hour="9-16", minute="*/30", timezone=IST),
    id="portfolio_sync",
    replace_existing=True,
)
```

**New router:**
```python
from .routers import sync as sync_router
app.include_router(sync_router.router)
```

**Startup sync expansion** (in `run_startup_sync`):
```python
await sync_fund_list(db)
await sync_benchmark_list(db)
await sync_portfolio_prices(db)   # NEW — best-effort, OfflineError is silent
await sync_watchlist_prices(db)   # NEW
```

---

## Error Handling Summary

| Scenario | Behavior |
|---|---|
| Token refresh: server offline | Log warning, skip. Retry in 5 min. |
| Token refresh: refresh token expired | Log warning "session expired". React gets `logged_in: false` on next `/auth/status` check. |
| Portfolio sync: server offline | Break loop at first `OfflineError`. Existing stale cache stays. |
| Portfolio sync: bad symbol (404) | Log and continue to next symbol. |
| Force-sync: server offline | Return `{"cleared": N, "refreshed": 0, "message": "Server offline — cache cleared, re-fetch pending"}` |
| Scheduler crash | APScheduler logs the exception and reschedules. Client keeps running. |

---

## Scheduler Job Summary

| Job | Trigger | What it does |
|---|---|---|
| `health_ping` | Every 60s | Existing — pings `/health`, updates `is_online` |
| `cache_cleanup` | Every 3600s | Existing — deletes expired cache rows |
| `token_refresh` | Every 5 min | NEW — proactive access token refresh |
| `portfolio_sync` | Mon–Fri 09–16 IST, every 30 min | NEW — price enrichment for holdings + watchlist |

---

## Definition of Done

- [ ] `GET /auth/status` returns correct login state without server call
- [ ] APScheduler logs "token refreshed" when access token is within 5 min of expiry
- [ ] APScheduler logs "token still valid — skipping" when token has >5 min remaining
- [ ] `SessionExpiredError` on bad refresh token logs a warning but does not crash scheduler
- [ ] On startup, portfolio holding prices are pre-warmed into cache
- [ ] On startup, watchlist item prices are pre-warmed into cache
- [ ] `portfolio_sync` job runs every 30 min during market hours — verified via log
- [ ] `GET /sync/client-status` returns correct `holdings_cached` / `watchlist_cached` counts
- [ ] `POST /sync/force {"resource": "all"}` clears cache and triggers full re-fetch
- [ ] `POST /sync/force {"resource": "portfolio"}` refreshes only holding symbols
- [ ] Server offline during force-sync returns 200 with `refreshed: 0`, not a 500
- [ ] All new scheduler jobs appear in APScheduler log on startup
