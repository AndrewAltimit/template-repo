#!/usr/bin/env pwsh
# Start ComfyUI MCP Server on Windows (PowerShell)
# This server acts as a bridge to the remote ComfyUI at 192.168.0.152:8013

Write-Host "Starting ComfyUI MCP Server Bridge..." -ForegroundColor Green
Write-Host ""

# Show remote server info
Write-Host "This server bridges to remote ComfyUI at:" -ForegroundColor Cyan
Write-Host "  Host: 192.168.0.152"
Write-Host "  Port: 8013"
Write-Host ""
Write-Host "Make sure the remote ComfyUI server is running for full functionality." -ForegroundColor Yellow
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
if ($env:COMFYUI_HOST) {
    Write-Host "Using custom ComfyUI host: $env:COMFYUI_HOST" -ForegroundColor Yellow
}
if ($env:COMFYUI_PORT) {
    Write-Host "Using custom ComfyUI port: $env:COMFYUI_PORT" -ForegroundColor Yellow
}
Write-Host ""

# Start the server
Write-Host "Starting bridge server on http://localhost:8013" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Change to repository root directory
Set-Location "$PSScriptRoot\.."

# Start the server with any additional arguments
python -m tools.mcp.comfyui.server --mode http $args

# Keep window open
Read-Host -Prompt "Press Enter to exit"
