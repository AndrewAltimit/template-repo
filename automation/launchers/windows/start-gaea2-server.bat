@echo off
REM Start Gaea2 MCP Server on Windows (Rust version)
REM For full-featured launcher with auto-detection, use start-gaea2-mcp.ps1

REM Navigate to repository root (3 levels up from this script)
cd /d "%~dp0\..\..\..\"

echo Starting Gaea2 MCP Server (Rust)...
echo.

REM Look for release binary first, then debug
if exist "tools\mcp\mcp_gaea2\target\release\mcp-gaea2.exe" (
    echo Using release binary
    tools\mcp\mcp_gaea2\target\release\mcp-gaea2.exe --mode standalone --port 8007 %*
) else if exist "tools\mcp\mcp_gaea2\target\debug\mcp-gaea2.exe" (
    echo Using debug binary
    tools\mcp\mcp_gaea2\target\debug\mcp-gaea2.exe --mode standalone --port 8007 %*
) else (
    echo ERROR: mcp-gaea2 binary not found
    echo Please build it first with: cargo build --release
    echo Run this from the tools\mcp\mcp_gaea2 directory
    pause
    exit /b 1
)
pause
