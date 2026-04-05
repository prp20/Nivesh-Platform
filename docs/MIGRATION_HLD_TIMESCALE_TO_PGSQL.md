# High-Level Design: TimescaleDB → Pure PostgreSQL Migration

> **Author:** Architecture Team  
> **Date:** 2026-04-02  
> **Status:** Draft — Pending Approval  

---

## 1. Objective

Migrate the Nivesh Elite backend from a **PostgreSQL + TimescaleDB extension** architecture to a **standard PostgreSQL-only** architecture, eliminating the TimescaleDB dependency entirely while preserving all existing functionality, API contracts, and data semantics.

---

## 2. Motivation & Business Case

| Driver | Detail |
| :--- | :--- |
| **Developer Onboarding** | New contributors must install TimescaleDB (custom Docker image or extension) — a non-trivial setup on many environments. |
| **Hosting Portability** | Standard PostgreSQL is universally offered by AWS RDS, GCP Cloud SQL, Supabase, Neon, Railway, etc. TimescaleDB-managed options are limited and more expensive. |
| **Minimal Feature Utilization** | The codebase uses only `create_hypertable()` — zero usage of `time_bucket()`, continuous aggregates, compression policies, data retention, or any advanced TimescaleDB API. |
| **Operational Simplicity** | Fewer moving parts in the infrastructure stack reduces maintenance burden and failure surfaces. |

---

## 3. Current Architecture (As-Is)

```
┌─────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
│                                                     │
│  main.py ──► create_hypertable() on startup         │
│  models.py ──► FundNavHistory (Hypertable)           │
│              BenchmarkNavHistory (Hypertable)        │
│  crud.py ──► Standard SQLAlchemy (no TSDB functions) │
│  analytics.py ──► Pandas-based (app-layer compute)  │
└────────────────────┬────────────────────────────────┘
                     │
              ┌──────▼──────┐
              │ TimescaleDB  │  (timescale/timescaledb:latest-pg16)
              │  PostgreSQL  │
              │  + Extension │
              └─────────────┘
```

### TimescaleDB Touchpoints (Complete Inventory)

| Layer | File | Usage |
| :--- | :--- | :--- |
| **Application Startup** | `app/main.py` (L14-21) | `SELECT create_hypertable(...)` for `fund_nav_history` and `benchmark_nav_history` |
| **ORM Models** | `app/models.py` (L62, L75) | Docstring comments referencing "TimescaleDB Hypertable" |
| **Infrastructure** | `docker-compose.yml` | Image `timescale/timescaledb:latest-pg16`, env `TIMESCALEDB_TELEMETRY: 'off'`, container name `nivesh_timescaledb` |
| **Documentation** | 7 files across `docs/` and `README.md` | References to TimescaleDB in descriptions, architecture diagrams, tech stack tables |

### Non-Touchpoints (Confirmed Safe)

| Layer | Verdict |
| :--- | :--- |
| `app/crud.py` | Pure SQLAlchemy — `pg_insert`, `select`, `update`, `delete`. No TSDB functions. |
| `app/analytics.py` | Pure Pandas/NumPy — all time-series calculations happen in Python memory. |
| `app/sync.py` | Calls `crud` functions only. No direct DB operations. |
| `app/schemas.py` | Pydantic models. Database-agnostic. |
| `app/routers/*` | Route handlers. Call `crud` and `analytics`. No TSDB awareness. |
| `app/database.py` | Standard `asyncpg` engine. Connection string is database-agnostic. |
| `app/config.py` | Standard `postgresql+asyncpg://` URI. No TSDB-specific config. |
| `scripts/*` | ETL scripts call `crud` or HTTP API. Zero TSDB dependency. |
| `requirements.txt` | No TimescaleDB Python libraries. |

---

## 4. Target Architecture (To-Be)

```
┌─────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
│                                                     │
│  main.py ──► Base.metadata.create_all only           │
│  models.py ──► FundNavHistory (Standard Table + Index)│
│              BenchmarkNavHistory (Standard Table + Index) │
│  crud.py ──► Unchanged                               │
│  analytics.py ──► Unchanged                           │
└────────────────────┬────────────────────────────────┘
                     │
              ┌──────▼──────┐
              │  PostgreSQL  │  (postgres:16-alpine)
              │  Standard    │
              └─────────────┘
```

---

## 5. Impact Analysis

### 5.1 Code Changes (Application)
- **main.py**: Remove the `create_hypertable()` calls and their try/except wrapper. The `Base.metadata.create_all` on L13 already provisions standard tables correctly.
- **models.py**: Update docstrings from "TimescaleDB Hypertable" to "Standard PostgreSQL table". Add explicit B-Tree indexes on `nav_date` for both history tables to compensate for loss of automatic hypertable chunk indexing.

### 5.2 Infrastructure Changes
- **docker-compose.yml**: Replace TimescaleDB image with standard PostgreSQL image. Remove TimescaleDB-specific environment variables. Update container name.

### 5.3 Documentation Changes
- **7 documentation files** across `docs/` and root `README.md` contain TimescaleDB references that must be updated to reflect "PostgreSQL".

### 5.4 Zero-Impact Areas (No Changes Needed)
- All CRUD operations (`crud.py`)
- Analytics engine (`analytics.py`)
- Sync pipeline (`sync.py`)
- All Pydantic schemas (`schemas.py`)
- All API routers (`routers/*`)
- All ETL scripts (`scripts/*`)
- Database connection setup (`database.py`, `config.py`)
- Python dependencies (`requirements.txt`)
- Security module (`security.py`)

---

## 6. Risk Assessment

| Risk | Severity | Mitigation |
| :--- | :--- | :--- |
| **Data Migration** | 🟡 Medium | Existing data must be exported and re-imported if the Docker volume is recreated. A `pg_dump`/`pg_restore` can handle this since the underlying table schema is identical. |
| **Query Performance on Large Datasets** | 🟢 Low | Current dataset is well within standard PostgreSQL capabilities. Adding a composite B-Tree index on `(scheme_code, nav_date)` provides equivalent lookup performance. |
| **Index Scan Performance** | 🟢 Low | The composite primary key `(scheme_code, nav_date)` already creates a B-Tree index. Adding a standalone index on `nav_date` covers date-range scans. |
| **Future Scale Concerns** | 🟡 Medium | If NAV history grows beyond ~50M rows, consider PostgreSQL native partitioning (`PARTITION BY RANGE`) as a future enhancement. |

---

## 7. Performance Considerations

### What TimescaleDB Was Providing (Automatically)
1. Transparent time-based partitioning (chunks) on `nav_date`
2. Automatic chunk-level indexing
3. Compression for old data (not configured in this project)

### How Standard PostgreSQL Compensates
1. **B-Tree composite index** on `(scheme_code, nav_date)` — already exists via the composite primary key.
2. **Standalone index** on `nav_date` — to be added explicitly for date-range-only queries.
3. **Native Partitioning** — available as a future enhancement via `PARTITION BY RANGE (nav_date)` if scale demands it.
4. **Application-layer aggregation** — all heavy analytics already happen in Pandas, not in DB-side `time_bucket()` calls.

---

## 8. Migration Strategy

The migration is a **non-breaking, backward-compatible change** that can be executed in a single release cycle:

1. **Phase 1: Code Changes** — Update `main.py`, `models.py`, `docker-compose.yml`
2. **Phase 2: Data Migration** — Export existing data via `pg_dump`, spin up new PostgreSQL container, restore via `pg_restore`
3. **Phase 3: Documentation** — Update all 7+ documentation files
4. **Phase 4: Verification** — Run application, verify all API endpoints, run ETL pipeline

> **Estimated Effort:** 1-2 hours for an experienced developer.  
> **Risk Level:** Low.  
> **Rollback Plan:** Revert to the TimescaleDB Docker image; `create_hypertable` calls are idempotent.
