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
#   1.  Check Git
#   2.  Check Python 3.10+ (winget auto-install if missing)
#   3.  Check Node.js 18+ (winget auto-install if missing)
#   4.  Clone/Update repository
#   5.  PostgreSQL setup — Docker (auto) or external URL
#   6.  Python virtual environment + dependencies (excluding TA-Lib)
#   7.  Environment configuration + Admin JWT
#   8.  Start Docker PostgreSQL (if chosen)
#   9.  Database migrations
#   10. Optional data seeding
#   11. Frontend build
#   12. TA-Lib installation
#   13. Start FastAPI server
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

# Ensure Python output is unbuffered so tqdm bars and prints stream in real time
$env:PYTHONUNBUFFERED = "1"

# ─── Timed runner helpers ─────────────────────────────────────────────────────
function Start-TimedOp {
  param([string]$Label)
  $script:_op_label = $Label
  $script:_op_sw = [System.Diagnostics.Stopwatch]::StartNew()
  Write-Info "⏳ ${Label}...  (do not interrupt)"
}
function End-TimedOp {
  $script:_op_sw.Stop()
  $elapsed = [int]$script:_op_sw.Elapsed.TotalSeconds
  Write-Success "$($script:_op_label) — done in ${elapsed}s"
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
# STEP 0 — Check Git
# =============================================================================
Write-Step "Step 0: Checking Git"

if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVer = & git --version
    Write-Success "$gitVer detected."
} else {
    Write-Warn "Git not found. Attempting to install via winget..."
    & winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fatal "Failed to install Git. Please install Git from https://git-scm.com and re-run this script."
    }
    Write-Warn "Git installed. Please restart this PowerShell window for PATH changes to take effect, then re-run this script."
    exit 0
}

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
# STEP 2.5 — Clone Project Repository (Optional)
# =============================================================================
Write-Step "Step 2.5: Clone Project Repository"

$DoClone = Read-Host "  Do you want to clone or update the repository? (y/N)"
if ($DoClone -notmatch "^[Yy]$") {
    Write-Info "Skipping repository cloning/update."
} else {
    $RepoUrl = "https://github.com/prp20/Nivesh-Platform"
    $BranchName = Read-Host "    Enter branch to clone/update [main]"
    if ([string]::IsNullOrWhiteSpace($BranchName)) { $BranchName = "main" }

    # Define clone_repo BEFORE any branch that calls it
    function clone_repo {
        Write-Info "Cloning $RepoUrl (branch: $BranchName)..."
        & git clone -b $BranchName $RepoUrl nivesh-cloned
        if ($LASTEXITCODE -ne 0) { Write-Fatal "git clone failed. Check network and repo URL." }
        Set-Location nivesh-cloned
        $clonedRoot = (Get-Item .).FullName
        # Re-resolve all paths relative to the cloned directory
        $script:BackendDir      = Join-Path $clonedRoot "backend"
        $script:FrontendDir     = Join-Path $clonedRoot "frontend"
        $script:VenvDir         = Join-Path $script:BackendDir "venv"
        $script:BackendEnvFile  = Join-Path $script:BackendDir ".env"
        $script:FrontendEnvFile = Join-Path $script:FrontendDir ".env"
        Write-Success "Cloned successfully into nivesh-cloned."
    }

    $IsRepo = $false
    try {
      if (& git rev-parse --is-inside-work-tree 2>$null) { $IsRepo = $true }
    } catch {}

    if ($IsRepo) {
        $CurrentRemote = & git remote get-url origin 2>$null
        if ($CurrentRemote -like "*Nivesh-Platform*") {
            Write-Info "Already inside the Nivesh-Platform repository."
            $SwitchBranch = Read-Host "    Do you want to switch to/update branch '$BranchName'? (y/N)"
            if ($SwitchBranch -match "^[Yy]$") {
                & git fetch origin
                & git checkout $BranchName 2>$null
                if ($LASTEXITCODE -ne 0) {
                    & git checkout -b $BranchName "origin/$BranchName"
                }
                & git pull origin $BranchName
                Write-Success "Updated to $BranchName."
            }
        } else {
            # Already inside a different git repo — clone alongside
            clone_repo
        }
    } else {
        # Not inside any git repo — clone fresh
        clone_repo
    }
}

# =============================================================================
# STEP 3 — Python virtual environment + dependencies (excluding TA-Lib)
# =============================================================================
Write-Step "Step 3: Python Virtual Environment"

Set-Location $ProjectRoot

if (Test-Path $VenvDir) {
  Write-Warn "Virtual environment already exists at $VenvDir."
  $DeleteVenv = Read-Host "  Do you want to delete it and create a fresh one? (y/N)"
  if ($DeleteVenv -match "^[Yy]$") {
    Write-Info "Deleting existing virtual environment..."
    Remove-Item $VenvDir -Recurse -Force
    Write-Info "Creating virtual environment at $VenvDir ..."
    & $PythonCmd -m venv $VenvDir
    Write-Success "Virtual environment created."
  } else {
    Write-Info "Proceeding with existing virtual environment."
  }
} else {
  Write-Info "Creating virtual environment at $VenvDir ..."
  & $PythonCmd -m venv $VenvDir
  Write-Success "Virtual environment created."
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
  Write-Success "Python dependencies installed (TA-Lib excluded — installed in Step 9)."
} finally {
  Remove-Item $TempReq -Force -ErrorAction SilentlyContinue
}

# =============================================================================
# STEP 4 — Environment Configuration & Admin JWT
# =============================================================================
Write-Step "Step 4: Environment Configuration"

# ── PostgreSQL Setup ──────────────────────────────────────────────────────────
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
  Write-Host "  ── URL format examples ────────────────────────────────────────────────" -ForegroundColor White
  Write-Host "  Local / self-hosted PostgreSQL (port 5432):"
  Write-Host "    postgresql+asyncpg://user:password@localhost:5432/dbname"
  Write-Host ""
  Write-Host "  Supabase — use Session Pooler (port 6543, NOT 5432):" -ForegroundColor White
  Write-Host "    postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres"
  Write-Warn "asyncpg is NOT compatible with Supabase port 5432 (PgBouncer transaction mode)."
  Write-Warn "Always use port 6543 (Session Pooler) for Supabase."
  Write-Host "  ───────────────────────────────────────────────────────────────────────"
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

# Verify Docker if selected
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

# ── API Keys ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Enter your API keys (leave blank to skip)."
Write-Host ""
$GroqApiKey = Read-Host "  Enter GROQ_API_KEY"

$EnableLS = Read-Host "  Enable LangSmith tracing? (y/N)"
if ($EnableLS -match "^[Yy]$") {
    $LT_V2 = "true"
    $LangsmithApiKey = Read-Host "  Enter LANGSMITH_API_KEY"
} else {
    $LT_V2 = "false"
    $LangsmithApiKey = ""
}

# Generate cryptographically secure SECRET_KEY
$SecretKey = & $PythonCmd -c "import secrets; print(secrets.token_urlsafe(32))"
if ($LASTEXITCODE -ne 0 -or -not $SecretKey) {
  $SecretKey = [System.Web.Security.Membership]::GeneratePassword(32, 8)
  if (-not $SecretKey) {
    $SecretKey = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
  }
}

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
GROQ_API_KEY=$GroqApiKey
LANGCHAIN_TRACING_V2=$LT_V2
LANGCHAIN_PROJECT=Nivesh_platform
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_API_KEY=$LangsmithApiKey
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

$AdminHelperPath = Join-Path $ScriptDir "admin_helper.py"
# Use the venv Python explicitly — bcrypt is installed there, not in system Python
& "$VenvDir\Scripts\python.exe" $AdminHelperPath $BackendEnvFile
if ($LASTEXITCODE -ne 0) {
  Write-Fatal "Failed to set admin credentials. Check the output above."
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
# -- API URL ------------------------------------------------------------------
# For development: http://localhost:8000/api/v1  (set in .env.development)
# For production: /api/v1 (same origin -- backend serves frontend)
VITE_API_URL=/api/v1
"@
  Set-Content -Path $FrontendEnvFile -Value $FrontendEnvContent -Encoding UTF8
  Write-Success "frontend\.env written to $FrontendEnvFile"
}

# =============================================================================
# STEP 5 — Start Docker PostgreSQL (if chosen)
# =============================================================================
if ($UseDocker) {
  Write-Step "Step 5: Starting Docker PostgreSQL"
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
  Write-Step "Step 5: PostgreSQL (External — skipping Docker)"
  Write-Info "Using your external PostgreSQL. Ensure it is reachable."
}

# =============================================================================
# STEP 6 — Database Setup
# =============================================================================
Write-Step "Step 6: Database Setup"

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
# STEP 7 — Data Seeding (Optional)
# =============================================================================
Write-Step "Step 7: Data Seeding (Optional)"

Write-Host ""
Write-Warn "Seeding Master data from CSV is FAST (5 min). Syncing history takes 30-90 min."
Write-Host ""
Write-Host "  What data would you like to seed?"
Write-Host "  [1] Stocks (Master + 1y History)               (15-20 min)"
Write-Host "  [2] Mutual Funds (Master + NAV Sync)           (35-60 min)"
Write-Host "  [3] Master Data ONLY (Stocks + MF - CSVs)      (5-10 min)"
Write-Host "  [4] History Sync (All Master + 5y History)     (60-90 min)"
Write-Host "  [5] Full Production Sync (All + Fundamentals)  (70-110 min)"
Write-Host "  [6] Skip seeding"
Write-Host ""
$SeedChoice = Read-Host "  Enter choice [6]"
if ([string]::IsNullOrWhiteSpace($SeedChoice)) { $SeedChoice = "6" }

switch ($SeedChoice) {
  "1" {
    Start-TimedOp "Seeding Markets & Stocks (Master)"
    & $PythonCmd scripts\seed\seed_master_data.py stocks
    End-TimedOp
    
    Start-TimedOp "Backfilling Stock & Index Prices (1y)"
    & $PythonCmd scripts\seed\backfill_prices.py 1y
    End-TimedOp
  }
  "2" {
    Start-TimedOp "Seeding Markets & Mutual Funds (Master)"
    & $PythonCmd scripts\seed\seed_master_data.py funds
    End-TimedOp
    
    Write-Warn "Syncing NAV history (30-60 min). Do not interrupt."
    Start-TimedOp "Syncing NAV history"
    & $PythonCmd scripts\sync_data.py
    End-TimedOp
  }
  "3" {
    Start-TimedOp "Seeding All Master Data from CSV"
    & $PythonCmd scripts\seed\seed_master_data.py all
    End-TimedOp
  }
  "4" {
    Write-Info "Running History Sync (All Master + 5y History)."
    & $PythonCmd scripts\seed\seed_master_data.py all
    & $PythonCmd scripts\sync_data.py
    & $PythonCmd scripts\seed\backfill_prices.py 5y
    Write-Success "History sync complete."
  }
  "5" {
    Write-Info "Running Full Production Sync (All + Fundamentals)."
    & $PythonCmd scripts\seed\seed_master_data.py all
    & $PythonCmd scripts\sync_data.py
    & $PythonCmd scripts\seed\backfill_prices.py 5y
    & $PythonCmd scripts\seed\seed_fundamentals.py
    Write-Success "Full sync complete."
  }
  Default {
    Write-Info "Skipping seeding."
  }
}

# =============================================================================
# STEP 8 — Build frontend
# =============================================================================
Write-Step "Step 8: Building Frontend"

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
# STEP 9 — TA-Lib Installation
# =============================================================================
Write-Step "Step 9: TA-Lib Installation"

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

# Note: --reload is omitted for production. Add it manually for development hot-reload.
& uvicorn app.main:app --host $Host_ --port $Port --log-level info
