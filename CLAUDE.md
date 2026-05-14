# Nivesh Platform — Monorepo Root

## Project Overview

Nivesh is a personal stock and mutual fund analytics platform split into three packages:

| Package | Purpose | Deployed To |
|---|---|---|
| `nivesh-server/` | Cloud FastAPI app — all market data, analytics, ingestion | Render.com |
| `nivesh-client/` | Local FastAPI + React app — user portfolio, agent, UI | User's machine |
| `nivesh-shared/` | Pip-installable Pydantic schemas — the API contract | Both |

**Core principle:** The server owns all market data and computation. The client stores only user-private data and a TTL cache.

> **Legacy reference:** `backend/` and `frontend/` are the original monolithic structure — kept for reference during migration. Do not add new code there.

## Directory Structure

```
stock_platform/
├── nivesh-server/     ← Cloud FastAPI (PostgreSQL via Supabase)
├── nivesh-client/     ← Local FastAPI + React (SQLite)
├── nivesh-shared/     ← Shared Pydantic schemas
├── backend/           ← LEGACY — original monolith, reference only
├── frontend/          ← LEGACY — original frontend, reference only
├── docs/              ← Architecture and API reference docs
├── setup/             ← Install scripts (setup.sh, setup.bat)
├── requirements-dev.txt
├── .gitignore
└── CLAUDE.md
```

## Development Setup (New Structure)

```bash
# Install all packages in editable mode
pip install -r requirements-dev.txt

# Run server locally (needs .env with DATABASE_URL)
cd nivesh-server && uvicorn app.main:app --port 8000 --reload

# Run client locally (SQLite auto-created at ~/.nivesh/nivesh_client.db)
cd nivesh-client && uvicorn app.main:app --port 8001 --reload
```

## Legacy Development (Original Structure)

```bash
# Still works — original monolith
cd backend && uvicorn app.main:app --port 8000 --reload
cd frontend && npm run dev
```

## Implementation Phases

| Phase | Status | Description |
|---|---|---|
| P0 | Done | Repo restructure — this layout |
| P1 | Done | Supabase DB setup — 18 Alembic migrations + seed scripts |
| P2 | Done | Server: Core API on Render — auth, EtlRun model, delta-sync, Render deploy |
| P3 | Pending | Server: Ingestion pipeline (NSE bhavcopy, AMFI) |
| P4 | Pending | Client: SQLite + local API |
| P5 | Pending | Client: JWT auth + sync engine |
| P6 | Pending | Client: Agentic layer |
| P7 | Pending | Client: UI adaptation |
| P8 | Pending | CI/CD + production hardening |

## Keeping CLAUDE.md Up to Date

**This file must be updated whenever a phase completes or a significant change is made to the project structure, architecture rules, or development workflow.**

- When a phase moves to Done: update the Implementation Phases table with the completion description.
- When a new architectural rule is established or removed: update the Key Architecture Rules section.
- When new sensitive file patterns are introduced: update the Sensitive Files section.
- When directory structure changes (new top-level dirs, removed dirs): update the Directory Structure block.

Do not defer these updates to a later commit — update CLAUDE.md in the same commit as the change.

## Key Architecture Rules

- **Never** connect client directly to cloud PostgreSQL — all data flows via REST API
- **Never** run pandas-ta or scipy on the client — server pre-computes all indicators
- **Never** store JWT tokens in browser — stored in client SQLite `auth_tokens` table
- **Always** use Supavisor pooler URL (port 6543) for runtime; direct URL (port 5432) for Alembic only
- **Always** import shared schemas from `schemas.*` (nivesh-shared), not from `app.schemas`

## Sensitive Files — Never Commit

- `.env` files in any subdirectory
- `*.db`, `*.sqlite` — database files
- `backend/venv/`, `backend/db_data/`

## Reference Docs

- Full implementation plan: `NIVESH_IMPLEMENTATION_PLAN.md`
- Architecture overview: `NIVESH_ARCHITECTURE.md`
- Original API reference: `docs/API_REFERENCE.md`
