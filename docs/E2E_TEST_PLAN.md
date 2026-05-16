# Nivesh Client — End-to-End Test Plan

**Role:** End-to-end tester  
**Scope:** All features across Phase 4–7 (Auth, Proxy/Cache, Portfolio, Watchlist, Agent, Sync Engine, JWT Refresh)  
**Environment:** Local — client on :8001, React UI on :5173, server on Render  

---

## Pre-Test Setup

### Environment checklist (run before any test)

```bash
# 1. Confirm .env exists with server URL and Groq key
cat ~/.nivesh/.env
```

Expected — must contain at minimum:
```
NIVESH_SERVER_URL=https://nivesh-server.onrender.com
GROQ_API_KEY=gsk_...
```

If not:
```bash
mkdir -p ~/.nivesh
cat > ~/.nivesh/.env << 'EOF'
NIVESH_SERVER_URL=https://nivesh-server.onrender.com
GROQ_API_KEY=gsk_your_key_here
EOF
```

```bash
# 2. Start the client API
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
uvicorn app.main:app --port 8001 --reload
```

Watch startup log for this exact line — confirms all 4 scheduler jobs are up:
```
[startup] APScheduler started (health_ping, cache_cleanup, token_refresh, portfolio_sync)
```

```bash
# 3. Start the React UI (separate terminal)
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client/frontend
npm run dev
```

```bash
# 4. Confirm both services are responding
curl -s http://localhost:8001/health
# → {"status":"ok","port":8001}
```

Open **http://localhost:5173** in browser — should show Login page.

---

## TC-01 — Auth: Login / Logout / Status

**Covers:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/status`  
**Server required:** Yes  

### TC-01a: Auth status when not logged in

```bash
curl -s http://localhost:8001/auth/status | python3 -m json.tool
```

**Expected:**
```json
{
    "logged_in": false,
    "username": null,
    "expires_at": null,
    "expires_in_seconds": null
}
```
**Pass criteria:** `logged_in` is `false`, all other fields null. No server call was made.

---

### TC-01b: Login with valid credentials

```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}' | python3 -m json.tool
```

**Expected:**
```json
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 900
}
```
**Pass criteria:** Both tokens present, `expires_in` > 0.

---

### TC-01c: Auth status after login (token stored in SQLite)

```bash
curl -s http://localhost:8001/auth/status | python3 -m json.tool
```

**Expected:**
```json
{
    "logged_in": true,
    "username": "admin",
    "expires_at": "2026-05-16T...",
    "expires_in_seconds": 870
}
```
**Pass criteria:** `logged_in: true`, `expires_in_seconds` between 1 and 900, `username` matches what you logged in with.

Also verify tokens are in SQLite — NOT in the browser:
```bash
sqlite3 ~/.nivesh/client.db "SELECT id, username, expires_at FROM auth_tokens;"
```
**Pass criteria:** Row exists with id=1.

---

### TC-01d: Login with wrong password

```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "wrongpassword"}' | python3 -m json.tool
```

**Expected:** HTTP 401
```json
{"detail": "Incorrect username or password"}
```

---

### TC-01e: Logout

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8001/auth/logout
```
**Expected:** `204`

```bash
curl -s http://localhost:8001/auth/status | python3 -m json.tool
```
**Expected:** `logged_in: false` — token row deleted from SQLite.

---

### TC-01f: UI Login flow

1. Open **http://localhost:5173** — redirects to `/login`
2. Enter correct credentials → click Login
3. **Pass:** Redirected to Dashboard, no token visible in browser dev tools → Application → LocalStorage
4. Open DevTools → Network tab → any API call → no `Authorization` header visible in the request from browser to client API (only visible on client-to-server proxy calls)

---

## TC-02 — Proxy + Cache: Stock Data

**Covers:** `GET /proxy/stocks/*`, TTL cache write + read  
**Server required:** Yes (must be logged in)  

### TC-02a: List stocks (cache miss → server fetch)

```bash
# Clear stocks cache first for a clean test
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "stocks"}'

# Fetch — this should hit the server
time curl -s "http://localhost:8001/proxy/stocks?limit=10" > /tmp/stocks_response.json
python3 -m json.tool < /tmp/stocks_response.json | head -30
```

**Pass criteria:** Returns a list of stocks. Response time noted (baseline for cache test).

---

### TC-02b: Stock detail (cache miss → cache write)

```bash
# First call — goes to server
time curl -s "http://localhost:8001/proxy/stocks/TCS" | python3 -m json.tool
```

**Expected:** Full stock object with symbol, name, sector, fundamentals, etc.

```bash
# Second call — should be served from cache (faster)
time curl -s "http://localhost:8001/proxy/stocks/TCS" | python3 -m json.tool
```

**Pass criteria:** Second call noticeably faster. Verify the cache entry was created:
```bash
sqlite3 ~/.nivesh/client.db \
  "SELECT key, fetched_at, ttl_seconds FROM cache_entries WHERE key LIKE 'stocks:detail:TCS%';"
```
**Expected:** One row with `fetched_at` timestamp and `ttl_seconds` = 3600.

---

### TC-02c: Stock search

```bash
curl -s "http://localhost:8001/proxy/stocks/search?q=Infosys" | python3 -m json.tool
```

**Pass criteria:** Returns list of matching stocks.

---

### TC-02d: Stock screener

```bash
curl -s "http://localhost:8001/proxy/stocks/screener?sort_by=fundamental_score&limit=5" | python3 -m json.tool
```

**Pass criteria:** Returns up to 5 stocks sorted by fundamental score.

---

## TC-03 — Proxy + Cache: Mutual Fund Data

**Covers:** `GET /proxy/funds/*`  
**Server required:** Yes  

### TC-03a: Fund categories

```bash
curl -s "http://localhost:8001/proxy/funds/categories" | python3 -m json.tool
```
**Pass criteria:** Returns a list of category strings (Equity, Debt, Hybrid, etc.)

---

### TC-03b: Fund detail

```bash
# Parag Parikh Flexi Cap — scheme code 120716
curl -s "http://localhost:8001/proxy/funds/120716" | python3 -m json.tool
```

**Pass criteria:** Returns fund object with scheme_name, amc, category, metrics.

---

### TC-03c: Fund NAV history

```bash
curl -s "http://localhost:8001/proxy/funds/120716/nav?period=1y" | python3 -m json.tool | head -20
```
**Pass criteria:** Returns array of `{date, nav}` objects spanning approximately 1 year.

---

### TC-03d: Fund compare

```bash
curl -s "http://localhost:8001/proxy/funds/compare?scheme_codes=120716,118989" | python3 -m json.tool
```
**Pass criteria:** Returns comparison object with both fund details side by side.

---

### TC-03e: Similar funds

```bash
curl -s "http://localhost:8001/proxy/funds/120716/similar" | python3 -m json.tool
```
**Pass criteria:** Returns list of funds in the same category.

---

### TC-03f: Fund list (paginated)

```bash
curl -s "http://localhost:8001/proxy/funds?limit=5&page=1" | python3 -m json.tool
```
**Pass criteria:** Returns 5 fund objects.

---

## TC-04 — Proxy + Cache: Benchmark / Index Data

**Covers:** `GET /proxy/benchmarks/*`  

### TC-04a: List benchmarks

```bash
curl -s "http://localhost:8001/proxy/benchmarks" | python3 -m json.tool
```
**Pass criteria:** Returns NIFTY50, SENSEX, NIFTYBANK and other indices.

---

### TC-04b: Benchmark NAV history

```bash
curl -s "http://localhost:8001/proxy/benchmarks/NIFTY50/nav?period=6m" | python3 -m json.tool | head -20
```
**Pass criteria:** Returns ~126 trading day NAV data points.

---

## TC-05 — Portfolio: Local CRUD

**Covers:** `POST/GET/PUT/DELETE /local/portfolio/holdings`, `/local/portfolio/transactions`  
**Server required:** No — all local SQLite  

### TC-05a: Add a stock holding

```bash
curl -s -X POST http://localhost:8001/local/portfolio/holdings \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "TCS",
    "asset_type": "STOCK",
    "quantity": 10,
    "average_cost": 3500.00,
    "notes": "Long-term hold"
  }' | python3 -m json.tool
```
**Expected:** Returns created holding with `id` field.  
**Pass criteria:** `id` is an integer, `symbol` = "TCS", `asset_type` = "STOCK".

---

### TC-05b: Add a fund holding

```bash
curl -s -X POST http://localhost:8001/local/portfolio/holdings \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "120716",
    "asset_type": "FUND",
    "quantity": 500,
    "average_cost": 65.50
  }' | python3 -m json.tool
```
**Pass criteria:** Returns holding with `asset_type` = "FUND".

---

### TC-05c: List all holdings

```bash
curl -s http://localhost:8001/local/portfolio/holdings | python3 -m json.tool
```
**Pass criteria:** Both holdings from TC-05a and TC-05b are present.

---

### TC-05d: Update a holding

```bash
# Replace {id} with the id from TC-05a
curl -s -X PUT http://localhost:8001/local/portfolio/holdings/1 \
  -H "Content-Type: application/json" \
  -d '{"quantity": 15, "average_cost": 3450.00}' | python3 -m json.tool
```
**Pass criteria:** Returns updated holding with `quantity` = 15.

---

### TC-05e: Add a transaction

```bash
curl -s -X POST http://localhost:8001/local/portfolio/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "holding_id": 1,
    "txn_type": "BUY",
    "quantity": 5,
    "price": 3500.00,
    "txn_date": "2026-05-01"
  }' | python3 -m json.tool
```
**Pass criteria:** Returns transaction with `txn_type` = "BUY".

---

### TC-05f: List transactions

```bash
curl -s "http://localhost:8001/local/portfolio/transactions" | python3 -m json.tool
```
**Pass criteria:** Transaction from TC-05e is present.

---

### TC-05g: Delete a holding

```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8001/local/portfolio/holdings/1
```
**Expected:** `204`

```bash
curl -s http://localhost:8001/local/portfolio/holdings | python3 -m json.tool
```
**Pass criteria:** Deleted holding is gone from the list.

---

### TC-05h: UI Portfolio page

1. Open **http://localhost:5173/portfolio**
2. Add a holding via the UI form
3. **Pass:** Holding appears in the list with current market price fetched from server
4. Edit quantity → **Pass:** Updated value persists after page refresh

---

## TC-06 — Watchlist: Local CRUD

**Covers:** `POST/GET/DELETE /local/watchlist`  
**Server required:** No  

### TC-06a: Add stocks to watchlist

```bash
curl -s -X POST http://localhost:8001/local/watchlist \
  -H "Content-Type: application/json" \
  -d '{"symbol": "INFY", "asset_type": "STOCK", "notes": "Watching for dip entry"}' | python3 -m json.tool
```
**Pass criteria:** Returns item with `id`, `symbol` = "INFY".

---

### TC-06b: Add fund to watchlist

```bash
curl -s -X POST http://localhost:8001/local/watchlist \
  -H "Content-Type: application/json" \
  -d '{"symbol": "118989", "asset_type": "FUND"}' | python3 -m json.tool
```

---

### TC-06c: View watchlist

```bash
curl -s http://localhost:8001/local/watchlist | python3 -m json.tool
```
**Pass criteria:** Both items from TC-06a and TC-06b visible.

---

### TC-06d: Remove from watchlist

```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8001/local/watchlist/1
```
**Expected:** `204`

---

### TC-06e: UI Watchlist page

1. Open **http://localhost:5173/watchlist**
2. Add "HDFC" via the search → Add button
3. **Pass:** Shows current price for HDFC stock
4. Remove it → **Pass:** Removed from list

---

## TC-07 — AI Agent Chat

**Covers:** `POST /agent/sessions`, `POST /agent/sessions/{id}/chat`, message history, memory  
**Server required:** Yes (agent fetches live data)  
**Groq key required:** Yes — `GROQ_API_KEY` in `~/.nivesh/.env`  

### TC-07a: Create a session

```bash
SESSION=$(curl -s -X POST http://localhost:8001/agent/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "E2E Test Session", "context_type": "general"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Session ID: $SESSION"
```
**Pass criteria:** `$SESSION` is a UUID string.

---

### TC-07b: Stock question (routes to stock agent)

```bash
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current P/E ratio of TCS and how does it compare to Infosys?"}' \
  | python3 -m json.tool
```
**Pass criteria:**
- `response` field contains a coherent answer mentioning TCS and Infosys
- `model_used` = "llama-3.3-70b-versatile"
- No error / no 500

---

### TC-07c: Fund question (routes to fund agent)

```bash
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Compare Parag Parikh Flexi Cap with Mirae Asset Large Cap fund. Which has better returns?"}' \
  | python3 -m json.tool
```
**Pass criteria:** Response compares the two funds with data. No hallucinated scheme codes.

---

### TC-07d: Portfolio question (routes to portfolio agent)

```bash
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is in my current portfolio?"}' \
  | python3 -m json.tool
```
**Pass criteria:** Response mentions holdings from your local SQLite portfolio. Agent fetches from `GET /local/portfolio/holdings`.

---

### TC-07e: Message history is persisted

```bash
curl -s "http://localhost:8001/agent/sessions/$SESSION/messages" | python3 -m json.tool
```
**Pass criteria:** Shows all messages from TC-07b, TC-07c, TC-07d — in order. `role` alternates between "user" and "assistant".

---

### TC-07f: Session list

```bash
curl -s http://localhost:8001/agent/sessions | python3 -m json.tool
```
**Pass criteria:** "E2E Test Session" appears in the list.

---

### TC-07g: Agent memory

```bash
# Write a preference
curl -s -X PUT "http://localhost:8001/agent/memory/risk_profile" \
  -H "Content-Type: application/json" \
  -d '{"value": "Conservative — prefer large cap, low debt, dividend payers"}' | python3 -m json.tool

# Read all memories
curl -s http://localhost:8001/agent/memory | python3 -m json.tool

# Use it in a conversation (agent should reference this context)
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Recommend 3 stocks suitable for my investment style"}' | python3 -m json.tool
```
**Pass criteria:** Agent response reflects the conservative/large cap/dividend preference stored in memory.

---

### TC-07h: Delete session

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE "http://localhost:8001/agent/sessions/$SESSION"
```
**Expected:** `204`

```bash
curl -s "http://localhost:8001/agent/sessions/$SESSION/messages" | python3 -m json.tool
```
**Expected:** 404 or empty list.

---

### TC-07i: Agent with GROQ_API_KEY missing

Temporarily break the key:
```bash
# In a new terminal (don't modify the .env file)
GROQ_API_KEY="" uvicorn app.main:app --port 8002
```
Then:
```bash
SESSION2=$(curl -s -X POST http://localhost:8002/agent/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "No key test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "http://localhost:8002/agent/sessions/$SESSION2/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}' | python3 -m json.tool
```
**Expected:** HTTP 503 with `"detail": "GROQ_API_KEY not configured"`  
**Pass criteria:** Error is clear, server does not crash.

```bash
# Clean up
kill $(lsof -ti:8002) 2>/dev/null || true
```

---

## TC-08 — Sync Engine: Cache Health

**Covers:** `GET /sync/client-status`  
**Server required:** No — all local SQLite reads  

### TC-08a: Status on fresh / offline state

```bash
curl -s http://localhost:8001/sync/client-status | python3 -m json.tool
```
**Pass criteria (all must hold):**

| Field | Expected |
|---|---|
| `is_online` | `true` or `false` (depends on server reachability) |
| `last_connected_at` | ISO timestamp or `null` |
| `token_expires_in_seconds` | integer if logged in, `null` if not |
| `cache_entries_total` | integer ≥ 0 |
| `cache_entries_fresh` | ≤ `cache_entries_total` |
| `holdings_total` | matches `sqlite3 ~/.nivesh/client.db "SELECT COUNT(*) FROM portfolio_holdings;"` |
| `watchlist_total` | matches `sqlite3 ~/.nivesh/client.db "SELECT COUNT(*) FROM watchlist;"` |
| `holdings_cached` | ≤ `holdings_total` |
| `watchlist_cached` | ≤ `watchlist_total` |

---

### TC-08b: Status after fetching stock data

```bash
# Fetch a stock detail to populate cache
curl -s "http://localhost:8001/proxy/stocks/TCS" > /dev/null

# Check that cache_entries_total increased
curl -s http://localhost:8001/sync/client-status | python3 -m json.tool
```
**Pass criteria:** `cache_entries_total` ≥ 1 and `cache_entries_fresh` ≥ 1.

---

## TC-09 — Sync Engine: Force Sync

**Covers:** `POST /sync/force`  

### TC-09a: Invalid resource → 400

```bash
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "nonsense"}' | python3 -m json.tool
```
**Expected:** HTTP 400, `detail` lists valid resource names.

---

### TC-09b: Force sync — stocks (clear only, no re-fetch)

```bash
# First populate the stocks cache
curl -s "http://localhost:8001/proxy/stocks/TCS" > /dev/null
curl -s "http://localhost:8001/proxy/stocks/INFY" > /dev/null

BEFORE=$(sqlite3 ~/.nivesh/client.db "SELECT COUNT(*) FROM cache_entries WHERE key LIKE 'stocks%';")
echo "Cache rows before: $BEFORE"

curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "stocks"}' | python3 -m json.tool

AFTER=$(sqlite3 ~/.nivesh/client.db "SELECT COUNT(*) FROM cache_entries WHERE key LIKE 'stocks%';")
echo "Cache rows after: $AFTER"
```
**Pass criteria:**
- Response: `cleared` > 0, `message` contains "re-fetches on next proxy request"
- `AFTER` = 0 (cache cleared)

---

### TC-09c: Force sync — portfolio (clear + re-fetch)

```bash
# Ensure there's at least one holding with a known symbol
sqlite3 ~/.nivesh/client.db "SELECT symbol, asset_type FROM portfolio_holdings LIMIT 3;"

curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "portfolio"}' | python3 -m json.tool
```

**Pass criteria (if server is online):**
```json
{
    "cleared": 0,
    "refreshed": 2,
    "message": "Portfolio: 0 cache entries cleared, 2 symbols refreshed"
}
```
- `refreshed` matches number of unique holdings
- New cache entries appear in SQLite for each holding's symbol

**Pass criteria (if server is offline):**
```json
{
    "cleared": 0,
    "refreshed": 0,
    "message": "Server offline — cache cleared (0 entries), re-fetch pending on next request"
}
```
- Returns HTTP **200** — not a 500. This is critical.

---

### TC-09d: Force sync — watchlist

```bash
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "watchlist"}' | python3 -m json.tool
```
**Pass criteria:** `refreshed` > 0 if server is online, 200 either way.

---

### TC-09e: Force sync — benchmarks

```bash
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "benchmarks"}' | python3 -m json.tool
```
**Pass criteria:** `cleared` ≥ 0, `refreshed` = 1 if server online.

---

### TC-09f: Force sync — all (nuclear)

```bash
BEFORE_TOTAL=$(sqlite3 ~/.nivesh/client.db "SELECT COUNT(*) FROM cache_entries;")
echo "Total cache entries before: $BEFORE_TOTAL"

curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "all"}' | python3 -m json.tool

echo "Response received — checking cache..."
sleep 2
AFTER_TOTAL=$(sqlite3 ~/.nivesh/client.db "SELECT COUNT(*) FROM cache_entries;")
echo "Total cache entries after: $AFTER_TOTAL"
```
**Pass criteria:**
- `cleared` = `BEFORE_TOTAL`
- Response is HTTP 200 regardless of server state
- After sync, `AFTER_TOTAL` ≥ 0 (may have been re-populated by startup sync)

---

## TC-10 — JWT Refresh: Proactive Token Refresh

**Covers:** `services/token_refresh.py`, `token_refresh` APScheduler job  
**Server required:** Yes (to issue tokens and accept refresh)  

### TC-10a: Token refresh logic — unit level

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 - << 'EOF'
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

async def test_token_refresh_skip():
    """Verify function returns False when token has plenty of time remaining."""
    from app.services.token_refresh import refresh_if_expiring_soon
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        # If no auth row, should return False cleanly
        result = await refresh_if_expiring_soon(db, window_seconds=300)
        print(f"No auth row → returned: {result}")
        assert result is False, "Expected False when not logged in"
        print("PASS: returns False when not logged in")

asyncio.run(test_token_refresh_skip())
EOF
```
**Pass criteria:** Prints `PASS: returns False when not logged in` — no crash.

---

### TC-10b: Token expiry window check (after login)

Login first (TC-01b), then:

```bash
python3 - << 'EOF'
import asyncio
from app.services.token_refresh import refresh_if_expiring_soon
from app.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as db:
        # Window larger than remaining — token is fresh, should skip
        result = await refresh_if_expiring_soon(db, window_seconds=1)
        print(f"window=1s → result: {result}  (expected False — token won't expire in 1 second)")
        
        # Window much larger than token lifetime — should attempt refresh
        result2 = await refresh_if_expiring_soon(db, window_seconds=99999)
        print(f"window=99999s → result: {result2}  (expected True — token expires within 99999s)")

asyncio.run(main())
EOF
```
**Pass criteria:**
- `window=1s` → `False` (token is fresh)
- `window=99999s` → `True` (forces refresh), and a new `expires_at` appears in SQLite

---

### TC-10c: Scheduler job fires every 5 minutes (observe in logs)

Watch the server log after starting:
```bash
# In the uvicorn terminal, you will see after ~5 minutes:
# Either:
#   Token valid for 570 more seconds — skipping proactive refresh
# Or:
#   [token_refresh] Access token refreshed proactively
```
**Pass criteria:** One of the above log lines appears every 5 minutes. Scheduler does NOT crash the server.

---

### TC-10d: Server offline during token refresh (graceful)

```bash
python3 - << 'EOF'
import asyncio
from unittest.mock import patch
import httpx
from app.services.token_refresh import refresh_if_expiring_soon
from app.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as db:
        # Simulate network error
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("offline")):
            result = await refresh_if_expiring_soon(db, window_seconds=99999)
            print(f"ConnectError → result: {result}")
            assert result is False, "Should return False on network error"
            print("PASS: returns False gracefully on server offline")

asyncio.run(main())
EOF
```
**Pass criteria:** Prints `PASS` — no exception propagated, server not crashed.

---

## TC-11 — Portfolio Sync: Price Enrichment

**Covers:** `services/portfolio_sync.py`, startup cache pre-warm  

### TC-11a: sync_portfolio_prices with no holdings

```bash
python3 - << 'EOF'
import asyncio
from app.services.portfolio_sync import sync_portfolio_prices
from app.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as db:
        count = await sync_portfolio_prices(db)
        print(f"sync_portfolio_prices returned: {count}")

asyncio.run(main())
EOF
```
**Pass criteria:** Returns an integer (0 if no holdings, or count of symbols refreshed). No crash.

---

### TC-11b: sync_watchlist_prices

```bash
python3 - << 'EOF'
import asyncio
from app.services.portfolio_sync import sync_watchlist_prices
from app.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as db:
        count = await sync_watchlist_prices(db)
        print(f"sync_watchlist_prices returned: {count}")

asyncio.run(main())
EOF
```
**Pass criteria:** Returns integer equal to number of watchlist items whose cache was refreshed.

---

### TC-11c: Startup pre-warm (restart the server)

```bash
# Stop the server, clear all cache, restart, and watch the startup log
sqlite3 ~/.nivesh/client.db "DELETE FROM cache_entries;"
echo "Cache cleared"

# Restart uvicorn and immediately watch the log
uvicorn app.main:app --port 8001 2>&1 | head -30
```

**Pass criteria in startup log:**
```
[startup] Warming cache...
[startup] Cache warm complete — portfolio: N symbols, watchlist: M symbols
```
Where N = portfolio holding count, M = watchlist item count.

---

## TC-12 — Offline Resilience

**What to test:** Client stays functional when the Render server is unreachable.

### TC-12a: Stale cache served when server offline

```bash
# Step 1: Prime the cache while online
curl -s "http://localhost:8001/proxy/stocks/TCS" > /dev/null

# Step 2: Point to a broken server URL
# In ~/.nivesh/.env temporarily set:
# NIVESH_SERVER_URL=http://localhost:19999  (nothing listening here)
# Then restart the client API

# Step 3: Fetch TCS — should serve from stale cache
curl -s "http://localhost:8001/proxy/stocks/TCS" | python3 -m json.tool
```
**Pass criteria:** Returns TCS data from cache (not a 503). Response may include `"cached": true` or similar.

---

### TC-12b: Sync client status when offline

```bash
curl -s http://localhost:8001/sync/client-status | python3 -m json.tool
```
**Pass criteria:** `is_online: false`, all other fields still return correctly — no 500.

---

### TC-12c: Force sync when offline returns 200

```bash
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "all"}' | python3 -m json.tool
```
**Pass criteria:**
- HTTP **200** (not 500 or 503)
- `refreshed: 0`
- `message` contains "Server offline" or similar

---

### TC-12d: Auth status works offline

```bash
curl -s http://localhost:8001/auth/status | python3 -m json.tool
```
**Pass criteria:** Correct response from SQLite — no server call needed.

---

## TC-13 — System Endpoints

### TC-13a: Health check

```bash
curl -s http://localhost:8001/health | python3 -m json.tool
```
**Expected:** `{"status": "ok", "port": 8001}`

---

### TC-13b: Full status endpoint

```bash
curl -s http://localhost:8001/status | python3 -m json.tool
```
**Expected fields:** `client_version`, `is_online`, `last_connected_at`, `server_url`, `cached_resources`, `db_path`

---

### TC-13c: API docs accessible

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/docs
```
**Expected:** `200`

---

## TC-14 — React UI: Full Page Walkthrough

With both servers running (:8001 API + :5173 UI):

| Step | Page | What to verify |
|---|---|---|
| 1 | `/login` | Redirected here before login. Form submits cleanly. Error shown for wrong password. |
| 2 | `/dashboard` (after login) | Market overview loads. SyncStatusBar shows online/offline status. |
| 3 | `/stocks` | Stock list loads with search. |
| 4 | `/stocks/TCS` | Stock detail page — price, fundamentals, scoring chart visible. |
| 5 | `/screener` | Screener table loads, filter controls work. |
| 6 | `/funds` | Fund list loads, category filter works. |
| 7 | `/funds/120716` | Fund detail with NAV chart. |
| 8 | `/funds/compare` | Select 2 funds — comparison table appears. |
| 9 | `/portfolio` | Holdings list visible. Add/Edit/Delete a holding. |
| 10 | `/watchlist` | Watchlist visible. Add a symbol via search, remove it. |
| 11 | `/agent` | Start a session. Ask a stock question. Response appears. Ask portfolio question. |
| 12 | Logout | Clicking logout redirects to `/login`. |
| 13 | Protected routes | Try navigating to `/portfolio` without login — redirects to `/login`. |

---

## Test Execution Summary Checklist

```
TC-01a  [ ] Auth status — not logged in
TC-01b  [ ] Login — valid credentials
TC-01c  [ ] Auth status — logged in
TC-01d  [ ] Login — wrong password (401)
TC-01e  [ ] Logout (204, token cleared)
TC-01f  [ ] UI login flow, no token in browser

TC-02a  [ ] Stock list — cache miss
TC-02b  [ ] Stock detail — cache write + faster second call
TC-02c  [ ] Stock search
TC-02d  [ ] Screener

TC-03a  [ ] Fund categories
TC-03b  [ ] Fund detail
TC-03c  [ ] Fund NAV history
TC-03d  [ ] Fund compare
TC-03e  [ ] Similar funds
TC-03f  [ ] Fund list paginated

TC-04a  [ ] Benchmark list
TC-04b  [ ] Benchmark NAV history

TC-05a  [ ] Add stock holding
TC-05b  [ ] Add fund holding
TC-05c  [ ] List holdings
TC-05d  [ ] Update holding
TC-05e  [ ] Add transaction
TC-05f  [ ] List transactions
TC-05g  [ ] Delete holding
TC-05h  [ ] UI portfolio page

TC-06a  [ ] Add stock to watchlist
TC-06b  [ ] Add fund to watchlist
TC-06c  [ ] View watchlist
TC-06d  [ ] Remove from watchlist
TC-06e  [ ] UI watchlist page

TC-07a  [ ] Create agent session
TC-07b  [ ] Stock question → agent response
TC-07c  [ ] Fund question → agent response
TC-07d  [ ] Portfolio question → agent response
TC-07e  [ ] Message history persisted
TC-07f  [ ] Session list
TC-07g  [ ] Agent memory read/write
TC-07h  [ ] Delete session
TC-07i  [ ] No GROQ key → 503 (not crash)

TC-08a  [ ] Client status fields correct
TC-08b  [ ] Cache count increments after proxy fetch

TC-09a  [ ] Force sync invalid resource → 400
TC-09b  [ ] Force sync stocks — clears cache
TC-09c  [ ] Force sync portfolio — clears + re-fetches (200 even offline)
TC-09d  [ ] Force sync watchlist
TC-09e  [ ] Force sync benchmarks
TC-09f  [ ] Force sync all — clears everything

TC-10a  [ ] Token refresh — no auth row → False
TC-10b  [ ] Token refresh — window check
TC-10c  [ ] Scheduler fires every 5 min (log observation)
TC-10d  [ ] Token refresh — server offline → False (not crash)

TC-11a  [ ] sync_portfolio_prices runs without error
TC-11b  [ ] sync_watchlist_prices runs without error
TC-11c  [ ] Startup pre-warm logged correctly

TC-12a  [ ] Stale cache served when offline
TC-12b  [ ] Client status → is_online:false (no crash)
TC-12c  [ ] Force sync all offline → 200
TC-12d  [ ] Auth status works offline

TC-13a  [ ] GET /health → 200
TC-13b  [ ] GET /status → all fields present
TC-13c  [ ] GET /docs → 200

TC-14   [ ] Full UI walkthrough — all 13 pages/actions
```

---

## Defect Severity Guide

| Severity | Example |
|---|---|
| **P0 — Blocker** | Server crash (5xx from unexpected exception), login broken, SQLite corrupted |
| **P1 — Critical** | Force sync returns 500 when server offline, agent crashes on missing key |
| **P2 — Major** | Cache not written on proxy fetch, wrong HTTP status codes |
| **P3 — Minor** | Log messages unclear, minor UI layout issues |
| **P4 — Cosmetic** | Typos, extra whitespace in JSON, non-breaking warnings |
