# Nivesh Platform — Audit Action Items

Generated from comprehensive backend audit on 2026-04-04.
Items are grouped by priority. Each item links to the relevant file and line.

---

## P0 — Pre-Launch Blockers (Must Fix Before Any Production Use)

- [ ] **[SEC] Add authentication to `POST /navs/{scheme_code}/bulk`**
  - File: `backend/app/routers/navs.py:9`
  - Add `current_user: str = Depends(security.get_current_user)` as a parameter
  - Risk: Anyone can overwrite historical NAV data for any fund without auth

- [ ] **[SEC] Add authentication to benchmark write endpoints**
  - File: `backend/app/routers/benchmarks.py:9,34,45`
  - `POST /`, `PUT /{code}`, `DELETE /{code}` are all unauthenticated
  - Risk: Unauthenticated users can create/modify/delete benchmark master data

- [ ] **[BUG] Fix `populate_nav_history.py` — iterates over dict keys, not fund list**
  - File: `backend/scripts/populate_nav_history.py:38`
  - `get_all_funds()` returns `{total, skip, limit, items}` but script does `for fund in funds` iterating over keys
  - Fix: change `funds = get_all_funds()` → `funds = get_all_funds().get("items", [])`

- [ ] **[BUG] Fix Sortino Ratio formula**
  - File: `backend/app/analytics.py:25-28`
  - Current uses `downside_returns.std()` which is wrong
  - Correct formula: `downside_deviation = np.sqrt(np.mean(downside_returns ** 2))`
  - Replace the return line with: `np.sqrt(252) * excess_returns.mean() / downside_deviation`

- [ ] **[BUG] Fix Information Ratio formula**
  - File: `backend/app/analytics.py:174-176`
  - Current mixes annualized return difference with annualized TE — inconsistent
  - Correct: `(active_returns.mean() / active_returns.std()) * np.sqrt(252)` where `active_returns = fund_ret - bench_ret`

- [ ] **[DATA] Guard `migrate.py` against accidental execution**
  - File: `backend/migrate.py:13-14`
  - Script deletes ALL benchmark_nav_history and benchmark_metrics rows with no confirmation
  - Add a `--force` CLI flag and a clear WARNING message before deletion

---

## P1 — Before User-Facing Release

- [ ] **[NAMING] Rename `rolling_return_3year/5year` to `cagr_3year/5year`**
  - Files: `backend/app/models.py:129-130`, `backend/app/schemas.py:42-43`, `backend/app/analytics.py:136-137`, `backend/app/sync.py:179-180`
  - Current values are point-to-point CAGRs, not rolling returns — misleading to investors

- [ ] **[BUG] Add zero/negative NAV guard before inserting NAV data**
  - File: `backend/app/sync.py:106-114`, `backend/app/crud.py:213`
  - Add `if float(v) <= 0: continue` before appending to rows in bulk_insert_fund_navs

- [ ] **[BUG] Fix `recompute_funds_metrics.py` to pass auth token**
  - File: `backend/scripts/recompute_funds_metrics.py:24`
  - Script calls `/metrics/{code}/compute` without auth — will get 401 when ENABLE_AUTH=true
  - Add a login step at script start using `ADMIN_PASSWORD` env var

- [ ] **[DATA] Verify AUM unit from Kuvera API (Millions vs Crores)**
  - File: `backend/app/sync.py:46`
  - Current divides raw AUM by 10 to "convert Millions to Crores" — unverified assumption
  - Test: fetch a known large fund (e.g., SBI Bluechip) and cross-check AUM against AMFI

- [ ] **[PERF] Add `pg_trgm` GIN indexes for ILIKE searches**
  - File: `backend/app/models.py` (FundMaster `__table_args__`)
  - `amc_name` and `scheme_category` use `ilike(f"%{value}%")` — these are seq scans without trigram index
  - Add: `Index("ix_fund_master_amc_trgm", "amc_name", postgresql_using="gin", postgresql_ops={"amc_name": "gin_trgm_ops"})`
  - Requires enabling PostgreSQL extension: `CREATE EXTENSION IF NOT EXISTS pg_trgm;`

- [ ] **[SEC] Change default SECRET_KEY and document required env vars**
  - File: `backend/app/config.py:14`
  - `SECRET_KEY = "dev-secret-key-do-not-use-in-production"` is in source code
  - Add a startup assertion: if `SECRET_KEY` contains "dev" and `ENABLE_AUTH=true`, raise on startup

- [ ] **[SEC] Set ENABLE_AUTH=true as the production default**
  - File: `backend/app/config.py:13`
  - Default is `False` — a misconfigured production deployment would expose all write endpoints

---

## P2 — Quality & Completeness

- [ ] **[API] Implement `GET /api/v1/funds/{scheme_code}/expense-ratio`**
  - File: `backend/app/routers/funds.py` (missing)
  - Documented in `docs/API_REFERENCE.md:24` but endpoint does not exist
  - For now, can return `{"expense_ratio": fund.metrics.expense_ratio}` from FundMetrics

- [ ] **[API] Add NAV trajectories to the compare endpoint response**
  - File: `backend/app/analytics.py:226-252`
  - `docs/FEATURE_MF_COMPARISON.md:42` documents that comparison returns last 500 NAV history points
  - Current implementation returns only pre-computed metrics

- [ ] **[DOCS] Fix script paths in WORKFLOW.md**
  - File: `docs/WORKFLOW.md:24-31`
  - References `scripts/seed_benchmarks.py` → actual path is `scripts/seed/seed_benchmarks.py`
  - References `scripts/migrate_data.py` and `scripts/import_new_equity.py` → these files do not exist
  - Either create the missing scripts or update the docs

- [ ] **[DB] Add FK constraint: `fund_master.benchmark_index_code` → `benchmark_master`**
  - File: `backend/app/models.py:44`
  - Currently a plain String — orphaned benchmark references go undetected
  - Change to: `ForeignKey("benchmark_master.benchmark_code", ondelete="SET NULL")`

- [ ] **[DB] Add composite index on `sync_jobs.(scheme_code, created_at DESC)`**
  - File: `backend/app/models.py:18`
  - `get_latest_sync_job` orders by `created_at DESC` per scheme_code on every metrics request
  - Add: `Index('ix_sync_jobs_scheme_created', 'scheme_code', 'created_at')`

- [ ] **[DB] Introduce Alembic for schema migrations**
  - Current `create_all` in lifespan cannot apply column/index changes to existing DBs
  - Run: `pip install alembic`, `alembic init alembic`, configure `env.py` with the async engine

- [ ] **[API] Add upper-bound to `GET /navs/{scheme_code}?limit=`**
  - File: `backend/app/routers/navs.py:14`
  - No max cap — `?limit=9999999` can dump millions of rows
  - Change to: `limit: int = Query(100, ge=1, le=5000)`

- [ ] **[API] Standardize pagination envelope across all list endpoints**
  - Funds: `{total, skip, limit, items}` vs Benchmarks: `{items, total}`
  - Create a shared `PaginatedResponse[T]` generic Pydantic model and apply to both

- [ ] **[API] Convert `POST /sync/{scheme_code}` to a background task**
  - File: `backend/app/routers/sync.py:23-31`
  - Currently runs sync synchronously in the request — can block for 30-120 seconds
  - Follow the pattern in `routers/metrics.py` and use `BackgroundTasks`

- [ ] **[ETL] Extend `TICKER_MAP` for all seeded benchmarks**
  - File: `backend/scripts/etl_populate_data.py:137-142`
  - Only 4 tickers mapped; NIFTY_100, NIFTY_500, NIFTY_LARGEMIDCAP_250, NIFTY_SMALLCAP_250 need entries or verified CSV fallback paths

- [ ] **[ETL] Add overall timeout to `sync_fund_data` mftool call**
  - File: `backend/app/sync.py:85-99`
  - Wrap with `asyncio.wait_for(asyncio.to_thread(...), timeout=60)` to prevent indefinite hangs

---

## P3 — Nice to Have / Future Improvements

- [ ] **[FEATURE] Implement XIRR for SIP return calculation**
  - Not currently implemented; standard metric on all Indian MF platforms
  - Use `scipy.optimize.brentq` or `numpy_financial.irr` for computation

- [ ] **[API] Implement `POST /auth/refresh` endpoint**
  - Documented in `docs/BACKEND.md:72` but not implemented
  - Issue a new access token given a still-valid token

- [ ] **[DB] Replace `FAKE_USERS_DB` with a proper `users` table**
  - File: `backend/app/routers/auth.py:13`
  - Add `users(id, username, hashed_password, role, is_active, created_at)` table
  - Move credential lookup to a CRUD query

- [ ] **[DB] Track AUM history**
  - `aum_in_crores` in `fund_metrics` is overwritten on every sync
  - Add `fund_aum_history(scheme_code, as_of_date, aum_in_crores)` table

- [ ] **[API] Add screener/leaderboard endpoint**
  - `GET /api/v1/metrics/?sort_by=sharpe_ratio&order=desc&limit=20`
  - Useful for fund discovery; currently no way to rank funds by a metric

- [ ] **[METRICS] Fix Sharpe Ratio denominator (minor)**
  - File: `backend/app/analytics.py:18`
  - Uses `returns.std()` — technically should be `excess_returns.std()` per Sharpe's original formula
  - Difference is negligible for most funds but worth correcting for accuracy

- [ ] **[METRICS] Add true rolling return computation**
  - Current `rolling_return_3year` is CAGR for the latest 3Y window only
  - True rolling return = average (or distribution) of all 3Y CAGRs across history

- [ ] **[API] Add `GET /api/v1/health` endpoint**
  - For load balancer / uptime monitoring
  - Should check DB connectivity and return `{status: "ok", db: "connected"}`

- [ ] **[DOCS] Remove or implement token refresh claim in BACKEND.md**
  - File: `docs/BACKEND.md:72`
  - Either implement the endpoint or remove the claim

- [ ] **[API] Add authorization to the compare endpoint**
  - File: `backend/app/routers/funds.py:49`
  - `docs/FEATURE_MF_COMPARISON.md:25` marks it as requiring JWT but it has no auth check

---

## Notes for the Agent

- All backend code lives in `backend/app/`
- Analytics/financial formulas are in `backend/app/analytics.py`
- Database models in `backend/app/models.py`
- API routes in `backend/app/routers/`
- ETL scripts in `backend/scripts/`
- Seed scripts in `backend/scripts/seed/`
- Docs in `docs/`
- The startup script is at `start.sh` (project root)
- Risk-free rate used throughout: **6.5% (0.065)** — hardcoded in `analytics.py:14,20`
- AMFI scheme codes are numeric strings (e.g., `"119533"`)
