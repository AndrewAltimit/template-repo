@echo off
REM Start ComfyUI MCP Server on Windows
REM This server acts as a bridge to the remote ComfyUI at 192.168.0.152:8013

echo Starting ComfyUI MCP Server Bridge...
echo.

REM Show remote server info
echo This server bridges to remote ComfyUI at:
echo   Host: 192.168.0.152
echo   Port: 8013
echo.
echo Make sure the remote ComfyUI server is running for full functionality.
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
if not "%COMFYUI_HOST%"=="" (
    echo Using custom ComfyUI host: %COMFYUI_HOST%
)
if not "%COMFYUI_PORT%"=="" (
    echo Using custom ComfyUI port: %COMFYUI_PORT%
)
echo.

REM Start the server
echo Starting bridge server on http://localhost:8013
echo Press Ctrl+C to stop the server
echo.

cd /d "%~dp0\.."
python -m tools.mcp.comfyui.server --mode http %*

pause
