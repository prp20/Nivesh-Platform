#!/usr/bin/env bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
COMPOSE_FILE="${BACKEND_DIR}/docker-compose.yml"

echo -e "${RED}==================================================${NC}"
echo -e "${RED}  Nivesh Platform -- Teardown Script (Linux/macOS)${NC}"
echo -e "${RED}==================================================${NC}"
echo ""
echo -e "${YELLOW}WARNING: This script will DESTROY the local environment,${NC}"
echo -e "${YELLOW}databases, virtual environments, and generated files.${NC}"
echo ""
read -r -p "Are you sure you want to proceed? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Teardown cancelled."
    exit 0
fi

echo ""
echo -e "${GREEN}[1/5] Stopping Servers...${NC}"
if pkill -f uvicorn >/dev/null 2>&1; then
    echo "  Killed uvicorn API server."
else
    echo "  No uvicorn processes found."
fi
if pkill -f node >/dev/null 2>&1; then
    echo "  Killed node processes."
else
    echo "  No node processes found."
fi

echo ""
echo -e "${GREEN}[2/5] Database Teardown...${NC}"
if [[ -f "$COMPOSE_FILE" ]]; then
    read -r -p "Do you want to stop and DELETE the Docker PostgreSQL volumes? (y/N): " DEL_DB
    if [[ "$DEL_DB" =~ ^[Yy]$ ]]; then
        echo "  Running docker compose down -v..."
        docker compose -f "$COMPOSE_FILE" down -v || true
        echo "  Docker DB destroyed."
    else
        echo "  Skipping Docker teardown."
    fi
else
    echo "  No docker-compose.yml found. Skipping Docker DB teardown."
fi

echo ""
echo -e "${GREEN}[3/5] Environment Cleanup...${NC}"
if [[ -d "${BACKEND_DIR}/venv" ]]; then
    echo "  Removing backend virtual environment..."
    rm -rf "${BACKEND_DIR}/venv"
fi
if [[ -d "${FRONTEND_DIR}/node_modules" ]]; then
    echo "  Removing frontend node_modules..."
    rm -rf "${FRONTEND_DIR}/node_modules"
fi
if [[ -d "${FRONTEND_DIR}/dist" ]]; then
    echo "  Removing frontend build (dist)..."
    rm -rf "${FRONTEND_DIR}/dist"
fi

echo ""
echo -e "${GREEN}[4/5] Configuration Cleanup...${NC}"
if [[ -f "${BACKEND_DIR}/.env" ]]; then
    rm -f "${BACKEND_DIR}/.env"
    echo "  Deleted backend/.env"
fi
if [[ -f "${FRONTEND_DIR}/.env" ]]; then
    rm -f "${FRONTEND_DIR}/.env"
    echo "  Deleted frontend/.env"
fi

echo ""
echo -e "${GREEN}[5/5] System Dependencies (DANGEROUS)${NC}"
echo -e "${YELLOW}  Do you want to globally uninstall Python and Node.js from your system?${NC}"
echo -e "${YELLOW}  WARNING: This might break other applications on your computer.${NC}"
read -r -p "Uninstall global dependencies? (y/N): " UNINSTALL
if [[ "$UNINSTALL" =~ ^[Yy]$ ]]; then
    OS="$(uname -s)"
    if [[ "$OS" == "Darwin" ]]; then
        if command -v brew &>/dev/null; then
            echo "  Attempting to uninstall via Homebrew..."
            brew uninstall python node || true
        fi
    else
        if command -v apt-get &>/dev/null; then
            echo "  Attempting to uninstall via apt-get (requires sudo)..."
            sudo apt-get remove -y python3 nodejs || true
        fi
    fi
    echo "  Uninstallation attempt complete."
else
    echo "  Skipped globally uninstalling Python and Node.js."
fi

echo ""
echo -e "${GREEN}Teardown complete!${NC}"
