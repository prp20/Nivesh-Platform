# =============================================================================
# Nivesh Platform — Setup Script (Windows PowerShell)
# =============================================================================
# Usage (run from project root in PowerShell):
#   .\setup\setup.ps1
#
# If you get "running scripts is disabled", run this once as Administrator:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#
# What this script does:
#   1. Checks prerequisites (Python 3.10+, Node.js, Docker)
#   2. Prompts for PostgreSQL: Docker (auto) or external URL
#   3. Attempts ta-lib install (pre-built wheel); shows fallback instructions if it fails
#   4. Creates Python virtual environment and installs dependencies
#   5. Writes backend\.env
#   6. Runs database migrations
#   7. Optionally seeds data
#   8. Starts the FastAPI server
# =============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

# ─── Colour helpers ──────────────────────────────────────────────────────────
function Write-Info    { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host "[OK]    $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Step    { param($msg) Write-Host "`n══ $msg ══`n" -ForegroundColor Cyan }
function Write-Fatal   {
  param($msg)
  Write-Host "[ERROR] $msg" -ForegroundColor Red
  exit 1
}

# ─── Resolve paths ───────────────────────────────────────────────────────────
$ScriptDir      = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot    = Split-Path -Parent $ScriptDir
$BackendDir     = Join-Path $ProjectRoot "backend"
$FrontendDir    = Join-Path $ProjectRoot "frontend"
$VenvDir        = Join-Path $BackendDir "venv"
$BackendEnvFile = Join-Path $BackendDir ".env"
$FrontendEnvFile= Join-Path $FrontendDir ".env"

Write-Host ""
Write-Host "  ╔═══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║     Nivesh Platform — Setup Script    ║" -ForegroundColor Cyan
Write-Host "  ╚═══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Info "Project root : $ProjectRoot"

# =============================================================================
# STEP 1 — Check prerequisites
# =============================================================================
Write-Step "Step 1: Checking Prerequisites"

# Python
$PythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
  if (Get-Command $cmd -ErrorAction SilentlyContinue) {
    $ver = & $cmd --version 2>&1
    if ($ver -match "Python (\d+)\.(\d+)") {
      $major = [int]$Matches[1]
      $minor = [int]$Matches[2]
      if ($major -ge 3 -and $minor -ge 10) {
        $PythonCmd = $cmd
        Write-Success "Python $major.$minor detected (command: $cmd)."
        break
      }
    }
  }
}
if (-not $PythonCmd) {
  Write-Fatal "Python 3.10+ not found. Download from https://python.org and ensure it is in PATH."
}

# Node.js
if (Get-Command node -ErrorAction SilentlyContinue) {
  $nodeVer = & node --version
  Write-Success "Node.js $nodeVer detected."
  $npmVer = & npm --version
  Write-Success "npm $npmVer detected."
} else {
  Write-Warn "Node.js not found."
  Write-Warn "Install Node.js 18+ LTS from https://nodejs.org"
  Write-Warn "Or use Windows Package Manager: winget install OpenJS.NodeJS"
  Write-Warn "After installing Node.js, please restart this script."
  Write-Fatal "Node.js is required for frontend setup."
}

# =============================================================================
# STEP 2 — PostgreSQL setup
# =============================================================================
Write-Step "Step 2: PostgreSQL Setup"

Write-Host ""
Write-Host "  How do you want to connect to PostgreSQL?" -ForegroundColor White
Write-Host "  [1] Docker  — auto-managed, starts postgres:16-alpine (default)"
Write-Host "  [2] External — I will provide my own connection URL"
Write-Host ""
$PgChoice = Read-Host "  Enter choice [1]"
if ([string]::IsNullOrWhiteSpace($PgChoice)) { $PgChoice = "1" }

$UseDocker = $false
$DatabaseUrl = ""

if ($PgChoice -eq "2") {
  Write-Host ""
  Write-Host "  Enter the PostgreSQL URL in this format:" -ForegroundColor White
  Write-Host "  postgresql+asyncpg://user:password@host:port/dbname"
  Write-Host ""
  $DatabaseUrl = Read-Host "  PostgreSQL URL"
  if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    Write-Fatal "No URL entered. Aborting."
  }
  if (-not $DatabaseUrl.StartsWith("postgresql")) {
    Write-Fatal "URL must start with 'postgresql'. Got: $DatabaseUrl"
  }
  Write-Success "Using external PostgreSQL URL."
} else {
  $DatabaseUrl = "postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db"
  $UseDocker = $true
  Write-Success "Will use Docker-managed PostgreSQL."
}

# Verify Docker if needed
if ($UseDocker) {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fatal "Docker not found. Install Docker Desktop from https://docker.com, or choose option [2] for an external PostgreSQL URL."
  }
  try {
    & docker info 2>&1 | Out-Null
    Write-Success "Docker is available."
  } catch {
    Write-Fatal "Docker daemon is not running. Start Docker Desktop and try again."
  }
}

# =============================================================================
# STEP 3 — ta-lib
# =============================================================================
Write-Step "Step 3: ta-lib (Technical Analysis Library)"

Write-Info "Attempting to install TA-Lib Python wheel..."
Write-Info "Note: TA-Lib >= 0.6.8 includes pre-built Windows wheels — this may succeed without extra steps."
Write-Host ""

# We'll try pip install after creating the venv. Just note the fallback here.
Write-Warn "If pip install fails for TA-Lib, you have these options:"
Write-Host "  A) Conda (recommended for Windows):"
Write-Host "       conda install -c conda-forge ta-lib"
Write-Host "  B) WSL (Windows Subsystem for Linux):"
Write-Host "       Run this script inside WSL with Ubuntu"
Write-Host "  C) Pre-built wheel from unofficial sources (use at your own risk)"
Write-Host ""

# =============================================================================
# STEP 4 — Python virtual environment + dependencies
# =============================================================================
Write-Step "Step 4: Python Virtual Environment"

Set-Location $ProjectRoot

if (-not (Test-Path $VenvDir)) {
  Write-Info "Creating virtual environment at $VenvDir ..."
  & $PythonCmd -m venv $VenvDir
  Write-Success "Virtual environment created."
} else {
  Write-Info "Virtual environment already exists at $VenvDir."
}

$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
  Write-Fatal "Virtual environment activation script not found: $ActivateScript"
}
. $ActivateScript
Write-Success "Virtual environment activated."

Write-Info "Upgrading pip..."
& pip install --upgrade pip --quiet

Write-Info "Installing Python dependencies from requirements.txt..."
$ReqFile = Join-Path $BackendDir "requirements.txt"
try {
  & pip install -r $ReqFile
  Write-Success "Python dependencies installed."
} catch {
  Write-Host ""
  Write-Warn "pip install encountered an error."
  Write-Warn "If the error is about TA-Lib, install it via conda first:"
  Write-Warn "  conda install -c conda-forge ta-lib"
  Write-Warn "Then rerun this script with --skip-deps or install remaining deps manually."
  Write-Fatal "Dependency installation failed. See above for details."
}

# =============================================================================
# STEP 5 — Write backend\.env
# =============================================================================
Write-Step "Step 5: Environment Configuration"

# Generate random SECRET_KEY
$SecretKey = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((Get-Random -Minimum 100000000 -Maximum 999999999).ToString() + (Get-Date).Ticks))

# Backend .env
$WriteBackendEnv = $true
if (Test-Path $BackendEnvFile) {
  Write-Warn "backend\.env already exists at $BackendEnvFile"
  $Overwrite = Read-Host "  Overwrite it with the new configuration? (y/N)"
  if ($Overwrite -notmatch "^[Yy]$") {
    Write-Info "Keeping existing backend\.env."
    $WriteBackendEnv = $false
  }
}

if ($WriteBackendEnv) {
  $BackendEnvContent = @"
# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=$DatabaseUrl

# ── API ───────────────────────────────────────────────────────────────────────
API_V1_STR=/api/v1
PROJECT_NAME=Nivesh API

# ── Security — CHANGE IN PRODUCTION ──────────────────────────────────────────
ENABLE_AUTH=false
SECRET_KEY=$SecretKey
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ── Third-party APIs (if needed) ──────────────────────────────────────────────
# ALPHA_VANTAGE_APIKEY=your_key_here
# SUPABASE_PASSWORD=your_password_here
"@
  Set-Content -Path $BackendEnvFile -Value $BackendEnvContent -Encoding UTF8
  Write-Success "backend\.env written with generated SECRET_KEY"
}

# Frontend .env
$WriteFrontendEnv = $true
if (Test-Path $FrontendEnvFile) {
  Write-Warn "frontend\.env already exists at $FrontendEnvFile"
  $Overwrite = Read-Host "  Overwrite it? (y/N)"
  if ($Overwrite -notmatch "^[Yy]$") {
    Write-Info "Keeping existing frontend\.env."
    $WriteFrontendEnv = $false
  }
}

if ($WriteFrontendEnv) {
  $FrontendEnvContent = @"
# ── API URL ──────────────────────────────────────────────────────────────────
# For development: http://localhost:8000/api/v1
# For production: /api/v1 (same origin — backend serves frontend)
VITE_API_URL=/api/v1
"@
  Set-Content -Path $FrontendEnvFile -Value $FrontendEnvContent -Encoding UTF8
  Write-Success "frontend\.env written"
}

$BackendEnvContents = Get-Content $BackendEnvFile -Raw
if ($BackendEnvContents -match "ENABLE_AUTH=false") {
  Write-Warn "ENABLE_AUTH=false — write endpoints are unprotected. Set to true for production."
}

# =============================================================================
# STEP 6 — Start Docker PostgreSQL (if chosen)
# =============================================================================
if ($UseDocker) {
  Write-Step "Step 6: Starting Docker PostgreSQL"
  $ComposeFile = Join-Path $BackendDir "docker-compose.yml"

  Write-Info "Starting PostgreSQL container via Docker Compose..."
  & docker compose -f $ComposeFile up -d postgres

  Write-Info "Waiting for PostgreSQL to become ready (up to 30s)..."
  $Ready = $false
  for ($i = 1; $i -le 30; $i++) {
    $result = & docker compose -f $ComposeFile exec -T postgres pg_isready -U nivesh_admin -d nivesh_db 2>&1
    if ($LASTEXITCODE -eq 0) {
      Write-Success "PostgreSQL is ready."
      $Ready = $true
      break
    }
    Start-Sleep -Seconds 1
  }
  if (-not $Ready) {
    Write-Fatal "PostgreSQL did not become ready after 30 seconds. Check: docker compose -f backend\docker-compose.yml logs postgres"
  }
} else {
  Write-Step "Step 6: PostgreSQL (External — skipping Docker)"
  Write-Info "Using your external PostgreSQL. Ensure it is reachable."
}

# =============================================================================
# STEP 7 — Database migrations
# =============================================================================
Write-Step "Step 7: Database Migrations"

Set-Location $BackendDir

Write-Info "Creating MF tables (SQLAlchemy create_all)..."
& python scripts\db_init.py
Write-Success "MF tables created."

Write-Info "Running Alembic migration for stock tables..."
& alembic upgrade head
Write-Success "Stock tables migrated."

# =============================================================================
# STEP 8 — Optional seeding
# =============================================================================
Write-Step "Step 8: Data Seeding (Optional)"

Write-Host ""
Write-Warn "Seeding fetches live data from AMFI and yfinance — this can take 30–90 minutes."
Write-Host ""
$SeedMf = Read-Host "  Seed mutual fund data (benchmarks + funds + NAV history)? (y/N)"

if ($SeedMf -match "^[Yy]$") {
  Write-Info "Seeding benchmark indices from CSV files..."
  & python scripts\seed_indices.py
  Write-Success "Benchmark indices seeded."

  Write-Info "Seeding fund master records..."
  & python scripts\seed_funds.py
  Write-Success "Fund master seeded."

  Write-Info "Fetching NAV history and computing metrics (30–60 minutes)..."
  & python scripts\sync_data.py
  Write-Success "Fund NAV history and metrics complete."
}

Write-Host ""
$SeedStocks = Read-Host "  Also seed stock master + 5y price history from yfinance? (y/N)"

if ($SeedStocks -match "^[Yy]$") {
  Write-Info "Seeding stock master (18 large-cap stocks + 3 indices)..."
  & python scripts\seed\seed_stock_master.py
  Write-Success "Stock master seeded."

  Write-Info "Backfilling 5 years of price data from yfinance (20–40 minutes)..."
  & python scripts\seed\backfill_prices.py 5y
  Write-Success "Stock price history backfilled."
}

# =============================================================================
# STEP 9 — Build frontend
# =============================================================================
Write-Step "Step 9: Building Frontend"

Set-Location $FrontendDir

Write-Info "Installing frontend dependencies (npm install)..."
& npm install --legacy-peer-deps
if ($LASTEXITCODE -ne 0) {
  Write-Fatal "npm install failed. Check the error output above."
}
Write-Success "Frontend dependencies installed."

Write-Info "Building frontend for production (npm run build)..."
& npm run build
if ($LASTEXITCODE -ne 0) {
  Write-Fatal "npm run build failed. Check the error output above."
}
$DistDir = Join-Path $FrontendDir "dist"
if (-not (Test-Path $DistDir)) {
  Write-Fatal "Frontend build directory not found at $DistDir"
}
Write-Success "Frontend built and ready at $DistDir"

# =============================================================================
# STEP 10 — Start API server
# =============================================================================
Write-Step "Step 10: Starting FastAPI Server"

Write-Host ""
Write-Host "  Setup complete! Starting Nivesh API..." -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend + API  :  http://localhost:8000" -ForegroundColor Green
Write-Host "  API docs        :  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Health          :  http://localhost:8000/api/health" -ForegroundColor Green
Write-Host ""

Set-Location $BackendDir

$Host_ = if ($env:NIVESH_HOST) { $env:NIVESH_HOST } else { "0.0.0.0" }
$Port  = if ($env:NIVESH_PORT) { $env:NIVESH_PORT } else { "8000" }

& uvicorn app.main:app --host $Host_ --port $Port --reload --log-level info
