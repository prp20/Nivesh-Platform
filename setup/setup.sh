#!/usr/bin/env bash
# =============================================================================
# Nivesh Platform — Cross-Platform Setup Script (Linux / macOS)
# =============================================================================
# Usage:
#   chmod +x setup/setup.sh
#   ./setup/setup.sh
#
# What this script does:
#   1. Checks prerequisites (Python 3.10+, Node.js, Docker)
#   2. Prompts for PostgreSQL: Docker (auto) or external URL
#   3. Installs ta-lib C library
#   4. Creates Python virtual environment and installs dependencies
#   5. Writes backend/.env
#   6. Runs database migrations
#   7. Optionally seeds data
#   8. Starts the FastAPI server
# =============================================================================

set -euo pipefail

# ─── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}══ $* ══${NC}"; }

# ─── Resolve paths ───────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
VENV_DIR="${BACKEND_DIR}/venv"
BACKEND_ENV_FILE="${BACKEND_DIR}/.env"
FRONTEND_ENV_FILE="${FRONTEND_DIR}/.env"
TALIB_SRC_DIR="${PROJECT_ROOT}/ta-lib"

echo -e "${BOLD}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║     Nivesh Platform — Setup Script    ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${NC}"
info "Project root : ${PROJECT_ROOT}"

# =============================================================================
# STEP 1 — Check prerequisites
# =============================================================================
step "Step 1: Checking Prerequisites"

# Python 3.10+
if ! command -v python3 &>/dev/null; then
  error "python3 not found. Please install Python 3.10+ from https://python.org and try again."
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
  success "Python ${PY_VERSION} detected."
else
  error "Python ${PY_VERSION} is too old. Python 3.10+ is required."
fi

# Node.js / nvm
if command -v node &>/dev/null; then
  NODE_VERSION=$(node --version)
  NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d'v' -f2 | cut -d'.' -f1)
  if [[ $NODE_MAJOR -lt 18 ]]; then
    warn "Node.js ${NODE_VERSION} is older than 18. Frontend may have issues."
  else
    success "Node.js ${NODE_VERSION} detected."
  fi
  NPM_VERSION=$(npm --version)
  success "npm ${NPM_VERSION} detected."
else
  warn "Node.js not found. Installing nvm and Node.js 20..."
  if [[ "$OS" == "Darwin" ]]; then
    # macOS
    if command -v brew &>/dev/null; then
      brew install nvm
      NVM_DIR="$HOME/.nvm"
      # shellcheck disable=SC1091
      [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    else
      curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
      NVM_DIR="$HOME/.nvm"
      # shellcheck disable=SC1091
      [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    fi
  else
    # Linux
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
    NVM_DIR="$HOME/.nvm"
    # shellcheck disable=SC1091
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  fi

  # Install Node.js 20
  nvm install 20
  nvm use 20
  success "Node.js 20 installed and activated."
fi

# =============================================================================
# STEP 2 — PostgreSQL setup
# =============================================================================
step "Step 2: PostgreSQL Setup"

echo ""
echo "  How do you want to connect to PostgreSQL?"
echo "  [1] Docker  — auto-managed, starts postgres:16-alpine (default)"
echo "  [2] External — I will provide my own connection URL"
echo ""
read -rp "  Enter choice [1]: " PG_CHOICE
PG_CHOICE="${PG_CHOICE:-1}"

if [[ "$PG_CHOICE" == "2" ]]; then
  echo ""
  echo "  Enter the PostgreSQL URL in this format:"
  echo "  postgresql+asyncpg://user:password@host:port/dbname"
  echo ""
  read -rp "  PostgreSQL URL: " DATABASE_URL
  if [[ -z "$DATABASE_URL" ]]; then
    error "No URL entered. Aborting."
  fi
  if [[ "$DATABASE_URL" != postgresql* ]]; then
    error "URL must start with 'postgresql'. Got: ${DATABASE_URL}"
  fi
  success "Using external PostgreSQL URL."
  USE_DOCKER=false
else
  DATABASE_URL="postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db"
  USE_DOCKER=true
  success "Will use Docker-managed PostgreSQL (URL: ${DATABASE_URL})"
fi

# Verify Docker if needed
if [[ "$USE_DOCKER" == true ]]; then
  if ! command -v docker &>/dev/null; then
    error "Docker not found. Install Docker Desktop from https://docker.com and try again, or choose option [2] for an external PostgreSQL URL."
  fi
  if ! docker info &>/dev/null 2>&1; then
    error "Docker daemon is not running. Start Docker Desktop and try again."
  fi
  success "Docker is available."
fi

# =============================================================================
# STEP 3 — Install ta-lib C library
# =============================================================================
step "Step 3: Installing ta-lib C Library"

OS="$(uname -s)"
TALIB_INSTALLED=false

# ── Universal pre-check: is ta-lib already present on the system? ─────────────
# Covers: prior source installs, apt/brew installs, custom prefix installs.
_talib_already_present() {
  # 1. pkg-config knows about it
  if command -v pkg-config &>/dev/null && pkg-config --exists ta-lib 2>/dev/null; then
    return 0
  fi
  # 2. The shared library is visible to the dynamic linker
  if ldconfig -p 2>/dev/null | grep -q 'libta_lib'; then
    return 0
  fi
  # 3. The header file exists at common install prefixes
  for _h in /usr/include/ta-lib/ta_libc.h \
             /usr/local/include/ta-lib/ta_libc.h \
             /opt/homebrew/include/ta-lib/ta_libc.h; do
    [[ -f "$_h" ]] && return 0
  done
  return 1
}

if _talib_already_present; then
  success "ta-lib C library already installed — skipping installation."
  TALIB_INSTALLED=true
elif [[ "$OS" == "Darwin" ]]; then
  # macOS
  if command -v brew &>/dev/null; then
    info "Installing ta-lib via Homebrew..."
    brew install ta-lib
    success "ta-lib installed via Homebrew."
    TALIB_INSTALLED=true
  else
    warn "Homebrew not found. Install Homebrew first: https://brew.sh"
    warn "Then run: brew install ta-lib"
    warn "Continuing — pip install may fail if ta-lib C library is missing."
  fi

elif [[ "$OS" == "Linux" ]]; then
  # Try apt-get first (Ubuntu/Debian)
  if command -v apt-get &>/dev/null; then
    info "Installing ta-lib via apt-get (requires sudo)..."
    sudo apt-get update -qq
    if sudo apt-get install -y libta-lib-dev &>/dev/null 2>&1; then
      success "ta-lib installed via apt-get."
      TALIB_INSTALLED=true
    else
      warn "apt-get install failed. Falling back to source compile."
    fi
  fi

  # Fallback: compile from bundled source in repo root
  if [[ "$TALIB_INSTALLED" == false ]]; then
    if [[ -d "${TALIB_SRC_DIR}" ]] && [[ -f "${TALIB_SRC_DIR}/configure" ]]; then
      info "Compiling ta-lib from source at ${TALIB_SRC_DIR}..."
      cd "${TALIB_SRC_DIR}"
      ./configure --prefix=/usr/local
      make -j"$(nproc 2>/dev/null || echo 2)"
      sudo make install
      sudo ldconfig
      cd "${PROJECT_ROOT}"
      success "ta-lib compiled and installed from source."
      TALIB_INSTALLED=true
    else
      warn "ta-lib source directory not found at ${TALIB_SRC_DIR}."
      warn "Continuing — pip install may fail if ta-lib C library is missing."
      warn "Manual install: sudo apt-get install libta-lib-dev"
    fi
  fi

else
  warn "Unknown OS '${OS}'. Skipping ta-lib C library install."
  warn "Install ta-lib manually before running pip install."
fi

# =============================================================================
# STEP 4 — Python virtual environment + dependencies
# =============================================================================
step "Step 4: Python Virtual Environment"

cd "${PROJECT_ROOT}"

if [[ ! -d "${VENV_DIR}" ]]; then
  info "Creating virtual environment at ${VENV_DIR}..."
  python3 -m venv "${VENV_DIR}"
  success "Virtual environment created."
else
  info "Virtual environment already exists at ${VENV_DIR}."
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
success "Virtual environment activated."

info "Upgrading pip..."
pip install --upgrade pip --quiet

info "Installing Python dependencies from requirements.txt..."
if pip install -r "${BACKEND_DIR}/requirements.txt" --quiet; then
  success "Python dependencies installed."
else
  if [[ "$TALIB_INSTALLED" == false ]]; then
    error "pip install failed. This is likely because the ta-lib C library is missing.\nInstall it manually (e.g. sudo apt-get install libta-lib-dev) and rerun this script."
  else
    error "pip install failed. Check the output above for details."
  fi
fi

# =============================================================================
# STEP 5 — Write backend/.env
# =============================================================================
step "Step 5: Environment Configuration"

# Generate a random SECRET_KEY if needed
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || echo "change-me-to-a-random-string")

# Backend .env
WRITE_BACKEND_ENV=true
if [[ -f "${BACKEND_ENV_FILE}" ]]; then
  warn "backend/.env already exists at ${BACKEND_ENV_FILE}"
  read -rp "  Overwrite it with the new configuration? (y/N): " OVERWRITE
  OVERWRITE="${OVERWRITE:-n}"
  if [[ "$OVERWRITE" =~ ^[Yy]$ ]]; then
    WRITE_BACKEND_ENV=true
  else
    info "Keeping existing backend/.env."
    WRITE_BACKEND_ENV=false
  fi
fi

if [[ "$WRITE_BACKEND_ENV" == true ]]; then
  cat > "${BACKEND_ENV_FILE}" <<EOF
# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=${DATABASE_URL}

# ── API ───────────────────────────────────────────────────────────────────────
API_V1_STR=/api/v1
PROJECT_NAME=Nivesh API

# ── Security — CHANGE IN PRODUCTION ──────────────────────────────────────────
ENABLE_AUTH=false
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ── Third-party APIs (if needed) ──────────────────────────────────────────────
# ALPHA_VANTAGE_APIKEY=your_key_here
# SUPABASE_PASSWORD=your_password_here
EOF
  success "backend/.env written with generated SECRET_KEY"
fi

# Frontend .env
WRITE_FRONTEND_ENV=true
if [[ -f "${FRONTEND_ENV_FILE}" ]]; then
  warn "frontend/.env already exists at ${FRONTEND_ENV_FILE}"
  read -rp "  Overwrite it? (y/N): " OVERWRITE
  OVERWRITE="${OVERWRITE:-n}"
  if [[ "$OVERWRITE" =~ ^[Yy]$ ]]; then
    WRITE_FRONTEND_ENV=true
  else
    info "Keeping existing frontend/.env."
    WRITE_FRONTEND_ENV=false
  fi
fi

if [[ "$WRITE_FRONTEND_ENV" == true ]]; then
  cat > "${FRONTEND_ENV_FILE}" <<EOF
# ── API URL ──────────────────────────────────────────────────────────────────
# For development: http://localhost:8000/api/v1
# For production: /api/v1 (same origin — backend serves frontend)
VITE_API_URL=/api/v1
EOF
  success "frontend/.env written"
fi

if grep -q 'ENABLE_AUTH=false' "${BACKEND_ENV_FILE}" 2>/dev/null; then
  warn "ENABLE_AUTH=false — write endpoints are unprotected. Set to true for production."
fi

# =============================================================================
# STEP 6 — Start Docker PostgreSQL (if chosen)
# =============================================================================
if [[ "$USE_DOCKER" == true ]]; then
  step "Step 6: Starting Docker PostgreSQL"
  info "Starting PostgreSQL container via Docker Compose..."
  docker compose -f "${BACKEND_DIR}/docker-compose.yml" up -d postgres

  info "Waiting for PostgreSQL to become ready (up to 30s)..."
  for i in $(seq 1 30); do
    if docker compose -f "${BACKEND_DIR}/docker-compose.yml" exec -T postgres \
        pg_isready -U nivesh_admin -d nivesh_db &>/dev/null 2>&1; then
      success "PostgreSQL is ready."
      break
    fi
    if [[ $i -eq 30 ]]; then
      error "PostgreSQL did not become ready after 30 seconds. Check Docker logs:\n  docker compose -f backend/docker-compose.yml logs postgres"
    fi
    sleep 1
  done
else
  step "Step 6: PostgreSQL (External — skipping Docker)"
  info "Using your external PostgreSQL. Ensure it is reachable at the provided URL."
fi

# =============================================================================
# STEP 7 — Database migrations
# =============================================================================
step "Step 7: Database Migrations"

cd "${BACKEND_DIR}"

info "Creating MF tables (SQLAlchemy create_all)..."
python3 scripts/db_init.py
success "MF tables created."

info "Running Alembic migration for stock tables..."
alembic upgrade head
success "Stock tables migrated."

# =============================================================================
# STEP 8 — Optional seeding
# =============================================================================
step "Step 8: Data Seeding (Optional)"

echo ""
warn "Seeding fetches live data from AMFI and yfinance — this can take 30–90 minutes."
echo ""
read -rp "  Seed mutual fund data (benchmarks + funds + NAV history)? (y/N): " SEED_MF
SEED_MF="${SEED_MF:-n}"

if [[ "$SEED_MF" =~ ^[Yy]$ ]]; then
  info "Seeding benchmark indices from CSV files..."
  python3 scripts/seed_indices.py
  success "Benchmark indices seeded."

  info "Seeding fund master records..."
  python3 scripts/seed_funds.py
  success "Fund master seeded."

  info "Fetching NAV history and computing metrics (this may take 30–60 minutes)..."
  python3 scripts/sync_data.py
  success "Fund NAV history and metrics complete."
fi

echo ""
read -rp "  Also seed stock master + 5y price history from yfinance? (y/N): " SEED_STOCKS
SEED_STOCKS="${SEED_STOCKS:-n}"

if [[ "$SEED_STOCKS" =~ ^[Yy]$ ]]; then
  info "Seeding stock master (18 large-cap stocks + 3 indices)..."
  python3 scripts/seed/seed_stock_master.py
  success "Stock master seeded."

  info "Backfilling 5 years of price data from yfinance (20–40 minutes)..."
  python3 scripts/seed/backfill_prices.py 5y
  success "Stock price history backfilled."
fi

# =============================================================================
# STEP 9 — Build frontend
# =============================================================================
step "Step 9: Building Frontend"

cd "${FRONTEND_DIR}"

info "Installing frontend dependencies (npm install)..."
npm install --legacy-peer-deps
success "Frontend dependencies installed."

info "Building frontend for production (npm run build)..."
npm run build
if [[ ! -d "${FRONTEND_DIR}/dist" ]]; then
  error "Frontend build failed. Check npm run build output above."
fi
success "Frontend built and ready at ${FRONTEND_DIR}/dist/"

# =============================================================================
# STEP 10 — Start API server
# =============================================================================
step "Step 10: Starting FastAPI Server"

echo ""
echo -e "${GREEN}${BOLD}  Setup complete! Starting Nivesh API...${NC}"
echo ""
echo -e "${GREEN}  Frontend + API  :  http://localhost:8000${NC}"
echo -e "${GREEN}  API docs        :  http://localhost:8000/docs${NC}"
echo -e "${GREEN}  Health          :  http://localhost:8000/api/health${NC}"
echo ""

cd "${BACKEND_DIR}"
exec uvicorn app.main:app \
  --host "${NIVESH_HOST:-0.0.0.0}" \
  --port "${NIVESH_PORT:-8000}" \
  --workers "${NIVESH_WORKERS:-1}" \
  --reload \
  --log-level info
