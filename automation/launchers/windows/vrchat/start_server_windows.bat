@echo off
REM Start Virtual Character MCP Server on Windows for VRChat control
REM This script should be run on the Windows machine with VRChat installed

echo ============================================
echo Virtual Character MCP Server for VRChat
echo ============================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Set default values
set PORT=8020
set HOST=0.0.0.0
set VRCHAT_HOST=127.0.0.1

REM Parse command line arguments
if not "%1"=="" set PORT=%1
if not "%2"=="" set HOST=%2
if not "%3"=="" set VRCHAT_HOST=%3

echo Configuration:
echo   Server Port: %PORT%
echo   Server Host: %HOST%
echo   VRChat Host: %VRCHAT_HOST%
echo.

REM Set environment variable for VRChat host
set VRCHAT_HOST=%VRCHAT_HOST%

REM Check if required packages are installed
echo Checking dependencies...
python -c "import pythonosc" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing python-osc...
    pip install --user python-osc
) else (
    echo   [OK] pythonosc installed
)

python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing FastAPI...
    pip install --user fastapi "uvicorn[standard]"
) else (
    echo   [OK] fastapi installed
)

python -c "import aiohttp" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing aiohttp...
    pip install --user aiohttp
) else (
    echo   [OK] aiohttp installed
)

REM Navigate to the repository root (script is in automation/launchers/windows/vrchat)
cd /d "%~dp0\..\..\..\..\"

echo.
echo Starting Virtual Character MCP Server...
echo Server will be available at http://%HOST%:%PORT%
echo.
echo Press Ctrl+C to stop the server
echo ============================================
echo.

REM Start the server
python -m tools.mcp.virtual_character.server --port %PORT% --host %HOST% --mode http

pause
