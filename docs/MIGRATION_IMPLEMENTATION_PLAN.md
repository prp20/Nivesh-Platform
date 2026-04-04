# Implementation Plan: TimescaleDB → Pure PostgreSQL Migration

> **Author:** Architecture Team  
> **Date:** 2026-04-02  
> **Companion Docs:**  
> - [High-Level Design](./MIGRATION_HLD_TIMESCALE_TO_PGSQL.md)  
> - [Low-Level Design](./MIGRATION_LLD_TIMESCALE_TO_PGSQL.md)  
> **Estimated Effort:** 1–2 hours  
> **Risk Level:** Low  

---

## Pre-Requisites

Before beginning the migration, ensure the following:

- [ ] Read and understand both the HLD and LLD documents
- [ ] Ensure no active ETL jobs are running (`GET /api/v1/metrics/{any_code}/status` should not show `RUNNING`)
- [ ] If preserving data, take a backup (see Step 2 below)
- [ ] Ensure Docker and Docker Compose are available on the host machine

---

## Step 1: Back Up Existing Data (Optional — Skip for Fresh Dev Setup)

> **When to do this:** Only if your current TimescaleDB instance contains data you want to preserve.  
> **Skip if:** You plan to re-seed from scratch using ETL scripts.

```bash
# 1.1 — Export all data from the running TimescaleDB container
cd backend
docker exec nivesh_timescaledb pg_dump -U nivesh_admin -d nivesh_db \
  --no-owner --no-privileges --data-only \
  -t fund_master \
  -t benchmark_master \
  -t fund_nav_history \
  -t benchmark_nav_history \
  -t fund_metrics \
  -t benchmark_metrics \
  -t sync_jobs \
  > nivesh_data_backup.sql

# 1.2 — Verify the backup file is non-empty
wc -l nivesh_data_backup.sql
# Expected: Several thousand lines if data exists
```

**Checkpoint:** `nivesh_data_backup.sql` exists and contains INSERT statements.

---

## Step 2: Stop and Remove the TimescaleDB Container

```bash
# 2.1 — Stop the running services
cd backend
docker-compose down

# 2.2 — Remove the old data volume (DESTRUCTIVE — skip if preserving data without backup)
docker volume rm backend_nivesh_pg_data
# Or use: docker-compose down -v
```

**Checkpoint:** `docker ps` shows no `nivesh_timescaledb` container. Volume is removed.

---

## Step 3: Update Infrastructure — `docker-compose.yml`

Modify `backend/docker-compose.yml` with the following changes:

| Line | Change |
|------|--------|
| L4 | Service name: `timescaledb:` → `postgres:` |
| L5 | Image: `timescale/timescaledb:latest-pg16` → `postgres:16-alpine` |
| L6 | Container name: `nivesh_timescaledb` → `nivesh_postgres` |
| L12 | Remove: `TIMESCALEDB_TELEMETRY: 'off'` |

**Target state of the file:**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: nivesh_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: nivesh_db
      POSTGRES_USER: nivesh_admin
      POSTGRES_PASSWORD: nivesh_password_123
    ports:
      - "5432:5432"
    volumes:
      - nivesh_pg_data:/var/lib/postgresql/data
    healthcheck:
      test: [ "CMD-SHELL", "pg_isready -U nivesh_admin -d nivesh_db" ]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - nivesh_network

volumes:
  nivesh_pg_data:

networks:
  nivesh_network:
    driver: bridge
```

**Checkpoint:** File saved. `docker-compose config` runs without errors.

---

## Step 4: Start the New PostgreSQL Container

```bash
cd backend
docker-compose up -d

# Verify the container is healthy
docker ps
# Expected: nivesh_postgres running, status "healthy"

# Verify connectivity
docker exec nivesh_postgres pg_isready -U nivesh_admin -d nivesh_db
# Expected: "accepting connections"
```

**Checkpoint:** PostgreSQL container is running and accepting connections.

---

## Step 5: Update Application Code — `app/main.py`

Modify `backend/app/main.py`:

1. **Remove** the `from sqlalchemy import text` import (L4)
2. **Remove** the entire `try/except` block (L14–L21) containing `create_hypertable` calls
3. **Keep** `Base.metadata.create_all` — this provisions standard tables

**Target state of the `lifespan` function:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown logic (none needed for now)
```

**Checkpoint:** File saved. No `timescale`, `hypertable`, or `text` references remain in `main.py`.

---

## Step 6: Update ORM Models — `app/models.py`

Modify `backend/app/models.py`:

### 6.1 — Update docstrings
- **L62:** `"""Historical NAV data for all mutual fund schemes (TimescaleDB Hypertable)"""` → `"""Historical NAV data for all mutual fund schemes"""`
- **L75:** `"""Historical index values for benchmark indices (TimescaleDB Hypertable)"""` → `"""Historical index values for benchmark indices"""`

### 6.2 — Add explicit `nav_date` indexes

**FundNavHistory `__table_args__` (L64–66):**
```python
__table_args__ = (
    UniqueConstraint('scheme_code', 'nav_date', name='uq_fund_nav_scheme_date'),
    Index('ix_fund_nav_history_nav_date', 'nav_date'),
)
```

**BenchmarkNavHistory `__table_args__` (L77–79):**
```python
__table_args__ = (
    UniqueConstraint('benchmark_code', 'nav_date', name='uq_benchmark_nav_date'),
    Index('ix_benchmark_nav_history_nav_date', 'nav_date'),
)
```

> **Note:** `Index` is already imported on L1. No additional imports needed.

**Checkpoint:** File saved. `grep -n "TimescaleDB" app/models.py` returns nothing.

---

## Step 7: Restore Data (Only If You Did Step 1)

```bash
# 7.1 — First, start the app briefly to create the schema
cd backend
source venv/bin/activate
python -c "
import asyncio
from app.database import engine, Base
from app.models import *

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Schema created successfully.')

asyncio.run(init())
"

# 7.2 — Restore the data
docker exec -i nivesh_postgres psql -U nivesh_admin -d nivesh_db < nivesh_data_backup.sql

# 7.3 — Verify row counts
docker exec nivesh_postgres psql -U nivesh_admin -d nivesh_db -c "
  SELECT 'fund_master' AS tbl, COUNT(*) FROM fund_master
  UNION ALL SELECT 'fund_nav_history', COUNT(*) FROM fund_nav_history
  UNION ALL SELECT 'benchmark_master', COUNT(*) FROM benchmark_master
  UNION ALL SELECT 'benchmark_nav_history', COUNT(*) FROM benchmark_nav_history
  UNION ALL SELECT 'fund_metrics', COUNT(*) FROM fund_metrics;
"
```

**Checkpoint:** Row counts match expectations from your original database.

---

## Step 8: Update Documentation

Update the following 6 files. Detailed before/after changes are in the [LLD document](./MIGRATION_LLD_TIMESCALE_TO_PGSQL.md#3-documentation-changes).

| # | File | Summary of Changes |
|---|------|--------------------|
| 1 | `docs/DATABASE.md` | Replace "TimescaleDB" → "PostgreSQL", "Hypertables" → "standard tables with indexes" |
| 2 | `docs/OVERVIEW.md` | Update architecture diagram, tech stack table, security section |
| 3 | `docs/INFRASTRUCTURE.md` | Update service name, image reference, remove time-series optimization line |
| 4 | `docs/SETUP.md` | "TimescaleDB container" → "PostgreSQL database container" |
| 5 | `backend/README.md` | Update tagline, stack section, DB schema link description |
| 6 | `README.md` (root) | Update DB schema link text, tech stack section |

**Checkpoint:** `grep -r -i "timescale\|hypertable" docs/ backend/README.md README.md` returns zero results.

---

## Step 9: Verify the Application

### 9.1 — Start the Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --port 8000
```

**Expected console output:**
- No `Hypertable creation skipped or failed` message (the old error/skip log)
- Standard Uvicorn startup message

### 9.2 — API Smoke Tests

```bash
# Health check
curl -s http://localhost:8000/ | python -m json.tool
# Expected: {"message": "Nivesh API API", "status": "running", ...}

# Fund listing (if data was restored or seeded)
curl -s "http://localhost:8000/api/v1/funds/?limit=3" | python -m json.tool
# Expected: JSON with "total" and "items" array

# Benchmark listing
curl -s "http://localhost:8000/api/v1/benchmarks/?limit=3" | python -m json.tool
# Expected: JSON with "items" and "total"
```

### 9.3 — Verify Index Creation
```bash
docker exec nivesh_postgres psql -U nivesh_admin -d nivesh_db -c "
  SELECT indexname, tablename
  FROM pg_indexes
  WHERE tablename IN ('fund_nav_history', 'benchmark_nav_history')
  ORDER BY tablename, indexname;
"
```

**Expected output should include:**
- `ix_fund_nav_history_nav_date` on `fund_nav_history`
- `ix_benchmark_nav_history_nav_date` on `benchmark_nav_history`
- Primary key indexes on both tables

### 9.4 — Full ETL Smoke Test (Optional)
```bash
# Trigger a single fund sync to verify the complete pipeline
curl -s -X POST "http://localhost:8000/api/v1/metrics/119598/compute" | python -m json.tool
# Expected: {"message": "Background sync started", "job_id": "...", ...}

# Wait 30 seconds, then check status
curl -s "http://localhost:8000/api/v1/metrics/119598/status" | python -m json.tool
# Expected: {"status": "COMPLETED", ...}
```

**Checkpoint:** All API endpoints return expected responses. No database errors in server logs.

---

## Step 10: Final Codebase Audit

Run the following command to confirm zero TimescaleDB references remain in code and docs:

```bash
cd /home/prasad/dev_home/mutual_fund_exp/stock_nivesh_platform
grep -r -i -n "timescale\|hypertable\|create_hypertable\|time_bucket" \
  --include="*.py" --include="*.yml" --include="*.md" --include="*.txt" \
  --exclude-dir=venv --exclude-dir=node_modules --exclude-dir=.git \
  .
```

**Expected:** Zero results (or only this migration plan document itself, which is acceptable).

---

## Step 11: Commit and Push

```bash
git add -A
git commit -m "refactor: migrate from TimescaleDB to standard PostgreSQL

- Remove create_hypertable() calls from app startup (main.py)
- Replace TimescaleDB Docker image with postgres:16-alpine
- Add explicit B-Tree indexes on nav_date columns
- Update all documentation to reflect PostgreSQL-only stack
- Add migration design documents (HLD, LLD, Implementation Plan)"

git push origin feature/cleanup-and-enhancements
```

---

## Rollback Plan

If issues are discovered post-migration:

1. **Revert code:** `git revert HEAD`
2. **Restore TimescaleDB container:** The old `docker-compose.yml` in git history will spin up TimescaleDB
3. **Restore data:** If the old volume was preserved, data will be intact. Otherwise, restore from `nivesh_data_backup.sql` into the TimescaleDB container
4. **`create_hypertable` is idempotent:** Re-adding the calls won't cause issues with existing hypertables

---

## Post-Migration Verification Checklist

- [ ] PostgreSQL container starts and is healthy
- [ ] Application starts without hypertable errors
- [ ] `GET /` returns health check JSON
- [ ] `GET /api/v1/funds/` returns fund list
- [ ] `GET /api/v1/benchmarks/` returns benchmark list
- [ ] `POST /api/v1/metrics/{code}/compute` triggers background sync
- [ ] `GET /api/v1/metrics/{code}/status` returns `COMPLETED` after sync
- [ ] `GET /api/v1/metrics/{code}` returns computed metrics
- [ ] B-Tree indexes exist on `nav_date` columns
- [ ] Zero `timescale`/`hypertable` references in codebase (excluding migration docs)
- [ ] All documentation updated
- [ ] Changes committed and pushed
