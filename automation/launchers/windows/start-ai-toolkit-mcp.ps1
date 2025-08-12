#!/usr/bin/env pwsh
# Start AI Toolkit MCP Server on Windows (PowerShell)
# This server acts as a bridge to the remote AI Toolkit at 192.168.0.152:8012

Write-Host "Starting AI Toolkit MCP Server Bridge..." -ForegroundColor Green
Write-Host ""

# Show remote server info
Write-Host "This server bridges to remote AI Toolkit at:" -ForegroundColor Cyan
Write-Host "  Host: 192.168.0.152"
Write-Host "  Port: 8012"
Write-Host ""
Write-Host "Make sure the remote AI Toolkit server is running for full functionality." -ForegroundColor Yellow
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ and add it to PATH"
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}

# Check if custom host/port provided via environment
if ($env:AI_TOOLKIT_HOST) {
    Write-Host "Using custom AI Toolkit host: $env:AI_TOOLKIT_HOST" -ForegroundColor Yellow
}
if ($env:AI_TOOLKIT_PORT) {
    Write-Host "Using custom AI Toolkit port: $env:AI_TOOLKIT_PORT" -ForegroundColor Yellow
}
Write-Host ""

# Start the server
Write-Host "Starting bridge server on http://localhost:8012" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Change to repository root directory
Set-Location "$PSScriptRoot\.."

# Start the server with any additional arguments
python -m tools.mcp.ai_toolkit.server --mode http $args

# Keep window open
Read-Host -Prompt "Press Enter to exit"
