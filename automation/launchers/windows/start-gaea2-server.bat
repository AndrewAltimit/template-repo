@echo off
REM Start Gaea2 MCP Server on Windows (simple launcher)
REM For full-featured launcher with auto-detection, use start-gaea2-mcp.bat

REM Navigate to repository root (3 levels up from this script)
cd /d "%~dp0\..\..\..\"

echo Starting Gaea2 MCP Server...
echo.

REM Check if packages are installed
python -c "import mcp_core" >nul 2>&1
if errorlevel 1 (
    echo Installing mcp_core package...
    pip install -e tools\mcp\mcp_core -q
)
python -c "import mcp_gaea2" >nul 2>&1
if errorlevel 1 (
    echo Installing mcp_gaea2 package...
    pip install -e tools\mcp\mcp_gaea2 -q
)

python -m mcp_gaea2.server --mode http %*
pause
