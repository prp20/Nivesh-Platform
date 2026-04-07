# Getting Started with Claude Code on Nivesh Platform
## Your complete guide to working on the Stock Market extension locally

---

## Part 1 — Install Claude Code

Claude Code is a command-line tool that gives an AI agent direct access to your terminal, files, and git — so it can read your actual code, run commands, and make targeted edits instead of just chatting.

### macOS / Linux

```bash
# Requires Node.js 18+. Check first:
node --version

# Install Claude Code globally
npm install -g @anthropic-ai/claude-code

# Verify
claude --version
```

### Windows

```bash
# Use WSL2 (Windows Subsystem for Linux) — Claude Code works best in a Unix shell
# Then run the same commands as above inside your WSL terminal
npm install -g @anthropic-ai/claude-code
```

### Login

```bash
claude login
# Opens a browser — log in with your Anthropic account
```

---

## Part 2 — Get the Repo Ready

```bash
# Clone the repo
git clone https://github.com/prp20/Nivesh-Platform.git
cd Nivesh-Platform

# Verify structure
ls
# You should see: backend/  frontend/  docs/  fundamental_data_extractor.py  BHARTIARTL.json
```

---

## Part 3 — Start the Existing Platform (verify it works first)

Before adding anything new, confirm the current MF platform runs. Claude Code will need a working baseline.

### 3.1 Start the database

```bash
cd backend
docker compose up -d

# Verify postgres is running
docker ps
# Should show a container named something like backend-database-1

# Test connection
docker exec -it backend-database-1 psql -U nivesh_admin -d nivesh_db -c "SELECT COUNT(*) FROM fund_master;"
```

### 3.2 Start the backend

```bash
cd backend

# Create venv if it doesn't exist
python3 -m venv venv
source venv/bin/activate          # Windows WSL: same command

# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn app.main:app --port 8000 --reload

# In another terminal, verify it's up:
curl http://localhost:8000/api/funds | head -c 200
```

### 3.3 Start the frontend

```bash
cd frontend
npm install
npm run dev

# Open http://localhost:5173 in your browser
# You should see the Nivesh dashboard with fund data
```

Once all three are running — DB, backend, frontend — you have a working baseline. Now Claude Code can safely add to it.

---

## Part 4 — Launch Claude Code in Your Project

```bash
# Open a new terminal tab/window
# Navigate to the project root
cd Nivesh-Platform

# Launch Claude Code
claude

# You'll see the Claude Code prompt:
# ❯
```

That's it. Claude Code now has access to your entire project directory.

---

## Part 5 — How to Work Phase by Phase

Each phase has a markdown file in your `phases/` folder. The workflow for each phase is:

1. Open Claude Code (`claude` in the project root)
2. Tell it which phase to work on and point it at the phase file
3. Let it read, plan, and implement — reviewing changes as it goes
4. Run the validation checklist before moving to the next phase

### Example: Starting Phase 1

Paste this into Claude Code:

```
Read the file phases/PHASE_1_DB_AND_STOCK_MASTER.md carefully.
Then read backend/app/models.py and backend/app/main.py to understand the existing structure.
Then implement Phase 1 completely:
1. Create the Alembic migration with all 9 new tables
2. Add the SQLAlchemy models to app/models.py (additive only)
3. Create backend/pipeline/ directory with __init__.py, audit.py, scheduler.py
4. Wire the scheduler lifespan into app/main.py (additive only)
5. Create scripts/seed/seed_stock_master.py

After each file change, pause and tell me what you changed and why.
Do not modify any existing files except app/models.py and app/main.py — and only add to them.
```

---

## Part 6 — Prompts for Each Phase

Copy-paste these directly into Claude Code. They are written to be precise, safe, and additive.

---

### Phase 0 — Audit (read-only, no code changes)

```
Read phases/PHASE_0_CODEBASE_AUDIT.md.

Then do a read-only audit of the existing codebase:
1. Read backend/app/main.py — list all existing routers and the lifespan/startup setup
2. Read backend/app/models.py — list all existing SQLAlchemy models and their table names
3. Read backend/app/database.py — note the async engine setup and session factory
4. Read backend/app/security.py — note the JWT dependency (get_current_user)
5. Read frontend/src/App.jsx — note the hash-based router and existing route map
6. Read frontend/src/store/slices/compareSlice.js — note the existing state shape
7. Read fundamental_data_extractor.py — confirm ScreenerScraper class interface
8. Read BHARTIARTL.json — note the exact output shape of the scraper

Report back with:
- Exact function/class names I must not break
- The existing DATABASE_URL format from .env or config.py
- The existing router prefix pattern (e.g. /api/funds vs /api/v1/funds)
- Any import paths I need to match for the new modules

Do not write any code yet.
```

---

### Phase 1 — Database Migration & Stock Master

```
Read phases/PHASE_1_DB_AND_STOCK_MASTER.md.
Also read backend/app/models.py and backend/app/main.py first.

Implement Phase 1. Rules:
- NEVER modify existing model classes or functions
- Only ADD new classes at the bottom of models.py
- Only ADD new lines to main.py (include_router and lifespan)
- Create all new files in the locations specified in the phase doc

Steps:
1. Create the Alembic migration file with all 9 table DDLs from Section 1.1
2. Add all 9 SQLAlchemy model classes to backend/app/models.py
3. Create backend/pipeline/__init__.py (empty)
4. Create backend/pipeline/audit.py from Section 1.3
5. Create backend/pipeline/scheduler.py from Section 1.4 (all jobs commented out)
6. Modify backend/app/main.py to wire the scheduler lifespan (additive only)
7. Create backend/scripts/seed/seed_stock_master.py from Section 1.5

After writing all files, run:
  cd backend && alembic upgrade head
  python scripts/seed/seed_stock_master.py

Then run the validation checklist from Section 1.6 and show me the output.
```

---

### Phase 2 — Price Ingestion & Basic Stock API

```
Read phases/PHASE_2_PRICE_INGESTION_API.md.
Also read backend/pipeline/scheduler.py and backend/app/routers/ to understand existing patterns.

Implement Phase 2:
1. Create backend/pipeline/price_ingestion.py (full implementation from Section 2.1)
2. Create backend/scripts/seed/backfill_prices.py (Section 2.2)
3. Uncomment price jobs in backend/pipeline/scheduler.py (Section 2.3)
4. Create backend/app/routers/stocks.py with these endpoints:
   - GET /stocks (listing + LATERAL joins for price + rating)
   - GET /stocks/search (tsvector FTS)
   - GET /stocks/{symbol} (full snapshot)
   - GET /stocks/{symbol}/price (OHLCV with interval support)
5. Register the router in backend/app/main.py
6. Create frontend/src/api/stockService.js
7. Create frontend/src/store/slices/stocksSlice.js
8. Register stocksReducer in the Redux store
9. Implement frontend/src/pages/StockListing.jsx (basic table)
10. Add new hash routes to frontend/src/App.jsx

Then run:
  python scripts/seed/backfill_prices.py 1y   # use 1y first, upgrade to 5y later

Test every endpoint:
  curl "http://localhost:8000/api/v1/stocks?limit=3"
  curl "http://localhost:8000/api/v1/stocks/search?q=reliance"
  curl "http://localhost:8000/api/v1/stocks/RELIANCE/price?interval=1d&limit=5"

Show me the JSON output of each.
```

---

### Phase 3 — Fundamental Pipeline & Normalizer

```
Read phases/PHASE_3_FUNDAMENTAL_PIPELINE.md.
Also read BHARTIARTL.json carefully — the normalizer must handle its exact format.

Implement Phase 3 in this order (the order matters for testing):

Step 1 — Normalizer first (test before anything else):
  Create backend/pipeline/normalizer.py (full implementation from Section 3.1)
  Create backend/tests/__init__.py
  Create backend/tests/test_normalizer.py (all 12 unit tests from Section 3.1)
  Run: cd backend && python -m pytest tests/test_normalizer.py -v
  ALL tests must pass before continuing.

Step 2 — Fundamental scraper:
  Create backend/pipeline/fundamental_scraper.py (Section 3.2)
  This imports from fundamental_data_extractor.py — do not modify that file.

Step 3 — Enable job in scheduler:
  Uncomment the fundamental scrape job in backend/pipeline/scheduler.py

Step 4 — API endpoints:
  Add to backend/app/routers/stocks.py:
    GET /stocks/{symbol}/fundamentals
    GET /stocks/{symbol}/shareholding

Step 5 — Frontend:
  Implement frontend/src/pages/StockDetail.jsx with tabs (Section 3.5)
  The fundamentals tab should render P&L/BS/CF as scrollable tables.

Manual test:
  python -c "
  import sys; sys.path.insert(0, '.')
  from fundamental_data_extractor import ScreenerScraper
  from pipeline.normalizer import normalize_financial_table
  s = ScreenerScraper(delay_seconds=1.5)
  raw = s.scrape_ticker('BHARTIARTL')
  pl = normalize_financial_table(raw['profit_and_loss'])
  print('Periods:', pl['periods'])
  print('Revenue:', pl['data'].get('revenue'))
  "
Show me the output.
```

---

### Phase 4 — Ratio Engine & Screener

```
Read phases/PHASE_4_RATIO_ENGINE_SCREENER.md.
Also read backend/pipeline/fundamental_scraper.py to understand how financial_statements is structured.

Implement Phase 4:
1. Create backend/pipeline/ratio_engine.py (full implementation from Section 4.1)
   Pay careful attention to the edge cases: division by zero, None inputs, negative equity.
2. Uncomment ratio compute job in backend/pipeline/scheduler.py
3. Create backend/app/routers/screener.py (Section 4.3)
   The screener must build a dynamic WHERE clause — no hardcoded filters.
4. Add GET /stocks/{symbol}/ratios to stocks.py
5. Add GET /compare endpoint to stocks.py (Section 4.4)
6. Register screener router in main.py
7. Create frontend/src/pages/Screener.jsx (Section 4.5)
8. Add #/screener route to App.jsx

Manual test — ratio compute:
  python -c "
  import asyncio
  from pipeline.ratio_engine import run_ratio_compute_all
  asyncio.run(run_ratio_compute_all())
  print('Done')
  "

API tests:
  curl "http://localhost:8000/api/v1/screener?min_roe=10&max_pe=40&sector=IT"
  curl "http://localhost:8000/api/v1/compare?symbols=RELIANCE,TCS,INFY"

Verify correctness: every result in the screener must have roe >= 10 and pe_ratio <= 40.
Run this check and show me the result:
  curl "http://localhost:8000/api/v1/screener?min_roe=10" | python3 -c "
  import json,sys
  d = json.load(sys.stdin)
  violations = [r['symbol'] for r in d['results'] if r.get('roe') is not None and r['roe'] < 10]
  print('Violations:', violations or 'None — all correct')
  "
```

---

### Phase 5 — Technical Indicators & Patterns

```
Read phases/PHASE_5_TECHNICALS_PATTERNS.md.
Also verify price_data has at least 100 rows for some stocks before starting:
  Run: psql -U nivesh_admin -d nivesh_db -c "SELECT stock_id, COUNT(*) FROM price_data GROUP BY stock_id ORDER BY COUNT(*) DESC LIMIT 5;"

Implement Phase 5:
1. Create backend/pipeline/technical_engine.py (Section 5.1)
   Uses pandas-ta — install first: pip install pandas-ta
2. Create backend/pipeline/pattern_engine.py (Section 5.2)
   Uses scipy — install first: pip install scipy
3. Uncomment both jobs in scheduler.py
4. Create backend/app/routers/technicals.py (Section 5.4)
5. Register technicals router in main.py
6. Create frontend/src/components/charts/CandlestickChart.jsx (Section 5.5)
   Install first: cd frontend && npm install lightweight-charts
7. Create frontend/src/components/charts/RSIChart.jsx
8. Update StockDetail.jsx Chart tab to use CandlestickChart
9. Update StockDetail.jsx Analysis tab to show RSI and MACD charts

Manual test — compute indicators for one stock:
  python -c "
  import asyncio
  from pipeline.technical_engine import compute_indicators_for_stock
  asyncio.run(compute_indicators_for_stock(1, '1d'))
  print('Done')
  "

Manual test — detect patterns:
  python -c "
  import asyncio
  from pipeline.pattern_engine import detect_patterns_for_stock
  patterns = asyncio.run(detect_patterns_for_stock(1))
  for p in patterns: print(p.pattern_type, p.direction, p.confidence)
  if not patterns: print('No patterns detected (normal for some stocks)')
  "

API test:
  curl "http://localhost:8000/api/v1/stocks/RELIANCE/technicals" | python3 -c "
  import json,sys; d=json.load(sys.stdin)
  print('RSI:', d['indicators'].get('rsi_14'))
  print('Trend:', d['signals'].get('trend'))
  "
```

---

### Phase 6 — Rating Engine, Compare & Dashboard

```
Read phases/PHASE_6_RATING_COMPARE_DASHBOARD.md.
Verify these tables have data before starting:
  psql -U nivesh_admin -d nivesh_db -c "SELECT COUNT(*) FROM financial_ratios; SELECT COUNT(*) FROM technical_indicators;"

Implement Phase 6:
1. Create backend/pipeline/rating_engine.py (full implementation — all 6 scoring functions)
2. Uncomment rating job in scheduler.py
3. Create backend/app/routers/ratings.py (Section 6.3)
4. Create backend/app/routers/admin_pipeline.py (Section 6.4)
5. Register both routers in main.py
6. Create frontend/src/components/stocks/RatingBadge.jsx (Section 6.5)
7. Add RatingCard to StockDetail Overview tab
8. Update Dashboard.jsx to add MarketOverview section (Section 6.6)
9. Extend compareSlice.js additively for stock compare (Section 6.7)

Manual test — compute ratings:
  python -c "
  import asyncio
  from pipeline.rating_engine import run_rating_compute
  asyncio.run(run_rating_compute())
  print('Done')
  "

Critical correctness check — run this and show me:
  psql -U nivesh_admin -d nivesh_db -c "
  SELECT rating_label, MIN(total_score), MAX(total_score), COUNT(*)
  FROM stock_ratings GROUP BY rating_label ORDER BY MIN(total_score) DESC;
  "
  -- STRONG_BUY min must be >= 75
  -- BUY min must be >= 60 (and max < 75)
  -- etc.

API test:
  curl "http://localhost:8000/api/v1/stocks/RELIANCE/rating" | python3 -c "
  import json,sys; d=json.load(sys.stdin)
  print('Label:', d['rating_label'], '| Score:', d['total_score'])
  "
```

---

### Phase 7 — Performance, Testing & Hardening

```
Read phases/PHASE_7_PERFORMANCE_TESTING.md.

Implement Phase 7 in this order:

Step 1 — Run EXPLAIN ANALYZE on all 5 critical queries from Section 7.1.
For each, confirm it uses an Index Scan. Show me the actual plan output.

Step 2 — Unit tests:
  Create backend/tests/conftest.py
  Create backend/tests/test_ratio_engine.py
  Create backend/tests/test_pattern_engine.py
  Create backend/tests/test_rating_engine.py
  Create backend/tests/test_api_stocks.py
  Run: cd backend && python -m pytest tests/ -v
  Fix any failures before continuing.

Step 3 — Caching:
  pip install cachetools
  Create backend/app/cache.py (Section 7.2)
  Add @cached("stock_detail") decorator to GET /stocks/{symbol}
  Add @cached("stock_listing") decorator to GET /stocks

Step 4 — Integrity check:
  Create backend/pipeline/integrity_check.py (Section 7.4)
  Enable the job in scheduler.py

Step 5 — Logging:
  Create backend/pipeline/logging_config.py (Section 7.5)
  Call configure_logging() in app/main.py startup

Step 6 — Health endpoint:
  Create backend/app/routers/health.py (Section 7.6)
  Register in main.py

Step 7 — Final regression:
  curl http://localhost:8000/api/funds   # must still return 200
  curl http://localhost:8000/health      # must show {"status": "healthy"}
  pytest tests/ -v                      # all tests pass

Show me the final pytest summary.
```

---

## Part 7 — Day-to-Day Claude Code Tips

### Give it the phase file every session

Claude Code doesn't remember between sessions. Start each session with:
```
Read phases/PHASE_X_whatever.md then read [relevant existing files] before doing anything.
```

### Ask it to explain before it edits

```
Before making any changes to app/main.py, show me exactly what lines you plan to add and where.
```

### Stop it from touching existing files

```
You must not modify any of these files:
- backend/app/analytics.py
- backend/app/routers/funds.py
- backend/app/routers/indices.py
- frontend/src/store/slices/fundsSlice.js
- fundamental_data_extractor.py

If you think you need to change them, stop and ask me first.
```

### Recover from a bad edit

```bash
# If Claude Code makes a wrong edit to an existing file:
git diff backend/app/main.py   # see what changed
git checkout backend/app/main.py   # restore original
```

### Ask it to run its own validation

```
After creating the file, run the validation commands from the phase doc and show me the output.
If any command fails, fix it before moving on.
```

### Split big phases into sessions

Phase 3 (Fundamental Pipeline) spans 3 weeks. Break it up:

- **Session A:** "Only implement pipeline/normalizer.py and the unit tests. Run all tests and show me they pass."
- **Session B:** "Now implement pipeline/fundamental_scraper.py. Test it manually on BHARTIARTL."
- **Session C:** "Now add the API endpoints and the frontend Fundamentals tab."

---

## Part 8 — Useful Commands to Keep Handy

```bash
# Check what's in your new tables
psql -U nivesh_admin -d nivesh_db -c "SELECT COUNT(*) FROM stocks;"
psql -U nivesh_admin -d nivesh_db -c "SELECT COUNT(*) FROM price_data;"
psql -U nivesh_admin -d nivesh_db -c "SELECT symbol, latest_close, rating_label FROM mv_stock_snapshot LIMIT 5;"

# Watch pipeline audit log in real time
psql -U nivesh_admin -d nivesh_db -c "SELECT job_name, status, records_out, started_at FROM pipeline_audit ORDER BY started_at DESC LIMIT 10;"

# Restart backend after code changes (if not using --reload)
pkill -f "uvicorn app.main"
cd backend && source venv/bin/activate && uvicorn app.main:app --port 8000 --reload

# Check APScheduler jobs are registered
curl http://localhost:8000/health | python3 -m json.tool

# Test screener with multiple filters
curl "http://localhost:8000/api/v1/screener?min_roe=12&max_pe=30&sector=IT&rating_label=BUY" | python3 -m json.tool

# Manually trigger a rating recompute (after getting a JWT token)
curl -X POST http://localhost:8000/api/v1/admin/pipeline/ratings/trigger \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Run pytest for a specific test file
cd backend && python -m pytest tests/test_normalizer.py -v

# Git status before each phase
git status
git add -p   # interactively stage only your new files
git commit -m "Phase 1: DB migration and stock master"
```

---

## Part 9 — Recommended Git Branching

```bash
# Create a branch per phase
git checkout -b phase-1-db-migration
# ... do Phase 1 work ...
git add backend/pipeline/ backend/scripts/seed/seed_stock_master.py
git commit -m "Phase 1: 9 new tables, SQLAlchemy models, APScheduler wiring"
git checkout main
git merge phase-1-db-migration

git checkout -b phase-2-price-ingestion
# ... etc
```

This way if a phase goes wrong you can always `git checkout main` and start clean.

---

## Quick Reference: DB Credentials

From `docs/INFRASTRUCTURE.md` and `docker-compose.yml`:

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `nivesh_db` |
| User | `nivesh_admin` |
| Password | `nivesh_password_123` |
| Full URL | `postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db` |

> The DATABASE_URL is already set in your backend `.env` — you don't need to change it.
