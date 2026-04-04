#!/usr/bin/env bash
# =============================================================================
# Nivesh Platform — Production-Ready Startup Script (Linux / macOS)
# =============================================================================
# Usage:
#   chmod +x start.sh
#   ./start.sh              # Full setup + launch
#   ./start.sh --skip-deps  # Skip pip install (already up to date)
#   ./start.sh --seed       # Also run seed scripts after startup
# =============================================================================

set -euo pipefail

# ─── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ─── Parse flags ─────────────────────────────────────────────────────────────
SKIP_DEPS=false
RUN_SEED=false
for arg in "$@"; do
  case $arg in
    --skip-deps) SKIP_DEPS=true ;;
    --seed)      RUN_SEED=true  ;;
    --help|-h)
      echo "Usage: $0 [--skip-deps] [--seed]"
      echo "  --skip-deps  Skip virtual-env creation and pip install"
      echo "  --seed       Run seed/ETL scripts after server starts"
      exit 0 ;;
    *) warn "Unknown flag: $arg (ignored)" ;;
  esac
done

# ─── Resolve project root ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
VENV_DIR="${BACKEND_DIR}/venv"
ENV_FILE="${BACKEND_DIR}/.env"

info "Project root : ${SCRIPT_DIR}"
info "Backend dir  : ${BACKEND_DIR}"

# ─── 1. Python check ─────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  error "python3 not found. Install Python 3.10+ and try again."
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python version: ${PY_VERSION}"
if python3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
  success "Python >= 3.10 detected."
else
  warn "Python ${PY_VERSION} detected. Python 3.10+ is recommended."
fi

# ─── 2. Virtual environment ──────────────────────────────────────────────────
if [[ "$SKIP_DEPS" == false ]]; then
  if [[ ! -d "${VENV_DIR}" ]]; then
    info "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
    success "Virtual environment created."
  else
    info "Virtual environment already exists."
  fi

  # Activate
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  success "Virtual environment activated."

  # ─── 3. Install dependencies ──────────────────────────────────────────────
  info "Installing Python dependencies from requirements.txt..."
  pip install --upgrade pip --quiet
  pip install -r "${BACKEND_DIR}/requirements.txt" --quiet
  success "Dependencies installed."
else
  if [[ -d "${VENV_DIR}" ]]; then
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    success "Virtual environment activated (deps skipped)."
  else
    warn "--skip-deps used but no venv found. Running with system Python."
  fi
fi

# ─── 4. Environment variables (.env) ─────────────────────────────────────────
if [[ ! -f "${ENV_FILE}" ]]; then
  warn ".env not found — creating from defaults. REVIEW before production use."
  cat > "${ENV_FILE}" <<'EOF'
# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db

# ── API ───────────────────────────────────────────────────────────────────────
API_V1_STR=/api/v1
PROJECT_NAME=Nivesh API

# ── Security — CHANGE IN PRODUCTION ──────────────────────────────────────────
ENABLE_AUTH=false
SECRET_KEY=change-this-to-a-long-random-string-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ── CORS ──────────────────────────────────────────────────────────────────────
# Add your frontend origin here if it differs from the default
EOF
  success ".env created at ${ENV_FILE}"
else
  info "Using existing .env at ${ENV_FILE}"
fi

# Production safety check
if grep -q 'ENABLE_AUTH=false' "${ENV_FILE}" 2>/dev/null; then
  warn "ENABLE_AUTH is false — write endpoints are unprotected. Set ENABLE_AUTH=true for production."
fi
if grep -q 'dev-secret-key' "${ENV_FILE}" 2>/dev/null; then
  warn "SECRET_KEY is the dev default — replace it before going to production."
fi

# ─── 5. Docker / PostgreSQL ───────────────────────────────────────────────────
if command -v docker &>/dev/null && command -v docker compose &>/dev/null; then
  info "Starting PostgreSQL via Docker Compose..."
  docker compose -f "${BACKEND_DIR}/docker-compose.yml" up -d postgres

  # Wait for Postgres to be ready
  info "Waiting for PostgreSQL to become ready..."
  for i in $(seq 1 30); do
    if docker compose -f "${BACKEND_DIR}/docker-compose.yml" exec -T postgres \
        pg_isready -U nivesh_admin -d nivesh_db &>/dev/null 2>&1; then
      success "PostgreSQL is ready."
      break
    fi
    if [[ $i -eq 30 ]]; then
      error "PostgreSQL did not become ready after 30 seconds."
    fi
    sleep 1
  done
else
  warn "Docker / docker compose not found. Assuming PostgreSQL is already running on localhost:5432."
fi

# ─── 6. Database migrations ───────────────────────────────────────────────────
info "Running database migrations (create_all)..."
cd "${BACKEND_DIR}"
python3 -c "
import asyncio, sys, os
sys.path.insert(0, '.')
from app.database import engine, Base
from app.models import FundMaster, BenchmarkMaster, FundNavHistory, BenchmarkNavHistory, FundMetrics, BenchmarkMetrics, SyncJob

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Migrations applied successfully.')
    await engine.dispose()

asyncio.run(migrate())
"
success "Database schema is up to date."

# ─── 7. (Optional) Seed data ──────────────────────────────────────────────────
if [[ "$RUN_SEED" == true ]]; then
  info "Running seed scripts..."

  # Start server temporarily for seeding (seeding scripts call the HTTP API)
  info "Starting background server for seeding..."
  uvicorn app.main:app --host 127.0.0.1 --port 8000 &
  SERVER_PID=$!
  sleep 4  # Let server boot

  info "Seeding benchmark master data..."
  python3 scripts/seed/seed_benchmarks.py || warn "seed_benchmarks.py failed (may already be seeded)"

  info "Importing Nifty index history from CSV..."
  python3 scripts/seed/import_nifty_indices.py || warn "import_nifty_indices.py failed"

  info "Running ETL pipeline (may take several minutes)..."
  python3 scripts/etl_populate_data.py || warn "ETL pipeline failed — check etl_populate.log"

  kill $SERVER_PID 2>/dev/null || true
  success "Seed phase complete."
fi

# ─── 8. Start FastAPI server ──────────────────────────────────────────────────
HOST="${NIVESH_HOST:-0.0.0.0}"
PORT="${NIVESH_PORT:-8000}"
WORKERS="${NIVESH_WORKERS:-1}"

info "Starting FastAPI server on ${HOST}:${PORT} (workers=${WORKERS})..."
echo ""
echo -e "${GREEN}  API docs   :  http://localhost:${PORT}/docs${NC}"
echo -e "${GREEN}  ReDoc      :  http://localhost:${PORT}/redoc${NC}"
echo -e "${GREEN}  Health     :  http://localhost:${PORT}/${NC}"
echo ""

cd "${BACKEND_DIR}"
exec uvicorn app.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --reload \
  --log-level info
