# Changelog

## 2026-04-21 — Session: v2.0.0 release notes, branch merge verification, GitHub issue triage

### Branch Merge Checks
- Verified `feature/fundamental_agentic_analysis` → `main`: no conflicts, clean merge
- Verified `feature/fundamental_agentic_analysis` → `dev`: no conflicts, clean merge
- Verified `dev` → `main`: no conflicts, clean merge
- Confirmed PRs #55 and #56 already merged; main at commit 889a21b

### Files Modified
- `RELEASE_NOTES.md` — v2.0.0 "The Intelligence Layer" release notes prepended (covers AI scoring engine, 250+ stocks, frontend overhaul, backend hardening, setup improvements, docs overhaul, breaking changes, upgrade instructions)

### GitHub Issues Closed
- #17 closed: Deterministic LangGraph fundamental analysis (delivered in v2.0.0)
- #54 closed: Update StockDetail display with correct insights (StockDetail.jsx redesigned)
- #19 closed: Clean mockup design for every page (full frontend overhaul + Stitch designs)

### Memory Updated
- `memory/project_status_2026_04_21.md` — new project status record for v2.0.0
- `memory/changelog.md` — updated (this entry)
- `memory/MEMORY.md` — index updated with v2.0.0 status entry

## 2026-04-16 — Session: Auth bypass removal, setup script fixes, fundamentals UX

### Issues Fixed
- #Issue1 (UI auth on load): Removed VITE_API_TOKEN bypass; enforced login via localStorage-only JWT
- #35/#36/#37 (setup script failures): Removed jose dependency, added shared admin_helper.py, fixed SECRET_KEY strength on Windows, made TA-Lib non-fatal, removed VITE_API_TOKEN from frontend .env
- #49 (fundamentals seeding): Added options [3] Stock+Fundamentals and [5] All to seeding menu in all setup scripts
- #Issue6 (fundamentals button stuck): Converted /pipeline/screener/{symbol} to background task; UI now polls /pipeline/status every 5s until job completes

### Modified Files
- `frontend/src/context/AuthContext.jsx` — Removed VITE_API_TOKEN env bypass; only reads localStorage token
- `frontend/src/api/apiClient.js` — Removed VITE_API_TOKEN and VITE_ADMIN_TOKEN env reads; simplified to localStorage-only auth
- `frontend/.env.development` — Removed VITE_ADMIN_TOKEN=dev-admin-token
- `frontend/.env` — Removed VITE_API_TOKEN bypass token (kept VITE_API_URL only)
- `frontend/src/pages/StockDetail.jsx` — Added useRef for poll cleanup; replaced sync handleSyncFundamentals with trigger+poll pattern (5s interval, 5min timeout)
- `backend/app/routers/pipeline.py` — /screener/{symbol}: converted synchronous scrape to background task; returns immediately with job_name for status polling
- `setup/admin_helper.py` — NEW: shared credential helper (bcrypt only, no jose dependency); called by all setup scripts
- `setup/setup.sh` — Uses shared admin_helper.py; removed jwt/TOKEN_FILE; made TA-Lib non-fatal (warn instead of crash); updated seeding menu (6 options); added setup completion summary banner
- `setup/setup.ps1` — Uses shared admin_helper.py; removed jwt/TOKEN_FILE; fixed SECRET_KEY to use Python secrets module; updated seeding menu (6 options)
- `setup/setup.bat` — Uses shared admin_helper.py; removed echo-based Python helper; fixed SECRET_KEY via Python; updated seeding menu (6 options)
- `backend/scripts/seed/seed_fundamentals.py` — NEW: async script to scrape screener.in for all stocks + ratio recompute

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

## 2026-04-25 12:41
- docs/CODE_REVIEW.md: Created full codebase code review — 48 issues (9 critical, 18 high, 13 medium, 8 low) across backend and frontend, covering security, financial calculation correctness, React patterns, and data pipeline reliability

## 2026-04-25 (mf-analyser implementation)
- backend/mf_analyser/__init__.py: New module — LangGraph-based MF analysis workflow
- backend/mf_analyser/state.py: MFAnalysisState TypedDict with full field set
- backend/mf_analyser/prompts/prompts.py: All LLM prompt strings (SYSTEM_PROMPT, build_user_prompt, FALLBACK_VERDICT_TEMPLATE)
- backend/mf_analyser/nodes/data_nodes.py: fetch_fund_node (loads FundMaster, NAV, benchmark) and persist_node (upserts fund_analysis, updates fund_metrics)
- backend/mf_analyser/nodes/compute_nodes.py: compute_metrics_node (wraps analytics.compute_all_metrics)
- backend/mf_analyser/nodes/peer_nodes.py: fetch_peers_node, rank_peers_node, skip_peers_node, route_peer_analysis (conditional edge)
- backend/mf_analyser/nodes/verdict_nodes.py: generate_verdict_node (Groq llama3-70b, JSON parse, deterministic fallback)
- backend/mf_analyser/graph.py: StateGraph assembly + run_mf_analyser() entry point
- backend/app/models.py: Added FundAnalysis model; added analysis_verdict/analysis_summary/analysis_at to FundMetrics
- backend/alembic/versions/002_add_fund_analysis.py: Idempotent migration — creates fund_analysis table, adds 3 cols to fund_metrics
- backend/app/routers/mf_analysis.py: POST/GET /api/v1/mf-analysis/{scheme_code} + _run_bulk_mf_analysis helper
- backend/app/main.py: Registered mf_analysis router
- backend/app/routers/pipeline.py: Added POST /api/v1/pipeline/mf-analysis/all admin bulk trigger
- backend/pipeline/scheduler.py: Added weekly mf_analysis_weekly job (Sunday 03:00 IST)
- backend/scripts/run_mf_analyser.py: CLI entry point for single-fund analysis
