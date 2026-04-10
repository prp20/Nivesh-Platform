# Changelog

## 2026-04-10 — Session: Cross-platform setup scripts + Documentation + Frontend Build

### Frontend Build & Environment Configuration
- Created `frontend/.env` — base environment config with `VITE_API_URL=/api/v1` (gitignored)
- Created `frontend/.env.production` — production config with relative API URL for same-origin serving (gitignored)
- Existing `frontend/.env.development` — dev config with `VITE_API_URL=http://localhost:8000/api/v1`
- Executed `npm run build` — production build outputs to `frontend/dist/`
- Verified: No hardcoded localhost URLs in built code
- Verified: API configuration is environment-driven via `VITE_API_URL`
- All API calls use `src/api/apiClient.js` which reads from env with safe fallback to `/api/v1`

### Environment-Driven API URL Pattern
| Environment | VITE_API_URL | Usage |
|---|---|---|
| Development | `http://localhost:8000/api/v1` | Dev server (5173) → Backend (8000) |
| Production | `/api/v1` | Backend serves frontend at same origin |
| Fallback | `/api/v1` | Used if env var undefined |

## 2026-04-10 — Cross-platform setup scripts + Documentation overhaul

### New Files
- `setup/setup.sh` — Linux/macOS bash setup script: prereq checks, PostgreSQL choice (Docker or external URL), ta-lib C library install, venv + pip, .env generation, DB migrations, optional seeding, frontend build, API server start
- `setup/setup.bat` — Windows CMD batch equivalent; recommends setup.ps1 for better experience; includes Node.js requirement, dual .env creation, frontend build
- `setup/setup.ps1` — Windows PowerShell setup script with coloured output, same logic as setup.sh; handles TA-Lib pre-built wheel attempt with conda/WSL fallback instructions; includes Node.js check, frontend build
- `setup/README.md` — Setup scripts documentation with quick start for all platforms, what each script does, platform-specific notes, common issues
- `docs/INSTALLATION.md` — Complete installation guide covering system requirements, prerequisites (Python 3.10+, Node.js 18+, Docker, PostgreSQL), step-by-step setup, configuration files, troubleshooting, post-installation checklist

### Enhanced Files
- `setup/setup.sh` — Added frontend setup:
  - Node.js/nvm installation (curl-based for Linux/macOS, brew for macOS)
  - Frontend `.env` generation (VITE_API_URL=/api/v1)
  - Backend `.env` with auto-generated SECRET_KEY and third-party API placeholders
  - `npm install --legacy-peer-deps` in frontend
  - `npm run build` to create production frontend bundle
  - Frontend served via backend (removed separate dev server instruction)

- `setup/setup.ps1` — Added frontend setup (PowerShell):
  - Node.js requirement check (now fatal if missing — suggests winget or nodejs.org)
  - Frontend/backend `.env` generation with auto-generated SECRET_KEY
  - `npm install --legacy-peer-deps` and `npm run build` steps
  - Error handling and verification of dist directory

- `setup/setup.bat` — Added frontend setup (CMD Batch):
  - Node.js requirement check (fatal if missing)
  - Frontend/backend `.env` files with timestamp-based SECRET_KEY
  - `npm install` and `npm run build` steps
  - Verifies dist directory creation

### Revamped Files
- `README.md` — Clean, professional redesign (concise & to-the-point):
  - Brief tagline and feature overview
  - One-command setup for all platforms
  - Documentation hub (links to 9 detailed guides in docs/)
  - Tech stack summary (one-liner format)
  - Simple project structure diagram
  - Quick development setup instructions
  - Security best practices with production config note
  - Contributing guidelines
  - Help section pointing to proper docs
  - No redundant information — all details in linked docs

### Modified Files
- `CLAUDE.md` — Multiple improvements:
  - Replaced 5 non-existent seed script references with actual scripts (seed_funds.py, seed_indices.py, sync_data.py, etc.)
  - Expanded pipeline schedule from 2 jobs to all 7 scheduled jobs (price, index, ratio refresh, TA, ratings, fundamental scrape, quarterly ratios)
  - Added new pipeline modules to project layout (ratio_engine, metric_recompute, technical_analysis, rating_engine, normalizer)
  - Added new routers (screener, pipeline) to layout
  - Updated Redux slices list (stockCompareSlice, fundDetailSlice, dashboardSlice)
  - Updated frontend pages list (Screener, StockCompare, IndexDetail)
  - Fixed "7 SQLAlchemy models" to "16 tables: 7 MF + 9 stocks"
  - Added health check command
  - Added ta-lib C library install note with apt-get and source compile options
  - Fixed Alembic section to reference migration filename instead of hardcoded table count
  - Added database access patterns section (get_db vs raw_connection)
  - Consolidated Fundamental Scraper section
