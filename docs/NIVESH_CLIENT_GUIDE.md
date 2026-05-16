# Nivesh Client — Setup & Feature Testing Guide

The Nivesh client is a local FastAPI + React application that runs on your machine. It stores your portfolio, watchlist, and agent chat history in a local SQLite database and proxies all market data through the Nivesh server (Render.com). JWT tokens never touch the browser — they live in SQLite only.

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| A running Nivesh server | — | `https://nivesh-server.onrender.com` or local |

---

## Part 1 — First-Time Setup

### Step 1: Install Python dependencies

From the repo root:

```bash
pip install -r requirements-dev.txt
```

This installs `nivesh-shared` (shared schemas) in editable mode and all client dependencies.

Alternatively, install the client directly:

```bash
cd nivesh-client
pip install -r requirements.txt
pip install -e ../nivesh-shared
```

### Step 2: Create the config directory and `.env`

The client reads all config from `~/.nivesh/.env`. Create it:

```bash
mkdir -p ~/.nivesh
cat > ~/.nivesh/.env << 'EOF'
# URL of the Nivesh server (local or Render)
NIVESH_SERVER_URL=http://localhost:8000

# For the cloud server use:
# NIVESH_SERVER_URL=https://nivesh-server.onrender.com

# Client port (default 8001)
CLIENT_PORT=8001

# Path to local SQLite DB (auto-created on first run)
SQLITE_DB_PATH=/home/$USER/.nivesh/nivesh_client.db

# Required for AI agent chat
GROQ_API_KEY=gsk_your_key_here
EOF
```

Get a free `GROQ_API_KEY` at [console.groq.com](https://console.groq.com) — the free tier is sufficient.

### Step 3: Start the client API

```bash
cd nivesh-client
uvicorn app.main:app --port 8001 --reload
```

On first run you will see:

```
[startup] SQLite migrations up to date
[startup] SQLite DB ready: /home/<user>/.nivesh/nivesh_client.db
[startup] APScheduler started (health_ping, cache_cleanup, token_refresh, portfolio_sync)
[startup] Nivesh Client ready — port 8001
```

The SQLite database is created automatically at `~/.nivesh/nivesh_client.db`. No manual migration step needed.

### Step 4: Install and start the React UI

In a second terminal:

```bash
cd nivesh-client/frontend
npm install
npm run dev
```

The UI starts on **http://localhost:5173** (Vite dev server).

> **Note:** The React UI calls the client API at `http://localhost:8001`. Make sure the API server is running before opening the UI.

---

## Part 2 — All Features: End-to-End Testing

Use the UI at **http://localhost:5173** alongside the API docs at **http://localhost:8001/docs**.

---

### Feature 1: Authentication (Login / Logout)

**What it does:** Forwards login to the Nivesh server, stores JWT tokens in local SQLite — never in the browser.

**Test via UI:**
1. Open http://localhost:5173
2. You are redirected to the Login page
3. Enter your username and password (created via `scripts/create_admin.py` on the server)
4. Click **Login**
5. You are redirected to the Dashboard

**Test via curl:**

```bash
# Login
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}' | python3 -m json.tool
```

Expected:
```json
{
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 900
}
```

**Check login state without hitting the server:**

```bash
curl -s http://localhost:8001/auth/status | python3 -m json.tool
```

Expected when logged in:
```json
{
    "logged_in": true,
    "username": "admin",
    "expires_at": "2026-05-16T14:30:00+00:00",
    "expires_in_seconds": 720
}
```

Expected when not logged in:
```json
{
    "logged_in": false,
    "username": null,
    "expires_at": null,
    "expires_in_seconds": null
}
```

**Logout:**

```bash
curl -s -X POST http://localhost:8001/auth/logout
# → 204 No Content (tokens cleared from SQLite)
```

---

### Feature 2: Stock Market Data (via Proxy)

**What it does:** Proxies stock requests to the server, injects JWT automatically, caches responses in local SQLite.

**Test via curl:**

```bash
# Search for stocks
curl -s "http://localhost:8001/stocks/search?q=TCS" | python3 -m json.tool

# Stock detail
curl -s "http://localhost:8001/stocks/TCS" | python3 -m json.tool

# Stock screener (top stocks by fundamental score)
curl -s "http://localhost:8001/stocks/screener?sort_by=fundamental_score&limit=10" | python3 -m json.tool

# List all stocks
curl -s "http://localhost:8001/stocks" | python3 -m json.tool
```

**Test via UI:**
1. Navigate to **Stocks** page
2. Use the search bar to find a stock (e.g., "TCS" or "Infosys")
3. Click a result to open the stock detail page — shows price, fundamentals, scoring
4. Navigate to **Screener** — filter stocks by sector, P/E ratio, market cap, etc.

**Verify caching:**

```bash
# First call — fetches from server
time curl -s "http://localhost:8001/stocks/TCS" > /dev/null

# Second call — served from local SQLite cache (should be faster)
time curl -s "http://localhost:8001/stocks/TCS" > /dev/null
```

---

### Feature 3: Mutual Fund Data (via Proxy)

**What it does:** Proxies fund data from the server, caches NAV and metrics locally.

**Test via curl:**

```bash
# List funds (paginated)
curl -s "http://localhost:8001/funds?limit=5" | python3 -m json.tool

# Fund categories
curl -s "http://localhost:8001/funds/categories" | python3 -m json.tool

# Fund detail by scheme code (e.g., 120716 = Parag Parikh Flexi Cap)
curl -s "http://localhost:8001/funds/120716" | python3 -m json.tool

# Fund NAV history
curl -s "http://localhost:8001/funds/120716/nav?period=1y" | python3 -m json.tool

# Compare funds (comma-separated scheme codes)
curl -s "http://localhost:8001/funds/compare?scheme_codes=120716,118989" | python3 -m json.tool

# Similar funds
curl -s "http://localhost:8001/funds/120716/similar" | python3 -m json.tool

# List AMCs
curl -s "http://localhost:8001/funds/amcs" | python3 -m json.tool
```

**Test via UI:**
1. Navigate to **Mutual Funds** page — browse and filter by category, AMC, rating
2. Open a fund — shows NAV chart, metrics, fund house info
3. Use **Compare** page — select 2–3 funds side by side

---

### Feature 4: Benchmark / Index Data

**What it does:** Provides index NAV history (NIFTY50, SENSEX, NIFTYBANK, etc.).

**Test via curl:**

```bash
# List benchmarks
curl -s "http://localhost:8001/benchmarks" | python3 -m json.tool

# Benchmark detail
curl -s "http://localhost:8001/benchmarks/NIFTY50" | python3 -m json.tool

# Benchmark NAV history
curl -s "http://localhost:8001/benchmarks/NIFTY50/nav?period=1y" | python3 -m json.tool
```

---

### Feature 5: Portfolio Management (Local)

**What it does:** CRUD for your personal holdings and transactions — stored in local SQLite only, never sent to the server.

**Test via curl:**

```bash
# Add a holding
curl -s -X POST http://localhost:8001/portfolio/holdings \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "TCS",
    "asset_type": "STOCK",
    "quantity": 10,
    "average_cost": 3500.00,
    "notes": "Long-term hold"
  }' | python3 -m json.tool

# Add a fund holding
curl -s -X POST http://localhost:8001/portfolio/holdings \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "120716",
    "asset_type": "FUND",
    "quantity": 500,
    "average_cost": 65.50
  }' | python3 -m json.tool

# View all holdings
curl -s http://localhost:8001/portfolio/holdings | python3 -m json.tool

# Update a holding (use the id from the list above)
curl -s -X PUT http://localhost:8001/portfolio/holdings/1 \
  -H "Content-Type: application/json" \
  -d '{"quantity": 15, "average_cost": 3450.00}' | python3 -m json.tool

# Add a transaction
curl -s -X POST http://localhost:8001/portfolio/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "holding_id": 1,
    "txn_type": "BUY",
    "quantity": 5,
    "price": 3500.00,
    "txn_date": "2026-05-01"
  }' | python3 -m json.tool

# View transactions
curl -s "http://localhost:8001/portfolio/transactions" | python3 -m json.tool

# Delete a holding
curl -s -X DELETE http://localhost:8001/portfolio/holdings/1
```

**Test via UI:**
1. Navigate to **Portfolio** page
2. Add a stock holding using the "+" button
3. Add a mutual fund holding
4. The portfolio shows current prices fetched live from the server

---

### Feature 6: Watchlist (Local)

**What it does:** Track stocks and funds you're watching — stored in local SQLite.

**Test via curl:**

```bash
# Add to watchlist
curl -s -X POST http://localhost:8001/watchlist \
  -H "Content-Type: application/json" \
  -d '{"symbol": "INFY", "asset_type": "STOCK", "notes": "Watching for entry"}' | python3 -m json.tool

# Add a fund to watchlist
curl -s -X POST http://localhost:8001/watchlist \
  -H "Content-Type: application/json" \
  -d '{"symbol": "118989", "asset_type": "FUND"}' | python3 -m json.tool

# View watchlist
curl -s http://localhost:8001/watchlist | python3 -m json.tool

# Remove from watchlist (use id from list)
curl -s -X DELETE http://localhost:8001/watchlist/1
```

**Test via UI:**
1. Navigate to **Watchlist** page
2. Add symbols using the search bar
3. Items show live prices fetched via the proxy

---

### Feature 7: AI Agent Chat

**What it does:** Multi-agent system with a LangGraph supervisor routing to 3 specialist agents (stock/fund/portfolio) backed by ChatGroq (llama-3.3-70b-versatile). Requires `GROQ_API_KEY` in `~/.nivesh/.env`.

**Create a session and chat via curl:**

```bash
# Create a session
SESSION=$(curl -s -X POST http://localhost:8001/agent/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "My first session", "context_type": "general"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Session ID: $SESSION"

# Send a message (uses LangGraph multi-agent pipeline)
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current P/E ratio of TCS and how does it compare to Infosys?"}' | python3 -m json.tool

# Try a fund question
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Compare Parag Parikh Flexi Cap with Mirae Asset Large Cap fund"}' | python3 -m json.tool

# Try a portfolio question
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my current portfolio?"}' | python3 -m json.tool

# View session message history
curl -s "http://localhost:8001/agent/sessions/$SESSION/messages" | python3 -m json.tool

# List all sessions
curl -s http://localhost:8001/agent/sessions | python3 -m json.tool
```

**Test via UI:**
1. Navigate to **Agent Chat** page
2. Start a new session
3. Ask questions like:
   - "What is TCS's fundamental score?"
   - "Which large cap mutual funds have beaten NIFTY50 over 5 years?"
   - "Show me my portfolio performance"
4. The agent routes your question to the right specialist automatically

**Agent memory (persistent across sessions):**

```bash
# Write a memory
curl -s -X PUT "http://localhost:8001/agent/memory/investment_style" \
  -H "Content-Type: application/json" \
  -d '{"value": "Long-term value investor, prefers large cap, avoids high debt companies"}' | python3 -m json.tool

# Read all memories
curl -s http://localhost:8001/agent/memory | python3 -m json.tool

# Delete a memory
curl -s -X DELETE http://localhost:8001/agent/memory/investment_style
```

---

### Feature 8: Sync Engine

**What it does:** Background scheduler pre-warms the cache for portfolio and watchlist symbols during market hours. Provides visibility into cache health and a force-sync escape hatch.

#### 8a. Cache Health Status

```bash
curl -s http://localhost:8001/sync/client-status | python3 -m json.tool
```

Expected response shape:
```json
{
    "is_online": true,
    "last_connected_at": "2026-05-16T09:00:00+00:00",
    "token_expires_in_seconds": 720,
    "cache_entries_total": 12,
    "cache_entries_fresh": 10,
    "holdings_cached": 2,
    "holdings_total": 2,
    "watchlist_cached": 4,
    "watchlist_total": 5
}
```

Fields explained:
- `is_online` — did the last health ping succeed?
- `cache_entries_fresh` — entries whose TTL has not expired
- `holdings_cached` — how many portfolio holdings have a fresh cache entry
- `watchlist_total` — total items in your watchlist

#### 8b. Force Sync — by resource type

```bash
# Refresh fund list cache
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "funds"}' | python3 -m json.tool

# Clear stocks cache (re-fetched on next proxy request)
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "stocks"}' | python3 -m json.tool

# Re-fetch prices for all portfolio holdings
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "portfolio"}' | python3 -m json.tool

# Re-fetch prices for watchlist items
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "watchlist"}' | python3 -m json.tool

# Nuclear option — clear everything and re-fetch all
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "all"}' | python3 -m json.tool

# Invalid resource returns 400
curl -s -X POST http://localhost:8001/sync/force \
  -H "Content-Type: application/json" \
  -d '{"resource": "invalid"}' | python3 -m json.tool
```

Valid resource values: `funds`, `stocks`, `benchmarks`, `portfolio`, `watchlist`, `all`

#### 8c. Proactive JWT Refresh (scheduler)

The `token_refresh` job runs every 5 minutes. When the access token is within 5 minutes of expiry, it silently refreshes using the stored refresh token. Watch for this in the server logs:

```
[token_refresh] Access token refreshed proactively
```

Or if the token is still valid:
```
Token valid for 420 more seconds — skipping proactive refresh
```

To verify the job is registered:
```bash
curl -s http://localhost:8001/status | python3 -m json.tool
```

---

### Feature 9: System Health and Status

```bash
# Lightweight health check (always 200)
curl -s http://localhost:8001/health | python3 -m json.tool

# Full status — connectivity, cache count, server URL
curl -s http://localhost:8001/status | python3 -m json.tool

# Sync status (legacy endpoint)
curl -s http://localhost:8001/sync/status | python3 -m json.tool
```

---

## Part 3 — Scheduler Jobs Reference

| Job ID | Trigger | What it does |
|---|---|---|
| `health_ping` | Every 60s | Pings server `/health`, updates `is_online` in SQLite |
| `cache_cleanup` | Every 1h | Deletes expired `cache_entries` rows from SQLite |
| `token_refresh` | Every 5 min | Refreshes JWT access token if within 5-min expiry window |
| `portfolio_sync` | Mon–Fri 09:00–16:00 IST, every 30 min | Pre-warms cache for all portfolio + watchlist symbols |

All four jobs appear in the startup log:
```
[startup] APScheduler started (health_ping, cache_cleanup, token_refresh, portfolio_sync)
```

---

## Part 4 — Troubleshooting

### Server is offline / `is_online: false`

The client works in offline mode — it serves stale cache entries when the server is unreachable. The `health_ping` job updates the online status every 60 seconds. If you bring the server back up, the status recovers automatically.

Force a connectivity check:
```bash
curl -s http://localhost:8001/health
curl -s http://localhost:8001/sync/client-status
```

### `GROQ_API_KEY not configured` error on chat

The agent chat requires the Groq API key:

```bash
echo 'GROQ_API_KEY=gsk_your_key_here' >> ~/.nivesh/.env
# Restart the client API server
```

### Token expired / `logged_in: false`

```bash
# Check token state
curl -s http://localhost:8001/auth/status | python3 -m json.tool

# Re-login
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}'
```

### Reset the SQLite database (wipe all local data)

```bash
# Stop the client server first, then:
rm ~/.nivesh/nivesh_client.db
# On next startup, Alembic recreates all tables automatically
```

### View the SQLite database directly

```bash
sqlite3 ~/.nivesh/nivesh_client.db

# Useful queries:
.tables
SELECT * FROM auth_tokens;
SELECT * FROM server_config;
SELECT key, fetched_at, ttl_seconds FROM cache_entries ORDER BY fetched_at DESC LIMIT 20;
SELECT * FROM portfolio_holdings;
SELECT * FROM watchlist;
SELECT id, title, created_at FROM agent_sessions;
```

---

## Part 5 — API Reference Summary

The full interactive API docs are available at **http://localhost:8001/docs** when the client is running.

| Prefix | Description |
|---|---|
| `GET/POST /auth/*` | Login, logout, auth status |
| `GET /stocks/*` | Stock search, detail, screener |
| `GET /funds/*` | Fund list, detail, NAV, compare, similar |
| `GET /benchmarks/*` | Index detail and NAV history |
| `GET/POST/PUT/DELETE /portfolio/*` | Holdings and transactions (local SQLite) |
| `GET/POST/DELETE /watchlist` | Watchlist items (local SQLite) |
| `GET/POST/DELETE /agent/*` | Agent sessions, chat, memory |
| `GET /sync/client-status` | Cache health snapshot |
| `POST /sync/force` | Force cache clear + re-fetch |
| `GET /health` | Liveness check |
| `GET /status` | Connectivity + cache summary |
