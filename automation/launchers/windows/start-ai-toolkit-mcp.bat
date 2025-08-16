@echo off
REM Start AI Toolkit MCP Server on Windows
REM This server acts as a bridge to the remote AI Toolkit at 192.168.0.152:8012

echo Starting AI Toolkit MCP Server Bridge...
echo.

REM Show remote server info
echo This server bridges to remote AI Toolkit at:
echo   Host: 192.168.0.152
echo   Port: 8012
echo.
echo Make sure the remote AI Toolkit server is running for full functionality.
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ and add it to PATH
    pause
    exit /b 1
)

REM Check if custom host/port provided via environment
if not "%AI_TOOLKIT_HOST%"=="" (
    echo Using custom AI Toolkit host: %AI_TOOLKIT_HOST%
)
if not "%AI_TOOLKIT_PORT%"=="" (
    echo Using custom AI Toolkit port: %AI_TOOLKIT_PORT%
)
echo.

REM Start the server
echo Starting bridge server on http://localhost:8012
echo Press Ctrl+C to stop the server
echo.

REM Navigate to repository root (3 levels up from this script)
cd /d "%~dp0\..\..\..\"
python -m tools.mcp.ai_toolkit.server --mode http %*

pause
