# Low-Level Design: TimescaleDB → Pure PostgreSQL Migration

> **Author:** Architecture Team  
> **Date:** 2026-04-02  
> **Companion Doc:** [HLD](./MIGRATION_HLD_TIMESCALE_TO_PGSQL.md)  

This document records **every single change** required across the codebase, organized by file, with exact line numbers, before/after content, and rationale.

---

## Table of Contents

1. [Application Code Changes](#1-application-code-changes)
2. [Infrastructure Changes](#2-infrastructure-changes)
3. [Documentation Changes](#3-documentation-changes)
4. [Database Migration (Data)](#4-database-migration-data)
5. [Files Confirmed Unchanged](#5-files-confirmed-unchanged)

---

## 1. Application Code Changes

### 1.1 `backend/app/main.py`

**Current Code (Lines 9-23):**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            # TimescaleDB hypertable setup
            await conn.execute(text("SELECT create_hypertable('fund_nav_history', 'nav_date', if_not_exists => TRUE);"))
            await conn.execute(text("SELECT create_hypertable('benchmark_nav_history', 'nav_date', if_not_exists => TRUE);"))
            await conn.commit()
        except Exception as e:
            # Skip if already a hypertable or outside TimescaleDB context
            print(f"Hypertable creation skipped or failed: {e}")
    yield
    # Shutdown logic (none needed for now)
```

**Required Changes:**

| # | Line(s) | Action | Detail |
|---|---------|--------|--------|
| 1 | L4 | REMOVE | `from sqlalchemy import text` — no longer needed (only used for hypertable SQL). |
| 2 | L14-21 | REMOVE | Entire `try/except` block containing `create_hypertable` calls and associated comment/print. |
| 3 | L18 | REMOVE | `await conn.commit()` inside the try block — the `engine.begin()` context manager auto-commits. |

**Target Code:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown logic (none needed for now)
```

> **Note:** Verify that `text` is not imported for use elsewhere in `main.py`. Current audit confirms it is only used for hypertable setup. However, `text` IS used in `crud.py` and `models.py` via their own imports, so removing it from `main.py` is safe.

---

### 1.2 `backend/app/models.py`

**Change 1 — Docstring Update (L62)**

| Item | Value |
|------|-------|
| **File** | `backend/app/models.py` |
| **Line** | 62 |
| **Before** | `"""Historical NAV data for all mutual fund schemes (TimescaleDB Hypertable)"""` |
| **After** | `"""Historical NAV data for all mutual fund schemes"""` |
| **Rationale** | Remove stale reference to TimescaleDB. |

**Change 2 — Docstring Update (L75)**

| Item | Value |
|------|-------|
| **File** | `backend/app/models.py` |
| **Line** | 75 |
| **Before** | `"""Historical index values for benchmark indices (TimescaleDB Hypertable)"""` |
| **After** | `"""Historical index values for benchmark indices"""` |
| **Rationale** | Remove stale reference to TimescaleDB. |

**Change 3 — Add Explicit Index on `nav_date` for `FundNavHistory` (L64-66)**

Add a B-Tree index on `nav_date` within the `__table_args__` tuple to optimize date-range queries that TimescaleDB's chunk indexing previously handled automatically.

| Item | Value |
|------|-------|
| **File** | `backend/app/models.py` |
| **Lines** | 64-66 |
| **Before** | `__table_args__ = (UniqueConstraint('scheme_code', 'nav_date', name='uq_fund_nav_scheme_date'),)` |
| **After** | `__table_args__ = (UniqueConstraint('scheme_code', 'nav_date', name='uq_fund_nav_scheme_date'), Index('ix_fund_nav_history_nav_date', 'nav_date'),)` |
| **Rationale** | Compensates for the loss of TimescaleDB's per-chunk automatic time indexing. Queries like `ORDER BY nav_date DESC LIMIT N` benefit from this standalone index. |

**Change 4 — Add Explicit Index on `nav_date` for `BenchmarkNavHistory` (L77-79)**

| Item | Value |
|------|-------|
| **File** | `backend/app/models.py` |
| **Lines** | 77-79 |
| **Before** | `__table_args__ = (UniqueConstraint('benchmark_code', 'nav_date', name='uq_benchmark_nav_date'),)` |
| **After** | `__table_args__ = (UniqueConstraint('benchmark_code', 'nav_date', name='uq_benchmark_nav_date'), Index('ix_benchmark_nav_history_nav_date', 'nav_date'),)` |
| **Rationale** | Same as Change 3 above, applied to benchmark history table. |

> **Note:** `Index` is already imported on L1 of `models.py`: `from sqlalchemy import ..., Index`. No additional import needed.

---

## 2. Infrastructure Changes

### 2.1 `backend/docker-compose.yml`

**Full file rewrite required. Current → Target:**

| # | Line(s) | Element | Before | After | Rationale |
|---|---------|---------|--------|-------|-----------|
| 1 | L4 | Service name | `timescaledb:` | `postgres:` | Reflects the actual service. |
| 2 | L5 | Docker image | `image: timescale/timescaledb:latest-pg16` | `image: postgres:16-alpine` | Standard PostgreSQL image. Alpine variant for smaller footprint. |
| 3 | L6 | Container name | `container_name: nivesh_timescaledb` | `container_name: nivesh_postgres` | Updated naming convention. |
| 4 | L12 | Env variable | `TIMESCALEDB_TELEMETRY: 'off'` | *(remove entirely)* | TimescaleDB-specific variable no longer applicable. |

**Target `docker-compose.yml`:**
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

---

### 2.2 `backend/migrate.py`

**No changes required.**  
This script uses `Base.metadata.create_all` and direct table deletes — both are pure SQLAlchemy and database-agnostic.

---

## 3. Documentation Changes

Every file below contains one or more references to "TimescaleDB", "Hypertable", or "timescale" that must be updated.

### 3.1 `docs/DATABASE.md`

| # | Line | Before | After |
|---|------|--------|-------|
| 1 | L1 | `# Database Schema & Time-Series Design` | `# Database Schema & Design` |
| 2 | L3 | `Nivesh Elite uses **PostgreSQL** with the **TimescaleDB** extension to effectively manage master data and millions of NAV history points.` | `Nivesh Elite uses **PostgreSQL** to manage master data and historical NAV data points.` |
| 3 | L24 | `## ⚡ Time-Series (TimescaleDB)` | `## ⚡ Time-Series Tables` |
| 4 | L25 | `Historical values are stored in **Hypertables**, partitioned by \`nav_date\`.` | `Historical values are stored in standard PostgreSQL tables with composite primary keys and B-Tree indexes on \`nav_date\`.` |
| 5 | L20 | Remove `- \`fund_expense_ratio\`: ...` line (if stale, per current models — this table no longer exists in models.py). | *(Verify if still relevant; if not, remove)* |

### 3.2 `docs/OVERVIEW.md`

| # | Line | Before | After |
|---|------|--------|-------|
| 1 | L14 | `DB[(TimescaleDB)]` | `DB[(PostgreSQL)]` |
| 2 | L29 | `- **Database**: PostgreSQL with the TimescaleDB extension, enabling efficient handling of millions of historical data points.` | `- **Database**: PostgreSQL, enabling efficient handling of historical data points with optimized indexing.` |
| 3 | L39 | `\| **Database** \| PostgreSQL + TimescaleDB \|` | `\| **Database** \| PostgreSQL 16 \|` |
| 4 | L48 | `- **Data Integrity**: Enforced via unique constraints and TimescaleDB segmentations.` | `- **Data Integrity**: Enforced via unique constraints and B-Tree indexing.` |

### 3.3 `docs/INFRASTRUCTURE.md`

| # | Line | Before | After |
|---|------|--------|-------|
| 1 | L7 | `### 🧬 database (TimescaleDB)` | `### 🧬 database (PostgreSQL)` |
| 2 | L8 | `The core data engine, based on the official TimescaleDB image (\`timescale/timescaledb:latest-pg14\`).` | `The core data engine, based on the official PostgreSQL image (\`postgres:16-alpine\`).` |
| 3 | L11 | `- **Time-Series Optimization**: Pre-configured to handle massive amounts of financial data points.` | `- **Indexing**: B-Tree indexes on time-series columns for efficient range queries.` |

### 3.4 `docs/SETUP.md`

| # | Line | Before | After |
|---|------|--------|-------|
| 1 | L10 | `Start the dedicated TimescaleDB container:` | `Start the PostgreSQL database container:` |

### 3.5 `backend/README.md`

| # | Line | Before | After |
|---|------|--------|-------|
| 1 | L3 | `High-performance financial analytics backend powered by **FastAPI** and **TimescaleDB**.` | `High-performance financial analytics backend powered by **FastAPI** and **PostgreSQL**.` |
| 2 | L9 | `- 🗄️ [**Database Schema**](./docs/DATABASE.md): Table structures and time-series hypertables.` | `- 🗄️ [**Database Schema**](./docs/DATABASE.md): Table structures and time-series data.` |
| 3 | L25 | `- **Database**: TimescaleDB / PostgreSQL` | `- **Database**: PostgreSQL 16` |

### 3.6 `README.md` (Root)

| # | Line | Before | After |
|---|------|--------|-------|
| 1 | L20 | `- 🗄️ [**Database Schema**](./docs/DATABASE.md): Models and TimescaleDB engine.` | `- 🗄️ [**Database Schema**](./docs/DATABASE.md): Models and database schema.` |
| 2 | L55 | `**Database**: TimescaleDB (PostgreSQL)` | `**Database**: PostgreSQL 16` |

### 3.7 `docs/BACKEND.md`

**No direct TimescaleDB references found.** However, verify L3 contextual reference:
> "The Nivesh backend is an asynchronous powerhouse designed to handle complex financial analytics and time-series data at scale."

This line is database-agnostic — no change required.

### 3.8 `docs/WORKFLOW.md`

**No TimescaleDB references found.** No changes needed.

### 3.9 `docs/API_REFERENCE.md`

**No TimescaleDB references found.** No changes needed.

### 3.10 `docs/FEATURE_MF_COMPARISON.md`

**No TimescaleDB references found.** The sequence diagram on L54 already uses `Database (Postgres)` — no change needed.

---

## 4. Database Migration (Data)

### 4.1 If Starting Fresh (Recommended for Dev/Test)

1. Stop the old container: `docker-compose down`
2. Remove the old volume: `docker volume rm backend_nivesh_pg_data` (or `docker-compose down -v`)
3. Start with the new `docker-compose.yml`: `docker-compose up -d`
4. Run the application — `Base.metadata.create_all` will provision all tables as standard PostgreSQL tables
5. Re-seed data using existing ETL scripts

### 4.2 If Preserving Existing Data (Production)

1. **Export** from TimescaleDB container:
   ```bash
   docker exec nivesh_timescaledb pg_dump -U nivesh_admin -d nivesh_db --no-owner --no-privileges > nivesh_backup.sql
   ```
2. Remove hypertable-specific SQL from the dump:
   ```bash
   # Remove lines containing create_hypertable, timescaledb extension references
   sed -i '/create_hypertable/d' nivesh_backup.sql
   sed -i '/timescaledb/d' nivesh_backup.sql
   ```
3. Stop old container, start new PostgreSQL container
4. **Import** into new container:
   ```bash
   docker exec -i nivesh_postgres psql -U nivesh_admin -d nivesh_db < nivesh_backup.sql
   ```

> **Warning:** TimescaleDB hypertables internally restructure table storage. A raw `pg_dump` from a TimescaleDB instance produces dump output that MAY include TimescaleDB-specific restore commands. The `sed` cleanup in step 2 is essential. Alternatively, use `pg_dump --table=fund_nav_history --data-only` to export just the data rows, then let SQLAlchemy's `create_all` provision the schema.

---

## 5. Files Confirmed Unchanged

The following files have been audited and require **zero modifications**:

| File | Reason |
| :--- | :--- |
| `backend/app/crud.py` | Pure SQLAlchemy. Uses `pg_insert`, `select`, `update`, `delete`. No TSDB functions. |
| `backend/app/analytics.py` | Pure Pandas/NumPy. All time-series math is application-layer. |
| `backend/app/sync.py` | Orchestrates `crud` calls. No direct DB operations. |
| `backend/app/schemas.py` | Pydantic models. Fully database-agnostic. |
| `backend/app/database.py` | Standard `asyncpg` engine factory. No TSDB config. |
| `backend/app/config.py` | `postgresql+asyncpg://` connection string. Already compatible. |
| `backend/app/security.py` | JWT/bcrypt auth. No DB awareness. |
| `backend/app/routers/funds.py` | Route handlers calling `crud`. |
| `backend/app/routers/benchmarks.py` | Route handlers calling `crud`. |
| `backend/app/routers/navs.py` | Route handlers calling `crud`. |
| `backend/app/routers/benchmark_navs.py` | Route handlers calling `crud`. |
| `backend/app/routers/metrics.py` | Route handlers calling `crud` and `sync`. |
| `backend/app/routers/sync.py` | Route handlers calling `sync`. |
| `backend/app/routers/auth.py` | Auth endpoints. No DB dependency. |
| `backend/requirements.txt` | No TimescaleDB Python packages. |
| `backend/migrate.py` | Uses `Base.metadata.create_all`. Database-agnostic. |
| `backend/scripts/etl_populate_data.py` | Calls `crud` functions. No TSDB awareness. |
| `backend/scripts/populate_nav_history.py` | Uses HTTP API. No direct DB operations. |
| `backend/scripts/recompute_funds_metrics.py` | Uses HTTP API. No direct DB operations. |
| `backend/scripts/seed/*` | Seeding scripts. No TSDB dependency. |
| `docs/BACKEND.md` | No TimescaleDB references (verified). |
| `docs/WORKFLOW.md` | No TimescaleDB references (verified). |
| `docs/API_REFERENCE.md` | No TimescaleDB references (verified). |
| `docs/FEATURE_MF_COMPARISON.md` | No TimescaleDB references (verified). |
| `docs/FRONTEND.md` | Frontend documentation. No DB references. |

---

## 6. Change Summary Matrix

| Change Category | Files Affected | Lines Changed (Est.) |
| :--- | :--- | :--- |
| Application Code | 2 (`main.py`, `models.py`) | ~15 lines |
| Infrastructure | 1 (`docker-compose.yml`) | ~4 lines |
| Documentation | 6 files | ~15 lines |
| **Total** | **9 files** | **~34 lines** |
