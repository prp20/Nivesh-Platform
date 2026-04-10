# Installation Guide — Nivesh Platform

This document provides a complete guide to installing and running the Nivesh Platform on your local machine or production server.

## Table of Contents

- [System Requirements](#system-requirements)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup Steps](#detailed-setup-steps)
- [Troubleshooting](#troubleshooting)
- [Post-Installation](#post-installation)

---

## System Requirements

### Hardware
- **CPU**: Dual-core or better
- **RAM**: 4 GB minimum, 8 GB recommended
- **Disk Space**: 10 GB minimum (includes database, Node modules, Python venv)
- **Internet**: Required for initial setup and live data fetching

### Operating Systems
- **Linux**: Ubuntu 20.04+, Debian 11+, or any distro with bash, Python 3.10+, and Docker support
- **macOS**: macOS 11+ (Intel or Apple Silicon)
- **Windows**: Windows 10/11 with PowerShell 5.0+ or Command Prompt

---

## Prerequisites

### 1. **Python 3.10 or Higher**

**Check if installed:**
```bash
python3 --version
# or
python --version
```

**Install:**
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt-get update
  sudo apt-get install python3.10 python3.10-venv python3-pip
  ```
  
- **macOS**:
  ```bash
  brew install python@3.10
  ```
  
- **Windows**:
  Download from [python.org](https://www.python.org/downloads/) and ensure "Add Python to PATH" is checked during installation.

### 2. **Node.js 18 or Higher (Required for Frontend)**

**Check if installed:**
```bash
node --version
npm --version
```

**Install:**
- **Linux**:
  ```bash
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
  ```
  
- **macOS**:
  ```bash
  brew install node
  ```
  
- **Windows**:
  - Download from [nodejs.org](https://nodejs.org/) (LTS recommended)
  - Or use Windows Package Manager: `winget install OpenJS.NodeJS`

### 3. **Docker & Docker Compose** (Required if using Docker PostgreSQL)

**Check if installed:**
```bash
docker --version
docker compose version
```

**Install:**
- **Linux**: Follow [Docker official guide](https://docs.docker.com/engine/install/)
- **macOS**: [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Windows**: [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)

**Verify Docker is running:**
```bash
docker ps
```

### 4. **Git** (Optional but Recommended)

**Check if installed:**
```bash
git --version
```

**Install:**
- **Linux**: `sudo apt-get install git`
- **macOS**: `brew install git`
- **Windows**: [Git for Windows](https://git-scm.com/download/win)

### 5. **PostgreSQL Connection** (Choose One)

#### Option A: Docker PostgreSQL (Easiest)
- Docker Desktop must be running
- The setup script will start PostgreSQL 16 Alpine automatically

#### Option B: External PostgreSQL
- Existing PostgreSQL 13+ database
- Connection details: `postgresql://user:password@host:port/database`
- Ensure your network can reach the database

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/prp20/Nivesh-Platform.git
cd Nivesh-Platform
```

### 2. Run the Setup Script

#### **Linux / macOS**
```bash
chmod +x setup/setup.sh
./setup/setup.sh
```

#### **Windows (PowerShell — Recommended)**
```powershell
powershell -ExecutionPolicy RemoteSigned -File setup\setup.ps1
```

Or double-click `setup\setup.ps1` if you prefer.

#### **Windows (CMD)**
```cmd
setup\setup.bat
```

### 3. Follow Interactive Prompts
- Choose PostgreSQL: Docker (default) or External
- Seed data: Yes/No (mutual funds and stocks)
- Wait for API to start

### 4. Access the Application
- **Frontend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

---

## Detailed Setup Steps

### Step 1: Verify Prerequisites

Run this before executing the setup script to ensure all requirements are met:

```bash
# Python
python3 --version        # Should be 3.10+

# Node.js
node --version          # Should be 18+
npm --version

# Docker (if using Docker PostgreSQL)
docker --version
docker compose version
docker ps               # Verify daemon is running
```

### Step 2: Download/Clone the Project

```bash
# Via Git
git clone https://github.com/prp20/Nivesh-Platform.git
cd Nivesh-Platform

# Or download ZIP from GitHub
unzip Nivesh-Platform.zip
cd Nivesh-Platform
```

### Step 3: Run the Setup Script

**Linux / macOS:**
```bash
chmod +x setup/setup.sh
./setup/setup.sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy RemoteSigned -File setup\setup.ps1
```

**Windows (CMD):**
```cmd
setup\setup.bat
```

### Step 4: Answer Setup Questions

The script will ask:

#### **PostgreSQL Setup**
```
How do you want to connect to PostgreSQL?
[1] Docker - auto-managed, starts postgres:16-alpine (default)
[2] External - I will provide my own connection URL

Enter choice [1]:
```

- **[1] Docker** — Recommended for new users. The script handles everything.
- **[2] External** — If you have an existing PostgreSQL database:
  ```
  PostgreSQL URL: postgresql+asyncpg://user:password@host:port/dbname
  ```

#### **Data Seeding** (Optional — Takes 30–90 minutes)
```
Seed mutual fund data (benchmarks + funds + NAV history)? (y/N):
```

- **Yes** — Fetches live data from AMFI API, computes metrics
- **No** — Skip; database will be empty except for schema

```
Also seed stock master + 5y price history from yfinance? (y/N):
```

- **Yes** — Downloads 5 years of stock price data (~20–40 minutes)
- **No** — Skip; stock tables will be empty

### Step 5: Wait for Completion

The script will:
1. ✓ Create Python virtual environment
2. ✓ Install Python dependencies (including ta-lib)
3. ✓ Start Docker PostgreSQL (if chosen)
4. ✓ Create environment files (backend `.env`, frontend `.env` + `.env.production`)
5. ✓ Run database migrations (SQLAlchemy tables + Alembic stock tables)
6. ✓ (Optional) Seed data (MF data, stock master, 5y price history)
7. ✓ Install Node.js dependencies
8. ✓ Build React frontend (production build → `frontend/dist/`)
9. ✓ Start FastAPI server on http://localhost:8000 (serves frontend + API)

---

## Frontend Build & Environment

The setup script automatically builds the React frontend for production:
```bash
npm run build  # Output: frontend/dist/
```

The frontend is configured with **environment-driven API URLs** — no hardcoded hosts or ports.

### Frontend Environment Files

| File | Variable | Value | Usage |
|---|---|---|---|
| `.env.development` | `VITE_API_URL` | `http://localhost:8000/api/v1` | Dev mode only (npm run dev) |
| `.env.production` | `VITE_API_URL` | `/api/v1` | Production build (npm run build) |

- Development: Frontend dev server (5173) calls backend API (8000)
- Production: Backend serves frontend from `frontend/dist/` at `/`, API at `/api/v1`

---

## Configuration Files

After setup, verify these files exist:

### `backend/.env`
```bash
cat backend/.env
```

**Should contain:**
```
DATABASE_URL=postgresql+asyncpg://...
API_V1_STR=/api/v1
PROJECT_NAME=Nivesh API
ENABLE_AUTH=false
SECRET_KEY=<auto-generated>
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Frontend Environment Files

**`frontend/.env`** (base fallback)
```bash
cat frontend/.env
```
Output:
```
VITE_API_URL=/api/v1
```

**`frontend/.env.development`** (dev mode)
```bash
cat frontend/.env.development
```
Output:
```
VITE_API_URL=http://localhost:8000/api/v1
```

**`frontend/.env.production`** (production build)
```bash
cat frontend/.env.production
```
Output:
```
VITE_API_URL=/api/v1
```

All three files are created automatically by the setup script. The environment-driven configuration ensures **no hardcoded URLs** in the frontend code.

---

## Starting the Application

### After Initial Setup

If the setup script completed successfully, the API is already running. Access:
- Frontend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Manual Start (If Needed)

```bash
# Start Docker PostgreSQL (if using Docker)
docker compose -f backend/docker-compose.yml up -d postgres

# Activate Python venv
cd backend
source venv/bin/activate          # Linux/macOS
# or
venv\Scripts\activate.bat          # Windows CMD
# or
.\venv\Scripts\Activate.ps1        # Windows PowerShell

# Start API server
uvicorn app.main:app --reload --port 8000
```

### Access the API

```bash
# Health check
curl http://localhost:8000/api/health

# Get API docs
curl http://localhost:8000/docs
```

---

## Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Example | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@localhost:5432/nivesh` | PostgreSQL connection string |
| `API_V1_STR` | `/api/v1` | API endpoint prefix |
| `PROJECT_NAME` | `Nivesh API` | Application name |
| `ENABLE_AUTH` | `false` | Enable JWT authentication (set `true` for production) |
| `SECRET_KEY` | `<auto-generated>` | JWT signing key (change in production) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT token lifetime |
| `ALPHA_VANTAGE_APIKEY` | (optional) | Stock price API key (future use) |
| `SUPABASE_PASSWORD` | (optional) | Supabase credentials (future use) |

### Frontend (`frontend/.env`)

| Variable | Example | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `/api/v1` | Backend API base URL (same origin in production) |

---

## Troubleshooting

### Python 3.10+ Not Found

**Error:**
```
python3 not found. Install Python 3.10+ and try again.
```

**Solution:**
```bash
# Check installed Python
python --version
python3 --version

# Install Python 3.10+
# Ubuntu/Debian
sudo apt-get install python3.10

# macOS
brew install python@3.10

# Windows
Download from https://python.org and add to PATH
```

### Node.js Not Found

**Error:**
```
Node.js not found. Frontend dev server will not be available.
```

**Solution:**
```bash
# Install Node.js 18+
# Linux
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install nodejs

# macOS
brew install node

# Windows
winget install OpenJS.NodeJS
# or download from https://nodejs.org
```

### Docker Not Running

**Error:**
```
Docker daemon is not running. Start Docker Desktop and try again.
```

**Solution:**
- **macOS/Windows**: Open Docker Desktop application
- **Linux**: Start Docker daemon:
  ```bash
  sudo systemctl start docker
  ```

### PostgreSQL Connection Failed

**Error:**
```
PostgreSQL did not become ready after 30 seconds.
```

**Solution:**
```bash
# Check Docker PostgreSQL logs
docker compose -f backend/docker-compose.yml logs postgres

# Restart PostgreSQL
docker compose -f backend/docker-compose.yml down postgres
docker compose -f backend/docker-compose.yml up -d postgres
```

### Port 8000 Already in Use

**Error:**
```
Address already in use
```

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000              # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill the process or use a different port
NIVESH_PORT=8001 uvicorn app.main:app --reload
```

### npm Install Fails

**Error:**
```
npm ERR! peer dep missing
```

**Solution:**
```bash
cd frontend
npm install --legacy-peer-deps
```

### ta-lib Compilation Fails (Linux)

**Error:**
```
fatal error: ta-lib/ta_libc.h: No such file or directory
```

**Solution:**
```bash
# Install pre-built ta-lib
sudo apt-get install libta-lib-dev libta-lib0

# OR compile from source
cd ta-lib
./configure
make
sudo make install
sudo ldconfig

# Then reinstall Python package
pip install --force-reinstall TA-Lib
```

### Frontend Build Fails

**Error:**
```
npm run build failed
```

**Solution:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install --legacy-peer-deps
npm run build
```

### Permission Denied on setup.sh

**Error:**
```
Permission denied: ./setup.sh
```

**Solution:**
```bash
chmod +x setup/setup.sh
./setup/setup.sh
```

---

## Post-Installation

### 1. Verify Installation

```bash
# Check API health
curl http://localhost:8000/api/health
# Expected: {"message": "Nivesh API", "status": "running", "documentation": "/docs"}

# Check API docs
curl -s http://localhost:8000/docs | head -20
```

### 2. Review Configuration

```bash
# Backend config
cat backend/.env

# Frontend config
cat frontend/.env

# Database schema
psql postgresql://user:pass@localhost:5432/nivesh -c "\dt"
```

### 3. Check Database Connectivity

```bash
# List tables
psql postgresql://user:pass@localhost:5432/nivesh -c "\dt"

# Count records (after seeding)
psql postgresql://user:pass@localhost:5432/nivesh -c "SELECT COUNT(*) FROM fund_master;"
```

### 4. Explore the Application

- **Frontend**: http://localhost:8000 — Browse mutual funds, stocks, screener
- **API Docs**: http://localhost:8000/docs — Swagger UI with all endpoints
- **Admin Panel**: http://localhost:8000/admin (if ENABLE_AUTH=false)

### 5. Read Developer Documentation

- **CLAUDE.md** — Development setup, coding conventions, debugging
- **API_REFERENCE.md** — All API endpoints with examples
- **DATABASE.md** — Database schema, table relationships
- **FRONTEND.md** — Frontend architecture, state management
- **WORKFLOW.md** — Development workflow, branching strategy

### 6. Configure for Production (Before Deployment)

Update `backend/.env`:
```bash
ENABLE_AUTH=true                          # Enable authentication
SECRET_KEY=<generate-a-long-random-key>   # Use `secrets.token_urlsafe(32)`
```

Update `frontend/.env`:
```bash
VITE_API_URL=https://your-domain.com/api/v1  # Point to production API
```

Rebuild frontend:
```bash
cd frontend
npm run build
```

---

## System Architecture After Installation

```
http://localhost:8000
│
├── Frontend (React 19)
│   └── Served by FastAPI from backend/dist/
│
└── Backend (FastAPI)
    ├── /api/v1/funds         → Mutual funds data
    ├── /api/v1/stocks        → Stock market data
    ├── /api/v1/screener      → Stock screener with filters
    ├── /api/v1/metrics       → Performance metrics
    ├── /docs                 → Swagger API docs
    └── Database (PostgreSQL)
        ├── Mutual Fund Tables (7)
        └── Stock Market Tables (9)
```

---

## Next Steps

1. **Explore the API**: Open http://localhost:8000/docs
2. **Check the Frontend**: Visit http://localhost:8000
3. **Read Development Guide**: See `CLAUDE.md` for developer setup
4. **Review Architecture**: See `OVERVIEW.md` for system design
5. **Start Development**: See `WORKFLOW.md` for branching and commit strategy

---

## Getting Help

- **Setup Issues**: Check [Troubleshooting](#troubleshooting) section above
- **API Documentation**: http://localhost:8000/docs
- **Source Code**: https://github.com/prp20/Nivesh-Platform
- **Issues**: File a GitHub issue with details of your setup and error logs

---

## Installation Summary Checklist

- [ ] Python 3.10+ installed and verified
- [ ] Node.js 18+ installed and verified
- [ ] Docker installed (if using Docker PostgreSQL)
- [ ] Repository cloned/downloaded
- [ ] Setup script executed (`setup.sh`, `setup.ps1`, or `setup.bat`)
- [ ] PostgreSQL selected (Docker or External)
- [ ] Data seeding completed (optional)
- [ ] Frontend built successfully
- [ ] API server running at http://localhost:8000
- [ ] Frontend accessible at http://localhost:8000
- [ ] API docs working at http://localhost:8000/docs
- [ ] Environment files verified (`backend/.env`, `frontend/.env`)
- [ ] Database connectivity confirmed

---

**Last Updated**: April 2026
**Supported Versions**: Python 3.10+, Node.js 18+, PostgreSQL 13+
