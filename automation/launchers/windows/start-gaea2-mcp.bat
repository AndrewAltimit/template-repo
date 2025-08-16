@echo off
REM Start Gaea2 MCP Server on Windows
REM This script starts the Gaea2 MCP server with optional Gaea2 path

echo Starting Gaea2 MCP Server...
echo.

REM Check if GAEA2_PATH is set
if "%GAEA2_PATH%"=="" (
    echo WARNING: GAEA2_PATH environment variable not set
    echo CLI automation features will be disabled
    echo.
    echo To enable CLI features, set GAEA2_PATH to your Gaea.Swarm.exe location:
    echo   set GAEA2_PATH=C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe
    echo.
) else (
    echo Using Gaea2 at: %GAEA2_PATH%
    echo.
)

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ and add it to PATH
    pause
    exit /b 1
)

REM Start the server
echo Starting server on http://localhost:8007
echo Press Ctrl+C to stop the server
echo.

REM Navigate to repository root (3 levels up from this script)
cd /d "%~dp0\..\..\..\"
python -m tools.mcp.gaea2.server --mode http %*

pause
