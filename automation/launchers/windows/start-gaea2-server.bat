@echo off
REM Start Gaea2 MCP Server on Windows

REM Navigate to repository root (3 levels up from this script)
cd /d "%~dp0\..\..\..\"
echo Starting Gaea2 MCP Server...
python -m tools.mcp.gaea2.server %*
pause
