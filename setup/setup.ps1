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
#   1.  Check Python 3.10+ (winget auto-install if missing)
#   2.  Check Node.js 18+ (winget auto-install if missing)
#   3.  PostgreSQL setup — Docker (auto) or external URL
#   4.  Python virtual environment + dependencies (excluding TA-Lib)
#   5.  Environment configuration + Admin JWT
#   6.  Start Docker PostgreSQL (if chosen)
#   7.  Database migrations
#   8.  Optional data seeding
#   9.  Frontend build
#   10. TA-Lib installation
#   11. Start FastAPI server
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
# STEP 1 — Check Python
# =============================================================================
Write-Step "Step 1: Checking Python"

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
  Write-Warn "Python 3.10+ not found. Attempting to install via winget..."
  & winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    Write-Fatal "Failed to install Python. Please install Python 3.10+ from https://python.org and re-run this script."
  }
  Write-Warn "Python installed. Please restart this PowerShell window for PATH changes to take effect, then re-run this script."
  exit 0
}

# =============================================================================
# STEP 2 — Check Node.js
# =============================================================================
Write-Step "Step 2: Checking Node.js"

if (Get-Command node -ErrorAction SilentlyContinue) {
  $nodeVer = & node --version
  Write-Success "Node.js $nodeVer detected."
  $npmVer = & npm --version
  Write-Success "npm $npmVer detected."
} else {
  Write-Warn "Node.js not found. Attempting to install via winget..."
  & winget install OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    Write-Fatal "Failed to install Node.js. Please install Node.js 18+ from https://nodejs.org and re-run this script."
  }
  Write-Warn "Node.js installed. Please restart this PowerShell window for PATH changes to take effect, then re-run this script."
  exit 0
}

# =============================================================================
# STEP 3 — PostgreSQL setup
# =============================================================================
Write-Step "Step 3: PostgreSQL Setup"

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
# STEP 4 — Python virtual environment + dependencies (excluding TA-Lib)
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

Write-Info "Installing Python dependencies (excluding TA-Lib)..."
$ReqFile = Join-Path $BackendDir "requirements.txt"
$TempReq = [System.IO.Path]::GetTempFileName()
try {
  Get-Content $ReqFile | Where-Object { $_ -notmatch '(?i)ta.?lib' } | Set-Content $TempReq
  & pip install --prefer-binary -r $TempReq
  if ($LASTEXITCODE -ne 0) {
    Write-Fatal "pip install failed. Check the error output above."
  }
  Write-Success "Python dependencies installed (TA-Lib excluded — installed in Step 10)."
} finally {
  Remove-Item $TempReq -Force -ErrorAction SilentlyContinue
}

# =============================================================================
# STEP 5 — Environment Configuration & Admin JWT
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
# -- Database -----------------------------------------------------------------
DATABASE_URL=$DatabaseUrl

# -- API ----------------------------------------------------------------------
API_V1_STR=/api/v1
PROJECT_NAME=Nivesh API

# -- Security - CHANGE IN PRODUCTION ------------------------------------------
ENABLE_AUTH=true
SECRET_KEY=$SecretKey
ACCESS_TOKEN_EXPIRE_MINUTES=30

# -- Admin portal credentials (set below) -------------------------------------
ADMIN_USERNAME=
ADMIN_PASSWORD_HASH=

# -- Third-party APIs (if needed) --------------------------------------------
# ALPHA_VANTAGE_APIKEY=your_key_here
# SUPABASE_PASSWORD=your_password_here
"@
  Set-Content -Path $BackendEnvFile -Value $BackendEnvContent -Encoding UTF8
  Write-Success "backend\.env written to $BackendEnvFile"
}

# ── Admin credentials ─────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Set up your admin login credentials for the Nivesh portal."
Write-Host ""

$HelperPath = [System.IO.Path]::GetTempFileName() + ".py"
$TokenFile  = [System.IO.Path]::GetTempFileName()

$HelperScript = @'
import sys, getpass, re, os, datetime
import bcrypt as _bcrypt
from jose import jwt
env_file = sys.argv[1]
secret_key = sys.argv[2]
username = input("  Admin username [admin]: ").strip() or "admin"
while True:
    pw = getpass.getpass("  Admin password: ")
    if not pw:
        print("  [WARN] Password cannot be empty.")
        continue
    pw2 = getpass.getpass("  Confirm password: ")
    if pw != pw2:
        print("  [WARN] Passwords do not match.")
        continue
    break
hash_ = _bcrypt.hashpw(pw.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
content = open(env_file).read()
content = re.sub(r"ADMIN_USERNAME=.*", "ADMIN_USERNAME=" + username, content)
content = re.sub(r"ADMIN_PASSWORD_HASH=.*", "ADMIN_PASSWORD_HASH=" + hash_, content)
open(env_file, "w").write(content)
exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
token = jwt.encode({"sub": username, "exp": exp}, secret_key, algorithm="HS256")
open(sys.argv[3], "w").write(token)
print("[OK]    Admin credentials saved (username: " + username + ")")
'@

Set-Content -Path $HelperPath -Value $HelperScript -Encoding UTF8

& $PythonCmd $HelperPath $BackendEnvFile $SecretKey $TokenFile
if ($LASTEXITCODE -ne 0) {
  Remove-Item $HelperPath -Force -ErrorAction SilentlyContinue
  Remove-Item $TokenFile  -Force -ErrorAction SilentlyContinue
  Write-Fatal "Failed to set admin credentials."
}
$AdminJwtToken = Get-Content $TokenFile -Raw
Remove-Item $HelperPath -Force -ErrorAction SilentlyContinue
Remove-Item $TokenFile  -Force -ErrorAction SilentlyContinue

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
# -- API URL ------------------------------------------------------------------
# For development: http://localhost:8000/api/v1
# For production: /api/v1 (same origin -- backend serves frontend)
VITE_API_URL=/api/v1

# -- API Bypass Token ----------------------------------------------------------
# Embedded JWT token allowing frontend clients to bypass the standard login loop.
VITE_API_TOKEN=$AdminJwtToken
"@
  Set-Content -Path $FrontendEnvFile -Value $FrontendEnvContent -Encoding UTF8
  Write-Success "frontend\.env written to $FrontendEnvFile"
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
# STEP 7 — Database Setup
# =============================================================================
Write-Step "Step 7: Database Setup"

Set-Location $BackendDir

Write-Info "Checking existing database state..."
& $PythonCmd scripts\db_setup.py --check 2>$null
$TablesExist = ($LASTEXITCODE -eq 0)

if ($TablesExist) {
  Write-Host ""
  Write-Warn "Existing database tables detected."
  Write-Host ""
  Write-Host "  [1] Keep all data -- update schema only  (safe, recommended)"
  Write-Host "  [2] Erase EVERYTHING and start fresh     (destructive, all data lost)"
  Write-Host ""
  $DbAction = Read-Host "  Enter choice [1]"
  if ([string]::IsNullOrWhiteSpace($DbAction)) { $DbAction = "1" }

  if ($DbAction -eq "2") {
    Write-Host ""
    Write-Warn "This will PERMANENTLY DELETE all data in the database."
    $DropConfirm = Read-Host "  Type YES to confirm"
    if ($DropConfirm -eq "YES") {
      Write-Info "Dropping all tables..."
      & $PythonCmd scripts\db_setup.py --drop-all
      if ($LASTEXITCODE -ne 0) { Write-Fatal "Failed to drop tables. Check database connectivity." }
      Write-Success "All tables dropped."
    } else {
      Write-Info "Cancelled. Keeping existing data."
    }
  }
} else {
  Write-Info "No existing tables found. Fresh installation."
}

Write-Info "Creating MF tables and enabling pg_trgm (SQLAlchemy create_all)..."
& $PythonCmd scripts\db_init.py
if ($LASTEXITCODE -ne 0) { Write-Fatal "db_init.py failed. Check database connectivity." }
Write-Success "MF tables ready."

Write-Info "Running Alembic migration for stock tables (idempotent)..."
& "$VenvDir\Scripts\alembic" upgrade head
if ($LASTEXITCODE -ne 0) { Write-Fatal "alembic upgrade head failed. Check database connectivity and alembic.ini." }
Write-Success "Stock tables ready."

# =============================================================================
# STEP 8 — Optional seeding
# =============================================================================
Write-Step "Step 8: Data Seeding (Optional)"

Write-Host ""
Write-Warn "Seeding fetches live data from AMFI and yfinance — this can take 30-90 minutes."
Write-Host ""
Write-Host "  What data would you like to seed?"
Write-Host "  [1] Mutual Fund data only   (benchmarks + funds + NAV history,  30-60 min)"
Write-Host "  [2] Stock data only         (18 stocks + 5y price history,      20-40 min)"
Write-Host "  [3] Both                    (recommended for full platform,     50-100 min)"
Write-Host "  [4] Skip seeding            (run seed scripts manually later)"
Write-Host ""
$SeedChoice = Read-Host "  Enter choice [4]"
if ([string]::IsNullOrWhiteSpace($SeedChoice)) { $SeedChoice = "4" }

$SeedMf     = $SeedChoice -eq "1" -or $SeedChoice -eq "3"
$SeedStocks = $SeedChoice -eq "2" -or $SeedChoice -eq "3"

if (-not ($SeedMf -or $SeedStocks)) {
  Write-Info "Skipping seeding."
}

if ($SeedMf) {
  Write-Info "Seeding benchmark indices from CSV files..."
  & $PythonCmd scripts\seed_indices.py
  Write-Success "Benchmark indices seeded."

  Write-Info "Seeding fund master records..."
  & $PythonCmd scripts\seed_funds.py
  Write-Success "Fund master seeded."

  Write-Info "Fetching NAV history and computing metrics (30-60 minutes)..."
  & $PythonCmd scripts\sync_data.py
  Write-Success "Fund NAV history and metrics complete."
}

if ($SeedStocks) {
  Write-Info "Seeding stock master (18 large-cap stocks + 3 indices)..."
  & $PythonCmd scripts\seed\seed_stock_master.py
  Write-Success "Stock master seeded."

  Write-Info "Backfilling 5 years of price data from yfinance (20-40 minutes)..."
  & $PythonCmd scripts\seed\backfill_prices.py 5y
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
# STEP 10 — TA-Lib Installation
# =============================================================================
Write-Step "Step 10: TA-Lib Installation"

Write-Info "TA-Lib >= 0.6.8 includes pre-built Windows wheels — attempting pip install..."
Write-Host ""

Set-Location $BackendDir

& pip install "TA-Lib>=0.6.8"
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Warn "pip install TA-Lib failed. You have these options:"
  Write-Host "  A) Conda (recommended for Windows):"
  Write-Host "       conda install -c conda-forge ta-lib"
  Write-Host "  B) WSL (Windows Subsystem for Linux):"
  Write-Host "       Run setup\setup.sh inside WSL with Ubuntu"
  Write-Fatal "TA-Lib installation failed. Install it manually and re-run this script."
}
Write-Success "TA-Lib installed."

# =============================================================================
# STEP 11 — Start API server
# =============================================================================
Write-Step "Step 11: Starting FastAPI Server"

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
