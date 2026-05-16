# Phase 7 — Sync Engine + JWT Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Nivesh client robust for daily use — access token refreshed proactively, portfolio/watchlist prices pre-loaded in cache, sync problems recoverable via a single API call.

**Architecture:** Three new service modules (`token_refresh.py`, `portfolio_sync.py`) and one new router (`routers/sync.py`). Two new APScheduler jobs. One new endpoint on `routers/auth.py`. All follow the existing pattern in `services/sync.py` and `services/http_client.py`. No new SQLite tables needed.

**Tech Stack:** FastAPI, SQLAlchemy async, aiosqlite, APScheduler, httpx, pytz (IST scheduling). All already installed.

---

## Baseline — What Already Exists

| Component | File | Phase 7 use |
|---|---|---|
| `ServerClient` async context manager | `services/http_client.py` | JWT injection + auto-refresh on 401, reused in portfolio_sync |
| `OfflineError`, `SessionExpiredError` | `services/http_client.py` | Imported into token_refresh.py + portfolio_sync.py |
| `get_cached`, `set_cached`, `invalidate` | `services/cache.py` | Cache read/write in portfolio_sync; invalidate in force-sync |
| `AuthToken` model (id=1 row, has `expires_at`) | `models/auth.py` | Read in token_refresh; read in /auth/status |
| `ServerConfig` model (key-value) | `models/auth.py` | Read in /sync/client-status |
| `PortfolioHolding` model | `models/user_data.py` | Iterated in portfolio_sync + force-sync |
| `Watchlist` model | `models/user_data.py` | Iterated in watchlist_sync + force-sync |
| `CacheEntry` model | `models/cache.py` | Counted in /sync/client-status |
| `sync_fund_list`, `sync_benchmark_list` | `services/sync.py` | Called from force-sync |
| APScheduler in `main.py` | `main.py` | Two new jobs added |
| `settings.CACHE_TTL_STOCK_DETAIL` | `config.py` | TTL for holdings cache |
| `settings.CACHE_TTL_FUND_DETAIL` | `config.py` | TTL for fund holdings cache |

---

## File Map

```
nivesh-client/app/
├── services/
│   ├── sync.py              MODIFY — expand run_startup_sync to call portfolio + watchlist sync
│   ├── token_refresh.py     CREATE — refresh_if_expiring_soon()
│   └── portfolio_sync.py    CREATE — sync_portfolio_prices(), sync_watchlist_prices()
├── routers/
│   ├── auth.py              MODIFY — add GET /auth/status
│   └── sync.py              CREATE — GET /sync/client-status, POST /sync/force
└── main.py                  MODIFY — register 2 new scheduler jobs, include sync router
```

---

## Task 1: Create `services/token_refresh.py`

**Files:**
- Create: `nivesh-client/app/services/token_refresh.py`

- [ ] **Step 1: Create the file**

```python
# nivesh-client/app/services/token_refresh.py
"""
Proactive JWT access token refresh.

refresh_if_expiring_soon(db, window_seconds=300):
    Called by APScheduler every 5 minutes.
    Reads expires_at from auth_tokens (id=1).
    If time remaining < window_seconds, POSTs /api/v1/auth/refresh.
    Updates auth_tokens with new access_token and expires_at.
    Returns True if refreshed, False if not needed or not logged in.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.auth import AuthToken
from ..services.http_client import SessionExpiredError

logger = logging.getLogger(__name__)


async def refresh_if_expiring_soon(
    db: AsyncSession,
    window_seconds: int = 300,
) -> bool:
    """
    Proactively refresh the access token if it expires within window_seconds.

    Returns True if a refresh was performed.
    Returns False if token is still valid, or no user is logged in.
    Raises SessionExpiredError if the refresh token itself is rejected (user must re-login).
    On server unreachable: logs warning, returns False (retried in 5 min by scheduler).
    """
    result = await db.execute(select(AuthToken).where(AuthToken.id == 1))
    row = result.scalar_one_or_none()
    if not row or not row.refresh_token:
        return False  # Not logged in — nothing to do

    # Normalise to UTC-aware datetime
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    time_remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()

    if time_remaining > window_seconds:
        logger.debug(
            "Token valid for %.0f more seconds — skipping proactive refresh",
            time_remaining,
        )
        return False

    logger.info(
        "Token expiring in %.0f seconds (threshold=%d) — refreshing proactively",
        time_remaining,
        window_seconds,
    )

    try:
        async with httpx.AsyncClient(
            base_url=settings.NIVESH_SERVER_URL, timeout=15
        ) as client:
            resp = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": row.refresh_token},
            )
            if resp.status_code == 401:
                raise SessionExpiredError(
                    "Refresh token rejected — user must log in again"
                )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning("Proactive token refresh skipped — server unreachable: %s", e)
        return False

    new_expires = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
    await db.execute(
        update(AuthToken)
        .where(AuthToken.id == 1)
        .values(
            access_token=data["access_token"],
            expires_at=new_expires,
        )
    )
    await db.commit()
    logger.info("Access token refreshed — new expiry: %s", new_expires.isoformat())
    return True
```

- [ ] **Step 2: Verify import works**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "from app.services.token_refresh import refresh_if_expiring_soon; print('token_refresh OK')"
```

Expected: `token_refresh OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/services/token_refresh.py
git commit -m "feat(phase7): add token_refresh service — proactive JWT refresh within 5-min window"
```

---

## Task 2: Create `services/portfolio_sync.py`

**Files:**
- Create: `nivesh-client/app/services/portfolio_sync.py`

- [ ] **Step 1: Create the file**

```python
# nivesh-client/app/services/portfolio_sync.py
"""
Portfolio and watchlist price enrichment.

sync_portfolio_prices(db):
    Reads all portfolio_holdings rows.
    For each holding, fetches the stock/fund detail from the server
    and writes it into the same cache key the proxy router uses.
    Skips symbols whose cache is already fresh.
    Aborts immediately on OfflineError — no point retrying if server is down.
    Per-symbol errors (404, bad data) are logged and skipped.
    Returns count of symbols successfully refreshed.

sync_watchlist_prices(db):
    Same pattern for watchlist items.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.user_data import PortfolioHolding, Watchlist
from ..services.cache import get_cached, set_cached
from ..services.http_client import OfflineError, ServerClient

logger = logging.getLogger(__name__)


async def sync_portfolio_prices(db: AsyncSession) -> int:
    """
    Pre-warm cache for all portfolio holdings.

    Cache keys used (same as proxy router):
      STOCK → 'stocks:detail:{SYMBOL}'
      FUND  → 'funds:detail:{SYMBOL}'   (symbol = scheme_code for funds)

    Returns count of symbols successfully refreshed.
    """
    result = await db.execute(select(PortfolioHolding))
    holdings = result.scalars().all()
    if not holdings:
        logger.debug("[portfolio_sync] No holdings — nothing to sync")
        return 0

    refreshed = 0
    for holding in holdings:
        sym = holding.symbol.upper()
        is_stock = holding.asset_type == "STOCK"
        cache_key = f"stocks:detail:{sym}" if is_stock else f"funds:detail:{sym}"
        server_path = f"/api/v1/stocks/{sym}" if is_stock else f"/api/v1/funds/{sym}"
        ttl = (
            settings.CACHE_TTL_STOCK_DETAIL
            if is_stock
            else settings.CACHE_TTL_FUND_DETAIL
        )

        # Skip if cache is already fresh — avoid redundant server calls
        _, is_fresh = await get_cached(db, cache_key)
        if is_fresh:
            logger.debug("[portfolio_sync] %s already cached — skipping", sym)
            continue

        try:
            async with ServerClient(db) as client:
                data = await client.get(server_path)
            await set_cached(db, cache_key, data, ttl)
            refreshed += 1
            logger.debug(
                "[portfolio_sync] Cached %s (%s)", sym, "stock" if is_stock else "fund"
            )
        except OfflineError:
            logger.warning(
                "[portfolio_sync] Server offline — aborting after %d/%d refreshed",
                refreshed,
                len(holdings),
            )
            break  # Don't hammer an offline server
        except Exception as exc:
            logger.warning(
                "[portfolio_sync] Failed to fetch %s: %s — continuing", sym, exc
            )
            # Per-symbol errors (404, parse error) don't abort the loop

    logger.info(
        "[portfolio_sync] Done — refreshed %d of %d holdings", refreshed, len(holdings)
    )
    return refreshed


async def sync_watchlist_prices(db: AsyncSession) -> int:
    """
    Pre-warm cache for all watchlist items.
    Same pattern as sync_portfolio_prices.

    Returns count of symbols successfully refreshed.
    """
    result = await db.execute(select(Watchlist))
    items = result.scalars().all()
    if not items:
        logger.debug("[watchlist_sync] Watchlist empty — nothing to sync")
        return 0

    refreshed = 0
    for item in items:
        sym = item.symbol.upper()
        is_stock = item.asset_type == "STOCK"
        cache_key = f"stocks:detail:{sym}" if is_stock else f"funds:detail:{sym}"
        server_path = f"/api/v1/stocks/{sym}" if is_stock else f"/api/v1/funds/{sym}"
        ttl = (
            settings.CACHE_TTL_STOCK_DETAIL
            if is_stock
            else settings.CACHE_TTL_FUND_DETAIL
        )

        _, is_fresh = await get_cached(db, cache_key)
        if is_fresh:
            logger.debug("[watchlist_sync] %s already cached — skipping", sym)
            continue

        try:
            async with ServerClient(db) as client:
                data = await client.get(server_path)
            await set_cached(db, cache_key, data, ttl)
            refreshed += 1
            logger.debug("[watchlist_sync] Cached %s", sym)
        except OfflineError:
            logger.warning(
                "[watchlist_sync] Server offline — aborting after %d/%d refreshed",
                refreshed,
                len(items),
            )
            break
        except Exception as exc:
            logger.warning(
                "[watchlist_sync] Failed to fetch %s: %s — continuing", sym, exc
            )

    logger.info(
        "[watchlist_sync] Done — refreshed %d of %d watchlist items",
        refreshed,
        len(items),
    )
    return refreshed
```

- [ ] **Step 2: Verify import works**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "
from app.services.portfolio_sync import sync_portfolio_prices, sync_watchlist_prices
print('portfolio_sync OK')
"
```

Expected: `portfolio_sync OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/services/portfolio_sync.py
git commit -m "feat(phase7): add portfolio_sync service — price enrichment for holdings + watchlist"
```

---

## Task 3: Expand `services/sync.py` — `run_startup_sync`

**Files:**
- Modify: `nivesh-client/app/services/sync.py` (lines 90–98)

- [ ] **Step 1: Update `run_startup_sync` to include portfolio + watchlist sync**

Replace the existing `run_startup_sync` function (lines 90–98):

```python
async def run_startup_sync(db: AsyncSession) -> None:
    """
    Runs once on client startup (in background, non-blocking).
    Warms the cache with the most commonly accessed data.
    Portfolio/watchlist sync is best-effort — OfflineError is caught per-function.
    """
    from .portfolio_sync import sync_portfolio_prices, sync_watchlist_prices

    logger.info("[startup] Warming cache...")
    await sync_fund_list(db)
    await sync_benchmark_list(db)

    p_count = await sync_portfolio_prices(db)
    w_count = await sync_watchlist_prices(db)
    logger.info(
        "[startup] Cache warm complete — portfolio: %d symbols, watchlist: %d symbols",
        p_count,
        w_count,
    )
```

Also update `__all__` at the bottom to export the new imports:

```python
__all__ = [
    "ping_server",
    "sync_fund_list",
    "sync_benchmark_list",
    "run_startup_sync",
    "cleanup_expired",
]
```

(No change to `__all__` needed — `portfolio_sync` functions are imported via their own module.)

- [ ] **Step 2: Verify the module still imports cleanly**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "from app.services.sync import run_startup_sync, ping_server; print('sync.py OK')"
```

Expected: `sync.py OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/services/sync.py
git commit -m "feat(phase7): expand run_startup_sync to include portfolio + watchlist price enrichment"
```

---

## Task 4: Add `GET /auth/status` to `routers/auth.py`

**Files:**
- Modify: `nivesh-client/app/routers/auth.py` (append new endpoint)

- [ ] **Step 1: Add the missing import and new endpoint**

At the top of `auth.py`, the existing imports already include `select` and `AuthToken`. Add the `datetime` import (it's already there for login). Add this endpoint after the `logout` function:

```python
@router.get("/status")
async def auth_status(db: AsyncSession = Depends(get_db)):
    """
    Returns login state without hitting the server.
    React calls this on load to decide whether to show Login or Dashboard.

    Response when logged in:
      { logged_in: true, username: "prasad",
        expires_at: "2026-05-16T14:30:00+00:00", expires_in_seconds: 720 }

    Response when not logged in:
      { logged_in: false, username: null, expires_at: null, expires_in_seconds: null }
    """
    result = await db.execute(select(AuthToken).where(AuthToken.id == 1))
    row = result.scalar_one_or_none()

    if not row:
        return {
            "logged_in": False,
            "username": None,
            "expires_at": None,
            "expires_in_seconds": None,
        }

    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    expires_in = int((expires_at - datetime.now(timezone.utc)).total_seconds())

    return {
        "logged_in": True,
        "username": row.username,
        "expires_at": expires_at.isoformat(),
        "expires_in_seconds": expires_in,
    }
```

The `timezone` and `datetime` are already imported at the top of `auth.py`.

- [ ] **Step 2: Verify import**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "from app.routers.auth import router; print('auth router OK')"
```

Expected: `auth router OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/routers/auth.py
git commit -m "feat(phase7): add GET /auth/status — login state check without server round-trip"
```

---

## Task 5: Create `routers/sync.py`

**Files:**
- Create: `nivesh-client/app/routers/sync.py`

- [ ] **Step 1: Create the file**

```python
# nivesh-client/app/routers/sync.py
"""
Sync router — /sync/*

Endpoints:
  GET  /sync/client-status  → Cache health stats for React SyncStatusBar.
                               Reads local SQLite only — no server call.
  POST /sync/force           → Clear cache by resource type and immediately re-fetch.
                               resource: "funds"|"stocks"|"benchmarks"|"portfolio"|"watchlist"|"all"
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.auth import AuthToken, ServerConfig
from ..models.cache import CacheEntry
from ..models.user_data import PortfolioHolding, Watchlist
from ..services.cache import get_cached, invalidate
from ..services.portfolio_sync import sync_portfolio_prices, sync_watchlist_prices
from ..services.sync import run_startup_sync, sync_benchmark_list, sync_fund_list

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])

VALID_RESOURCES = {"funds", "stocks", "benchmarks", "portfolio", "watchlist", "all"}


class ForceSyncRequest(BaseModel):
    resource: str


@router.get("/client-status")
async def client_sync_status(db: AsyncSession = Depends(get_db)):
    """
    Cache health stats consumed by the React SyncStatusBar.
    All reads are local SQLite — no server call.
    """
    # ── Server connectivity state ─────────────────────────────────────────────
    cfg_result = await db.execute(
        select(ServerConfig).where(
            ServerConfig.key.in_(["is_online", "last_connected_at"])
        )
    )
    config = {r.key: r.value for r in cfg_result.scalars().all()}

    # ── Token expiry ──────────────────────────────────────────────────────────
    token_result = await db.execute(select(AuthToken).where(AuthToken.id == 1))
    token_row = token_result.scalar_one_or_none()
    token_expires_in: int | None = None
    if token_row and token_row.expires_at:
        exp = token_row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        token_expires_in = int((exp - datetime.now(timezone.utc)).total_seconds())

    # ── Cache entry counts ────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    all_entries = (await db.execute(select(CacheEntry))).scalars().all()
    total = len(all_entries)
    fresh = 0
    for e in all_entries:
        fetched = e.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if (now - fetched).total_seconds() < e.ttl_seconds:
            fresh += 1

    # ── Holdings cache coverage ───────────────────────────────────────────────
    holdings = (await db.execute(select(PortfolioHolding))).scalars().all()
    holdings_cached = 0
    for h in holdings:
        sym = h.symbol.upper()
        key = f"stocks:detail:{sym}" if h.asset_type == "STOCK" else f"funds:detail:{sym}"
        _, is_fresh = await get_cached(db, key)
        if is_fresh:
            holdings_cached += 1

    # ── Watchlist cache coverage ──────────────────────────────────────────────
    watchlist = (await db.execute(select(Watchlist))).scalars().all()
    watchlist_cached = 0
    for w in watchlist:
        sym = w.symbol.upper()
        key = f"stocks:detail:{sym}" if w.asset_type == "STOCK" else f"funds:detail:{sym}"
        _, is_fresh = await get_cached(db, key)
        if is_fresh:
            watchlist_cached += 1

    return {
        "is_online": config.get("is_online") == "true",
        "last_connected_at": config.get("last_connected_at"),
        "token_expires_in_seconds": token_expires_in,
        "cache_entries_total": total,
        "cache_entries_fresh": fresh,
        "holdings_cached": holdings_cached,
        "holdings_total": len(holdings),
        "watchlist_cached": watchlist_cached,
        "watchlist_total": len(watchlist),
    }


@router.post("/force")
async def force_sync(body: ForceSyncRequest, db: AsyncSession = Depends(get_db)):
    """
    Clear cache for a resource type and immediately re-fetch from the server.

    resource="funds"       → clear funds:* cache + re-fetch fund list
    resource="stocks"      → clear stocks:* cache (re-fetched on next proxy request)
    resource="benchmarks"  → clear benchmarks:* cache + re-fetch
    resource="portfolio"   → clear cache for each held symbol + re-fetch prices
    resource="watchlist"   → clear cache for each watchlist symbol + re-fetch prices
    resource="all"         → clear all cache entries + full startup sync
    """
    if body.resource not in VALID_RESOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown resource '{body.resource}'. Valid: {sorted(VALID_RESOURCES)}",
        )

    cleared = 0
    refreshed = 0
    message = ""

    try:
        resource = body.resource

        if resource == "funds":
            cleared = await invalidate(db, "funds:")
            refreshed = 1 if await sync_fund_list(db) else 0
            message = f"Funds cache cleared ({cleared} entries) and refreshed"

        elif resource == "stocks":
            cleared = await invalidate(db, "stocks:")
            message = (
                f"Stocks cache cleared ({cleared} entries) — "
                "data re-fetches on next proxy request"
            )

        elif resource == "benchmarks":
            cleared = await invalidate(db, "benchmarks:")
            refreshed = 1 if await sync_benchmark_list(db) else 0
            message = f"Benchmarks cache cleared ({cleared} entries) and refreshed"

        elif resource == "portfolio":
            holdings = (await db.execute(select(PortfolioHolding))).scalars().all()
            for h in holdings:
                sym = h.symbol.upper()
                prefix = (
                    f"stocks:detail:{sym}"
                    if h.asset_type == "STOCK"
                    else f"funds:detail:{sym}"
                )
                cleared += await invalidate(db, prefix)
            refreshed = await sync_portfolio_prices(db)
            message = f"Portfolio: {cleared} cache entries cleared, {refreshed} symbols refreshed"

        elif resource == "watchlist":
            watchlist = (await db.execute(select(Watchlist))).scalars().all()
            for w in watchlist:
                sym = w.symbol.upper()
                prefix = (
                    f"stocks:detail:{sym}"
                    if w.asset_type == "STOCK"
                    else f"funds:detail:{sym}"
                )
                cleared += await invalidate(db, prefix)
            refreshed = await sync_watchlist_prices(db)
            message = f"Watchlist: {cleared} cache entries cleared, {refreshed} symbols refreshed"

        elif resource == "all":
            # invalidate("") matches LIKE "%" — clears every cache_entry row
            cleared = await invalidate(db, "")
            await run_startup_sync(db)
            p = await sync_portfolio_prices(db)
            w = await sync_watchlist_prices(db)
            refreshed = p + w
            message = (
                f"Full cache cleared ({cleared} entries). "
                f"Re-fetched: {refreshed} portfolio+watchlist symbols"
            )

    except Exception as exc:
        logger.error("force_sync failed for resource=%s: %s", body.resource, exc)
        return {
            "cleared": cleared,
            "refreshed": 0,
            "message": (
                f"Server offline — cache cleared ({cleared} entries), "
                "re-fetch pending on next request"
            ),
        }

    return {"cleared": cleared, "refreshed": refreshed, "message": message}
```

- [ ] **Step 2: Verify import**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "from app.routers.sync import router; print('sync router OK')"
```

Expected: `sync router OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/routers/sync.py
git commit -m "feat(phase7): add sync router — GET /sync/client-status + POST /sync/force"
```

---

## Task 6: Update `main.py` — scheduler jobs + sync router

**Files:**
- Modify: `nivesh-client/app/main.py`

- [ ] **Step 1: Add pytz import and IST timezone at the top of `main.py`**

After the existing imports, add:

```python
import pytz
```

And define IST just before the scheduler job registrations inside `lifespan()`:

```python
IST = pytz.timezone("Asia/Kolkata")
```

- [ ] **Step 2: Import and include the sync router**

In `main.py`, update the routers import line from:

```python
from .routers import agent, auth, local, proxy
```

to:

```python
from .routers import agent, auth, local, proxy, sync as sync_router
```

And add after the existing `app.include_router(agent.router)` line:

```python
app.include_router(sync_router.router)
```

- [ ] **Step 3: Register the two new scheduler jobs in `lifespan()`**

In the `lifespan()` function, after the existing `scheduler.add_job(_cleanup, ...)` block, add:

```python
    # ── Token refresh job ──────────────────────────────────────────────────────
    from .services.token_refresh import refresh_if_expiring_soon
    from .services.http_client import SessionExpiredError

    async def _token_refresh():
        async with AsyncSessionLocal() as db:
            try:
                refreshed = await refresh_if_expiring_soon(db, window_seconds=300)
                if refreshed:
                    logger.info("[token_refresh] Access token refreshed proactively")
            except SessionExpiredError:
                logger.warning(
                    "[token_refresh] Refresh token expired — user must log in again"
                )
            except Exception as exc:
                logger.error("[token_refresh] Unexpected error: %s", exc)

    scheduler.add_job(
        _token_refresh,
        "interval",
        minutes=5,
        id="token_refresh",
        replace_existing=True,
    )

    # ── Portfolio price enrichment job (market hours) ──────────────────────────
    from apscheduler.triggers.cron import CronTrigger
    from .services.portfolio_sync import sync_portfolio_prices, sync_watchlist_prices

    async def _portfolio_sync():
        async with AsyncSessionLocal() as db:
            try:
                p = await sync_portfolio_prices(db)
                w = await sync_watchlist_prices(db)
                logger.info(
                    "[portfolio_sync] Scheduled run: %d holdings, %d watchlist refreshed",
                    p, w,
                )
            except Exception as exc:
                logger.error("[portfolio_sync] Scheduled run failed: %s", exc)

    scheduler.add_job(
        _portfolio_sync,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-16",
            minute="*/30",
            timezone=IST,
        ),
        id="portfolio_sync",
        replace_existing=True,
    )
```

Also update the log line after `scheduler.start()` from:

```python
    logger.info("[startup] APScheduler started (health_ping, cache_cleanup)")
```

to:

```python
    logger.info(
        "[startup] APScheduler started "
        "(health_ping, cache_cleanup, token_refresh, portfolio_sync)"
    )
```

And add `IST = pytz.timezone("Asia/Kolkata")` just before the scheduler job block:

```python
    IST = pytz.timezone("Asia/Kolkata")
```

- [ ] **Step 4: Verify the full app loads cleanly**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "from app.main import app; print('app loaded OK:', app.title)"
```

Expected: `app loaded OK: Nivesh Client API`

- [ ] **Step 5: Start the server and check startup logs show all 4 jobs**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
uvicorn app.main:app --port 8001 &
sleep 4
curl -s http://localhost:8001/health
kill %1 2>/dev/null
```

Expected startup log output (look for):
```
[startup] APScheduler started (health_ping, cache_cleanup, token_refresh, portfolio_sync)
```

- [ ] **Step 6: Commit**

```bash
git add nivesh-client/app/main.py
git commit -m "feat(phase7): register token_refresh + portfolio_sync scheduler jobs, include sync router"
```

---

## Task 7: Smoke Tests

**No server required for auth/status. Server required for force-sync and portfolio-sync.**

- [ ] **Step 1: Verify all new module imports in one shot**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "
from app.services.token_refresh import refresh_if_expiring_soon
from app.services.portfolio_sync import sync_portfolio_prices, sync_watchlist_prices
from app.routers.sync import router as sync_router
from app.routers.auth import router as auth_router
print('All Phase 7 imports OK')
print('Sync router routes:', [r.path for r in sync_router.routes])
print('Auth router routes:', [r.path for r in auth_router.routes])
"
```

Expected output:
```
All Phase 7 imports OK
Sync router routes: ['/sync/client-status', '/sync/force']
Auth router routes: ['/auth/login', '/auth/logout', '/auth/status']
```

- [ ] **Step 2: Test GET /auth/status when not logged in**

Start the server, then:

```bash
uvicorn app.main:app --port 8001 &
sleep 4
curl -s http://localhost:8001/auth/status | python3 -m json.tool
```

Expected (no auth_tokens row in fresh DB):
```json
{
    "logged_in": false,
    "username": null,
    "expires_at": null,
    "expires_in_seconds": null
}
```

- [ ] **Step 3: Test GET /sync/client-status**

```bash
curl -s http://localhost:8001/sync/client-status | python3 -m json.tool
```

Expected:
```json
{
    "is_online": false,
    "last_connected_at": null,
    "token_expires_in_seconds": null,
    "cache_entries_total": 0,
    "cache_entries_fresh": 0,
    "holdings_cached": 0,
    "holdings_total": 0,
    "watchlist_cached": 0,
    "watchlist_total": 0
}
```
(All zeros/false on a fresh DB is correct.)

- [ ] **Step 4: Test POST /sync/force with invalid resource**

```bash
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "invalid"}' | python3 -m json.tool
```

Expected: HTTP 400 with `"detail": "Unknown resource 'invalid'..."`

- [ ] **Step 5: Test POST /sync/force with valid resource (server offline)**

```bash
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "stocks"}' | python3 -m json.tool
```

Expected (server offline):
```json
{
    "cleared": 0,
    "refreshed": 0,
    "message": "Stocks cache cleared (0 entries) — data re-fetches on next proxy request"
}
```
(0 entries cleared because cache is empty on fresh DB — correct.)

- [ ] **Step 6: Stop server and commit smoke test results**

```bash
kill %1 2>/dev/null || true
```

- [ ] **Step 7: Update CLAUDE.md to mark P7 Done**

In `/home/prasad/dev_home/projects/stock_platform/CLAUDE.md`, update the phases table:

```markdown
| P7 | Done | Client: Sync engine + JWT refresh — proactive token refresh (5-min scheduler), portfolio/watchlist price enrichment (market-hours cron), GET /auth/status, POST /sync/force, GET /sync/client-status |
```

In `/home/prasad/dev_home/projects/stock_platform/nivesh-client/CLAUDE.md`, update the Environment Variables table to confirm `GROQ_API_KEY` is listed (already done in Phase 6) and add a note about the scheduler jobs:

Update the stack section (in Stack block) to add:
```
- **pytz** — IST-aware APScheduler cron triggers (portfolio_sync job)
```

- [ ] **Step 8: Final commit**

```bash
git add CLAUDE.md nivesh-client/CLAUDE.md
git commit -m "docs(phase7): mark P7 Done — sync engine + JWT refresh complete"
```

---

## Definition of Done Checklist

- [ ] `GET /auth/status` returns `{logged_in: false}` on fresh DB (no server call)
- [ ] `GET /sync/client-status` returns correct structure with zero counts on fresh DB
- [ ] `POST /sync/force {"resource": "invalid"}` returns HTTP 400
- [ ] `POST /sync/force {"resource": "stocks"}` returns 200 with `cleared` count
- [ ] `POST /sync/force {"resource": "all"}` returns 200 even when server offline
- [ ] Startup log shows: `APScheduler started (health_ping, cache_cleanup, token_refresh, portfolio_sync)`
- [ ] `token_refresh` job appears in APScheduler job list
- [ ] `portfolio_sync` job appears in APScheduler job list
- [ ] All Phase 7 imports succeed in one `python3 -c` command
- [ ] `CLAUDE.md` P7 row updated to Done
