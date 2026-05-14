#!/usr/bin/env bash
# =============================================================================
# Nivesh Client — Local Setup Script (Linux / macOS)
# =============================================================================
# Usage:
#   chmod +x setup/setup.sh
#   ./setup/setup.sh
#
# What this script does:
#   1. Check Python 3.10+
#   2. Create ~/.nivesh/ directory
#   3. Copy .env.example → ~/.nivesh/.env  (if missing)
#   4. pip install -e . (editable install of nivesh-client + nivesh-shared)
#   5. Run alembic upgrade head (init SQLite schema)
# =============================================================================

set -euo pipefail

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NIVESH_DIR="${HOME}/.nivesh"
ENV_FILE="${NIVESH_DIR}/.env"
ENV_EXAMPLE="${CLIENT_DIR}/.env.example"

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║    Nivesh Client — Local Setup Script    ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"
info "Client directory : ${CLIENT_DIR}"
info "Data directory   : ${NIVESH_DIR}"

# =============================================================================
# STEP 1 — Check Python 3.10+
# =============================================================================
info "Checking Python version..."
if ! command -v python3 &>/dev/null; then
    error "python3 not found. Please install Python 3.10+ and try again."
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)"; then
    success "Python ${PY_VERSION} detected."
else
    error "Python ${PY_VERSION} is too old. Python 3.10+ is required."
fi

# =============================================================================
# STEP 2 — Create ~/.nivesh/
# =============================================================================
info "Creating ${NIVESH_DIR} ..."
mkdir -p "${NIVESH_DIR}"
success "${NIVESH_DIR} ready."

# =============================================================================
# STEP 3 — Copy .env.example → ~/.nivesh/.env  (skip if already exists)
# =============================================================================
if [[ -f "${ENV_FILE}" ]]; then
    warn "${ENV_FILE} already exists — skipping copy."
    warn "Edit it manually if you need to change NIVESH_SERVER_URL."
else
    if [[ -f "${ENV_EXAMPLE}" ]]; then
        cp "${ENV_EXAMPLE}" "${ENV_FILE}"
        success "Copied .env.example → ${ENV_FILE}"
        echo ""
        warn "ACTION REQUIRED: Edit ${ENV_FILE} and set NIVESH_SERVER_URL"
        echo "  Default: https://nivesh-server.onrender.com"
        echo ""
    else
        warn ".env.example not found at ${ENV_EXAMPLE} — creating minimal .env"
        cat > "${ENV_FILE}" <<'EOF'
NIVESH_SERVER_URL=https://nivesh-server.onrender.com
CLIENT_PORT=8001
DEBUG=false
EOF
        success "Created minimal ${ENV_FILE}"
    fi
fi

# =============================================================================
# STEP 4 — pip install
# =============================================================================
info "Installing Python packages..."
cd "${CLIENT_DIR}"

# Use the active venv pip, or fall back to pip3
PIP_CMD="pip"
if ! command -v pip &>/dev/null; then
    PIP_CMD="pip3"
fi

if "${PIP_CMD}" install -r requirements.txt --quiet; then
    success "Python packages installed."
else
    error "pip install failed. Check the output above."
fi

# =============================================================================
# STEP 5 — Run Alembic migrations (initialise SQLite schema)
# =============================================================================
info "Running Alembic migrations to initialise SQLite schema..."
cd "${CLIENT_DIR}"
if alembic upgrade head; then
    success "SQLite schema initialised at ${NIVESH_DIR}/client.db"
else
    warn "Alembic migration failed — the app will retry on first startup."
fi

# =============================================================================
# Done
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}  ╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}  ║     Nivesh Client setup complete!             ║${NC}"
echo -e "${GREEN}${BOLD}  ╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}  Start the client:${NC}"
echo "    cd ${CLIENT_DIR}"
echo "    uvicorn app.main:app --port 8001 --reload"
echo ""
echo -e "${CYAN}  API docs : http://localhost:8001/docs${NC}"
echo -e "${CYAN}  Health   : http://localhost:8001/health${NC}"
echo ""
