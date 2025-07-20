# Start Gaea2 MCP Server on Windows
# This script starts the Gaea2 MCP server with optional Gaea2 path

Write-Host "Starting Gaea2 MCP Server..." -ForegroundColor Green
Write-Host ""

# Check if GAEA2_PATH is set
if (-not $env:GAEA2_PATH) {
    Write-Host "WARNING: GAEA2_PATH environment variable not set" -ForegroundColor Yellow
    Write-Host "CLI automation features will be disabled" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To enable CLI features, set GAEA2_PATH to your Gaea.Swarm.exe location:" -ForegroundColor Cyan
    Write-Host '  $env:GAEA2_PATH = "C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe"' -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "Using Gaea2 at: $env:GAEA2_PATH" -ForegroundColor Green
    Write-Host ""
}

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ and add it to PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Start the server
Write-Host "Starting server on http://localhost:8007" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Change to repository root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptPath
Set-Location $repoRoot

# Start the server
python -m tools.mcp.gaea2.server --mode http $args
