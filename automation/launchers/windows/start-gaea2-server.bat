@echo off
REM Start Gaea2 MCP Server on Windows

cd /d "%~dp0\.."
echo Starting Gaea2 MCP Server...
python -m tools.mcp.gaea2.server %*
pause
