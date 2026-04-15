@echo off
:: =============================================================================
:: Nivesh Platform — Setup Script (Windows CMD / Batch)
:: =============================================================================
:: RECOMMENDED: Use setup.ps1 (PowerShell) instead for a better experience.
::
:: Usage: Double-click setup.bat or run from Command Prompt:
::   setup\setup.bat
::
:: Requirements:
::   - Python 3.10+    https://python.org
::   - Node.js 18+     https://nodejs.org    (optional, for frontend)
::   - Docker Desktop  https://docker.com    (only if using Docker PostgreSQL)
:: =============================================================================

setlocal enabledelayedexpansion

:: ─── Paths ───────────────────────────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
:: Normalise the path (remove trailing backslash quirks)
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "BACKEND_DIR=%PROJECT_ROOT%\backend"
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"
set "VENV_DIR=%BACKEND_DIR%\venv"
set "BACKEND_ENV_FILE=%BACKEND_DIR%\.env"
set "FRONTEND_ENV_FILE=%FRONTEND_DIR%\.env"
set "COMPOSE_FILE=%BACKEND_DIR%\docker-compose.yml"

echo.
echo   ==================================================
echo     Nivesh Platform -- Setup Script (Windows CMD)
echo   ==================================================
echo.
echo   NOTE: For a better experience with colour output
echo         and richer error handling, use setup.ps1:
echo         powershell -ExecutionPolicy RemoteSigned -File setup\setup.ps1
echo.
echo   Project root: %PROJECT_ROOT%
echo.

:: =============================================================================
:: STEP 1 — Check Python and Install if missing
:: =============================================================================
echo [STEP 1] Checking Python...

python --version >nul 2>&1
if errorlevel 1 (
  echo [WARN] 'python' command not found. Attempting to install Python via winget...
  winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo [ERROR] Failed to install Python. Please install Python 3.10+ manually.
    pause
    exit /b 1
  )
  echo [OK] Python installed. Please restart this command prompt for PATH changes to take effect.
) else (
  for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
  echo [OK]    Python !PY_VER! detected.
)

:: Basic version check (major.minor >= 3.10)
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.10+ is required.
  pause
  exit /b 1
)

:: =============================================================================
:: STEP 2 — Check Nodejs and Install if missing
:: =============================================================================
echo.
echo [STEP 2] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
  echo [WARN] Node.js not found. Attempting to install Node.js via winget...
  winget install OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo [ERROR] Failed to install Node.js. Please install manually.
    pause
    exit /b 1
  )
  echo [OK] Node.js installed.
) else (
  for /f %%v in ('node --version 2^>^&1') do echo [OK]    Node.js %%v detected.
  for /f %%v in ('npm --version 2^>^&1') do echo [OK]    npm %%v detected.
)

:: =============================================================================
:: STEP 3 — PostgreSQL setup
:: =============================================================================
echo.
echo [STEP 3] PostgreSQL Setup
echo.
echo   How do you want to connect to PostgreSQL?
echo   [1] Docker  -- auto-managed, starts postgres:16-alpine (default)
echo   [2] External -- I will provide my own connection URL
echo.
set /p PG_CHOICE="  Enter choice [1]: "
if "%PG_CHOICE%"=="" set PG_CHOICE=1

set USE_DOCKER=0
if "%PG_CHOICE%"=="2" (
  echo.
  echo   Enter the PostgreSQL URL in this format:
  echo   postgresql+asyncpg://user:password@host:port/dbname
  echo.
  set /p DATABASE_URL="  PostgreSQL URL: "
  if "!DATABASE_URL!"=="" (
    echo [ERROR] No URL entered. Aborting.
    pause
    exit /b 1
  )
  echo [OK]    Using external PostgreSQL URL.
) else (
  set DATABASE_URL=postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db
  set USE_DOCKER=1
  echo [OK]    Will use Docker-managed PostgreSQL.

  docker --version >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Docker not found. Install Docker Desktop from https://docker.com
    echo         Or choose option [2] and provide an external PostgreSQL URL.
    pause
    exit /b 1
  )
)

:: =============================================================================
:: STEP 4 — Python virtual environment + dependencies
:: =============================================================================
echo.
echo [STEP 4] Python Virtual Environment
echo.

cd /d "%PROJECT_ROOT%"

if not exist "%VENV_DIR%" (
  echo [INFO]  Creating virtual environment at %VENV_DIR%...
  python -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
  echo [OK]    Virtual environment created.
) else (
  echo [INFO]  Virtual environment already exists.
)

echo [INFO]  Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] Failed to activate virtual environment.
  pause
  exit /b 1
)
echo [OK]    Virtual environment activated.

echo [INFO]  Upgrading pip...
pip install --upgrade pip --quiet

echo [INFO]  Installing Python dependencies (excluding ta-lib)...
findstr /v /i "TA-Lib" "%BACKEND_DIR%\requirements.txt" > "%TEMP%\req_temp.txt"
pip install -r "%TEMP%\req_temp.txt"
if errorlevel 1 (
  echo.
  echo [ERROR] pip install failed.
  pause
  exit /b 1
)
del "%TEMP%\req_temp.txt" /q
echo [OK]    Python dependencies installed.

:: =============================================================================
:: STEP 5 — Environment Configuration
:: =============================================================================
echo.
echo [STEP 5] Environment Configuration
echo.

:: Generate random SECRET_KEY (using timestamp + random number)
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set "SECRET_KEY=dev-secret-%mydate%-%mytime%-%RANDOM%"

:: Backend .env
set WRITE_BACKEND_ENV=1
if exist "%BACKEND_ENV_FILE%" (
  echo [WARN]  backend\.env already exists at %BACKEND_ENV_FILE%
  set /p OVERWRITE="  Overwrite it with the new configuration? (y/N): "
  if /i not "!OVERWRITE!"=="y" (
    echo [INFO]  Keeping existing backend\.env.
    set WRITE_BACKEND_ENV=0
  )
)

if "%WRITE_BACKEND_ENV%"=="1" (
  (
    echo # -- Database -----------------------------------------------------------------
    echo DATABASE_URL=!DATABASE_URL!
    echo.
    echo # -- API ----------------------------------------------------------------------
    echo API_V1_STR=/api/v1
    echo PROJECT_NAME=Nivesh API
    echo.
    echo # -- Security - CHANGE IN PRODUCTION ------------------------------------------
    echo ENABLE_AUTH=true
    echo SECRET_KEY=%SECRET_KEY%
    echo ACCESS_TOKEN_EXPIRE_MINUTES=30
    echo.
    echo # -- Admin portal credentials ^(set below^) -----------------------------------
    echo ADMIN_USERNAME=
    echo ADMIN_PASSWORD_HASH=
    echo.
    echo # -- Third-party APIs ^(if needed^) -------------------------------------------
    echo # ALPHA_VANTAGE_APIKEY=your_key_here
    echo # SUPABASE_PASSWORD=your_password_here
  ) > "%BACKEND_ENV_FILE%"
  echo [OK]    backend\.env written to %BACKEND_ENV_FILE%
)

:: ── Admin credentials ─────────────────────────────────────────────────────────
echo.
echo [INFO]  Set up your admin login credentials for the Nivesh portal.
echo.

:: Write a temporary Python helper to prompt for credentials and patch the .env
set "HELPER=%TEMP%\nivesh_admin_setup.py"

:: Disable delayed expansion just for writing the helper to avoid ! conflicts with !=
setlocal disabledelayedexpansion
del "%HELPER%" >nul 2>&1
echo import sys, getpass, re, os, datetime > "%HELPER%"
echo from passlib.context import CryptContext >> "%HELPER%"
echo from jose import jwt >> "%HELPER%"
echo env_file = sys.argv[1] >> "%HELPER%"
echo secret_key = sys.argv[2] >> "%HELPER%"
echo username = input("  Admin username [admin]: ").strip() or "admin" >> "%HELPER%"
echo while True: >> "%HELPER%"
echo     pw = getpass.getpass("  Admin password: ") >> "%HELPER%"
echo     if not pw: >> "%HELPER%"
echo         print("  [WARN] Password cannot be empty.") >> "%HELPER%"
echo         continue >> "%HELPER%"
echo     pw2 = getpass.getpass("  Confirm password: ") >> "%HELPER%"
echo     if pw != pw2: >> "%HELPER%"
echo         print("  [WARN] Passwords do not match.") >> "%HELPER%"
echo         continue >> "%HELPER%"
echo     break >> "%HELPER%"
echo hash_ = CryptContext(schemes=["bcrypt"], deprecated="auto").hash(pw) >> "%HELPER%"
echo content = open(env_file).read() >> "%HELPER%"
echo content = re.sub(r"ADMIN_USERNAME=.*", "ADMIN_USERNAME=" + username, content) >> "%HELPER%"
echo content = re.sub(r"ADMIN_PASSWORD_HASH=.*", "ADMIN_PASSWORD_HASH=" + hash_, content) >> "%HELPER%"
echo open(env_file, "w").write(content) >> "%HELPER%"
echo exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650) >> "%HELPER%"
echo token = jwt.encode({"sub": username, "exp": exp}, secret_key, algorithm="HS256") >> "%HELPER%"
echo open(sys.argv[3], "w").write(token) >> "%HELPER%"
echo print("[OK]    Admin credentials saved (username: " + username + ")") >> "%HELPER%"
endlocal

set "TOKEN_FILE=%TEMP%\admin_jwt_token.txt"
python "%HELPER%" "%BACKEND_ENV_FILE%" "%SECRET_KEY%" "%TOKEN_FILE%"
if errorlevel 1 (
  echo [ERROR] Failed to set admin credentials.
  del "%HELPER%" >nul 2>&1
  pause
  exit /b 1
)
set /p ADMIN_JWT_TOKEN=<"%TOKEN_FILE%"
del "%HELPER%" >nul 2>&1
del "%TOKEN_FILE%" >nul 2>&1

:: Frontend .env
set WRITE_FRONTEND_ENV=1
if exist "%FRONTEND_ENV_FILE%" (
  echo [WARN]  frontend\.env already exists at %FRONTEND_ENV_FILE%
  set /p OVERWRITE="  Overwrite it? (y/N): "
  if /i not "!OVERWRITE!"=="y" (
    echo [INFO]  Keeping existing frontend\.env.
    set WRITE_FRONTEND_ENV=0
  )
)

if "%WRITE_FRONTEND_ENV%"=="1" (
  (
    echo # -- API URL ------------------------------------------------------------------
    echo # For development: http://localhost:8000/api/v1
    echo # For production: /api/v1 (same origin -- backend serves frontend)
    echo VITE_API_URL=/api/v1
    echo.
    echo # -- API Bypass Token ----------------------------------------------------------
    echo # Embedded JWT token allowing frontend clients to bypass the standard login loop.
    echo VITE_API_TOKEN=!ADMIN_JWT_TOKEN!
  ) > "%FRONTEND_ENV_FILE%"
  echo [OK]    frontend\.env written to %FRONTEND_ENV_FILE%
)

:: =============================================================================
:: STEP 6 — Start Docker PostgreSQL (if chosen)
:: =============================================================================
echo.
if "%USE_DOCKER%"=="1" (
  echo [STEP 6] Starting Docker PostgreSQL
  echo.
  echo [INFO]  Starting PostgreSQL via Docker Compose...
  docker compose -f "%COMPOSE_FILE%" up -d postgres
  if errorlevel 1 (
    echo [ERROR] Failed to start Docker PostgreSQL. Is Docker Desktop running?
    pause
    exit /b 1
  )

  echo [INFO]  Waiting for PostgreSQL to become ready ^(up to 30s^)...
  set READY=0
  for /l %%i in (1,1,30) do (
    if "!READY!"=="0" (
      docker compose -f "%COMPOSE_FILE%" exec -T postgres pg_isready -U nivesh_admin -d nivesh_db >nul 2>&1
      if not errorlevel 1 (
        echo [OK]    PostgreSQL is ready.
        set READY=1
      ) else (
        timeout /t 1 /nobreak >nul
      )
    )
  )
  if "!READY!"=="0" (
    echo [ERROR] PostgreSQL did not become ready after 30 seconds.
    echo         Check: docker compose -f backend\docker-compose.yml logs postgres
    pause
    exit /b 1
  )
) else (
  echo [STEP 6] PostgreSQL (External -- skipping Docker)
  echo [INFO]  Using your external PostgreSQL. Ensure it is reachable.
)

:: =============================================================================
:: STEP 7 — Database Setup
:: =============================================================================
echo.
echo [STEP 7] Database Setup
echo.

cd /d "%BACKEND_DIR%"

echo [INFO]  Checking existing database state...
python scripts\db_setup.py --check
if errorlevel 1 goto :fresh_install

:: Tables exist — ask user what to do
echo.
echo [WARN]  Existing database tables detected.
echo.
echo   [1] Keep all data -- update schema only  ^(safe, recommended^)
echo   [2] Erase EVERYTHING and start fresh     ^(destructive, all data lost^)
echo.
set /p DB_ACTION="  Enter choice [1]: "
if "!DB_ACTION!"=="" set DB_ACTION=1
if not "!DB_ACTION!"=="2" goto :run_migrations

:: Confirm destructive drop
echo.
echo [WARN]  This will PERMANENTLY DELETE all data from the database.
set /p DROP_CONFIRM="  Type YES to confirm: "
if /i not "!DROP_CONFIRM!"=="YES" (
  echo [INFO]  Cancelled. Keeping existing data.
  goto :run_migrations
)

echo [INFO]  Dropping all tables...
python scripts\db_setup.py --drop-all
if errorlevel 1 (
  echo [ERROR] Failed to drop tables. Check database connectivity.
  pause
  exit /b 1
)
echo [OK]    All tables dropped.
goto :run_migrations

:fresh_install
echo [INFO]  No existing tables found. Fresh installation.

:run_migrations
echo [INFO]  Creating MF tables and enabling pg_trgm ^(SQLAlchemy create_all^)...
python scripts\db_init.py
if errorlevel 1 (
  echo [ERROR] db_init.py failed. Check database connectivity.
  pause
  exit /b 1
)
echo [OK]    MF tables ready.

echo [INFO]  Running Alembic migration for stock tables ^(idempotent^)...
"%VENV_DIR%\Scripts\alembic.exe" upgrade head
if errorlevel 1 (
  echo [ERROR] alembic upgrade head failed. Check database connectivity and alembic.ini.
  pause
  exit /b 1
)
echo [OK]    Stock tables ready.

:: =============================================================================
:: STEP 8 — Optional seeding
:: =============================================================================
echo.
echo [STEP 8] Data Seeding (Optional)
echo.
echo [WARN]  Seeding fetches live data from AMFI and yfinance -- this can take 30-90 minutes.
echo.
echo   What data would you like to seed?
echo   [1] Mutual Fund data only   ^(benchmarks + funds + NAV history,  30-60 min^)
echo   [2] Stock data only         ^(18 stocks + 5y price history,      20-40 min^)
echo   [3] Both                    ^(recommended for full platform,     50-100 min^)
echo   [4] Skip seeding            ^(run seed scripts manually later^)
echo.
set /p SEED_CHOICE="  Enter choice [4]: "
if "!SEED_CHOICE!"=="" set SEED_CHOICE=4

set SEED_MF=0
set SEED_STOCKS=0
if "!SEED_CHOICE!"=="1" set SEED_MF=1
if "!SEED_CHOICE!"=="2" set SEED_STOCKS=1
if "!SEED_CHOICE!"=="3" (
  set SEED_MF=1
  set SEED_STOCKS=1
)

if "!SEED_MF!"=="1" (
  echo [INFO]  Seeding benchmark indices...
  python scripts\seed_indices.py
  echo [OK]    Benchmark indices seeded.

  echo [INFO]  Seeding fund master records...
  python scripts\seed_funds.py
  echo [OK]    Fund master seeded.

  echo [INFO]  Fetching NAV history and computing metrics ^(30-60 minutes^)...
  python scripts\sync_data.py
  echo [OK]    Fund NAV history and metrics complete.
)

if "!SEED_STOCKS!"=="1" (
  echo [INFO]  Seeding stock master...
  python scripts\seed\seed_stock_master.py
  echo [OK]    Stock master seeded.

  echo [INFO]  Backfilling 5 years of price data ^(20-40 minutes^)...
  python scripts\seed\backfill_prices.py 5y
  echo [OK]    Stock price history backfilled.
)

:: =============================================================================
:: STEP 9 — Build frontend
:: =============================================================================
echo.
echo [STEP 9] Building Frontend
echo.

cd /d "%FRONTEND_DIR%"

echo [INFO]  Installing frontend dependencies ^(npm install^)...
call npm install --legacy-peer-deps
if errorlevel 1 (
  echo [ERROR] npm install failed. Check the error output above.
  pause
  exit /b 1
)
echo [OK]    Frontend dependencies installed.

echo [INFO]  Building frontend for production ^(npm run build^)...
call npm run build
if errorlevel 1 (
  echo [ERROR] npm run build failed. Check the error output above.
  pause
  exit /b 1
)
if not exist "%FRONTEND_DIR%\dist" (
  echo [ERROR] Frontend build directory not found at %FRONTEND_DIR%\dist
  pause
  exit /b 1
)
echo [OK]    Frontend built and ready at %FRONTEND_DIR%\dist

:: =============================================================================
:: STEP 10 — Install Ta-lib (Moved to last)
:: =============================================================================
echo.
echo [STEP 10] Install Ta-lib
echo.
echo   TA-Lib ^>= 0.6.8 includes pre-built Windows wheels.
echo   pip install will be attempted. If it fails, you have these options:
echo   A) Conda:  conda install -c conda-forge ta-lib
echo   B) WSL:    Run setup\setup.sh inside Windows Subsystem for Linux
echo.

pip install TA-Lib>=0.6.8
if errorlevel 1 (
  echo [ERROR] pip install TA-Lib failed.
  echo         Install it via conda: conda install -c conda-forge ta-lib
  echo         Then rerun this script.
  pause
  exit /b 1
)
echo [OK]    TA-Lib installed.

:: =============================================================================
:: STEP 11 — Start API server
:: =============================================================================
echo.
echo [STEP 11] Starting FastAPI Server
echo.
echo   Setup complete! Starting Nivesh API...
echo.
echo   Frontend + API  :  http://localhost:8000
echo   API docs        :  http://localhost:8000/docs
echo   Health          :  http://localhost:8000/api/health
echo.

cd /d "%BACKEND_DIR%"

if "%NIVESH_HOST%"=="" set NIVESH_HOST=0.0.0.0
if "%NIVESH_PORT%"=="" set NIVESH_PORT=8000

uvicorn app.main:app --host %NIVESH_HOST% --port %NIVESH_PORT% --reload --log-level info

endlocal