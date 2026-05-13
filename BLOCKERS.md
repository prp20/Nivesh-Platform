# Blockers — Deferred Work

This file tracks known blockers that must be resolved before certain features can go live.
Each blocker references the code that needs to change and what it's blocked on.

---

## BLOCKER-001 — App code references `sync_jobs` / `pipeline_audit` (not `etl_runs`)

**Status:** Open  
**Blocking:** Production deployment of the ETL pipeline; `routers/sync.py` will 404 until resolved  
**Introduced in:** Phase 1 (2026-05-13)

### Context

The Phase 1 database schema introduces `etl_runs` as a unified ETL tracking table,
replacing the two existing tables `sync_jobs` and `pipeline_audit`.

The new Supabase database has **only `etl_runs`** — `sync_jobs` and `pipeline_audit`
are not created in the Phase 1 migrations.

However, the following server app files still reference the old tables:

| File | References |
|---|---|
| `app/crud.py` | `sync_jobs` table — create, read, update sync job records |
| `app/routers/sync.py` | `sync_jobs` — GET /sync/status, POST /sync/trigger |
| `app/sync.py` | `sync_jobs` — MF NAV sync pipeline writes job status here |
| `backend/pipeline/audit.py` | `pipeline_audit` — stock pipeline job tracking |

### What needs to change

1. Update `app/crud.py` — replace all `sync_jobs` queries with `etl_runs` equivalents
2. Update `app/routers/sync.py` — read from `etl_runs`, use new column names
3. Update `app/sync.py` — write ETL status to `etl_runs` (pipeline_name='amfi_nav', entity_id=scheme_code)
4. Update `backend/pipeline/audit.py` — write to `etl_runs` (pipeline_name=job_name, entity_id=symbol)
5. Remove `sync_jobs` and `pipeline_audit` from `app/models.py` (after all references updated)

### `etl_runs` column mapping from old tables

**From `sync_jobs`:**
| sync_jobs | etl_runs |
|---|---|
| `id` (UUID) | `id` (BIGSERIAL) |
| `scheme_code` | `entity_id` |
| `status` | `status` (same values: RUNNING/COMPLETED/FAILED) |
| `message` | `error_msg` |
| `created_at` | `started_at` |
| `updated_at` | `ended_at` |
| _(none)_ | `pipeline_name` = `'amfi_nav'` |

**From `pipeline_audit`:**
| pipeline_audit | etl_runs |
|---|---|
| `id` | `id` |
| `job_name` | `pipeline_name` |
| `stock_id` (int) | `entity_id` (symbol string — join stocks table) |
| `status` | `status` |
| `started_at` | `started_at` |
| `ended_at` | `ended_at` |
| `records_in` | `records_in` |
| `records_out` | `records_out` |
| `error_msg` | `error_msg` |
| `metadata_` | `metadata` |

---

*Add new blockers below this line in the same format.*
