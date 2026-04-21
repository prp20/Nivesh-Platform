@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
set "BACKEND_DIR=%PROJECT_ROOT%\backend"
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"
set "COMPOSE_FILE=%BACKEND_DIR%\docker-compose.yml"

echo ==================================================
echo   Nivesh Platform -- Teardown Script (Windows)
echo ==================================================
echo.
echo WARNING: This script will DESTROY the local environment,
echo databases, virtual environments, and generated files.
echo.
set /p CONFIRM="Are you sure you want to proceed? (y/N): "
if /i not "%CONFIRM%"=="y" (
    echo Teardown cancelled.
    exit /b 0
)

echo.
echo [1/5] Stopping Servers...
taskkill /F /IM uvicorn.exe >nul 2>&1
if errorlevel 0 (echo   Killed uvicorn API server.) else (echo   No uvicorn processes found.)
taskkill /F /IM node.exe >nul 2>&1
if errorlevel 0 (echo   Killed node servers.) else (echo   No node processes found.)

echo.
echo [2/5] Database Teardown...
if exist "%COMPOSE_FILE%" (
    set /p DEL_DB="Do you want to stop and DELETE the Docker PostgreSQL volumes? (y/N): "
    if /i "!DEL_DB!"=="y" (
        echo   Running docker compose down -v...
        docker compose -f "%COMPOSE_FILE%" down -v
        echo   Docker DB destroyed.
    ) else (
        echo   Skipping Docker teardown.
    )
) else (
    echo   No docker-compose.yml found. Skipping Docker DB teardown.
)

echo.
echo [3/5] Environment Cleanup...
if exist "%BACKEND_DIR%\venv" (
    echo   Removing backend virtual environment...
    rmdir /S /Q "%BACKEND_DIR%\venv"
)
if exist "%FRONTEND_DIR%\node_modules" (
    echo   Removing frontend node_modules...
    rmdir /S /Q "%FRONTEND_DIR%\node_modules"
)
if exist "%FRONTEND_DIR%\dist" (
    echo   Removing frontend dist...
    rmdir /S /Q "%FRONTEND_DIR%\dist"
)

echo.
echo [4/5] Configuration Cleanup...
if exist "%BACKEND_DIR%\.env" (
    del /f /q "%BACKEND_DIR%\.env"
    echo   Deleted backend\.env
)
if exist "%FRONTEND_DIR%\.env" (
    del /f /q "%FRONTEND_DIR%\.env"
    echo   Deleted frontend\.env
)

echo.
echo [5/5] System Dependencies (DANGEROUS)
echo   Do you want to globally uninstall Python and Node.js from your system?
echo   WARNING: This might break other applications on your computer.
set /p UNINSTALL="Uninstall global dependencies? (y/N): "
if /i "!UNINSTALL!"=="y" (
    echo   Uninstalling Node.js...
    winget uninstall OpenJS.NodeJS.LTS --silent --accept-source-agreements
    echo   Uninstalling Python...
    winget uninstall --id Python.Python.3.11 --silent --accept-source-agreements
    echo   Uninstallation commands sent.
) else (
    echo   Skipped globally uninstalling Python and Node.js.
)

echo.
echo Teardown complete!
endlocal
