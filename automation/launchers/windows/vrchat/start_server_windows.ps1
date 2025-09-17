#!/usr/bin/env pwsh
# PowerShell script to start Virtual Character MCP Server on Windows
# Run this on the Windows machine with VRChat installed

param(
    [int]$Port = 8020,
    [string]$Host = "0.0.0.0",
    [string]$VRChatHost = "127.0.0.1",
    [switch]$AutoStart = $false
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Virtual Character MCP Server for VRChat" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found Python: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from python.org" -ForegroundColor Yellow
    if (-not $AutoStart) { Read-Host "Press Enter to exit" }
    exit 1
}

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Server Port: $Port"
Write-Host "  Server Host: $Host"
Write-Host "  VRChat Host: $VRChatHost"
Write-Host ""

# Set environment variables
$env:VRCHAT_HOST = $VRChatHost
$env:VRCHAT_USE_VRCEMOTE = "true"  # Enable VRCEmote by default
$env:VRCHAT_USE_BRIDGE = "true"    # Enable audio bridge for actual audio playback
$env:VRCHAT_BRIDGE_PORT = "$Port"  # Use same port as server for bridge
$env:MCP_SERVER_PORT = "$Port"     # Let server know its own port

# Check and install dependencies
Write-Host "Checking dependencies..." -ForegroundColor Yellow

$packages = @(
    @{Name="pythonosc"; Package="python-osc"},
    @{Name="fastapi"; Package="fastapi uvicorn[standard]"},
    @{Name="aiohttp"; Package="aiohttp"}
)

foreach ($pkg in $packages) {
    $testResult = python -c "import $($pkg.Name)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $($pkg.Name) installed" -ForegroundColor Green
    }
    else {
        Write-Host "  Installing $($pkg.Package)..." -ForegroundColor Yellow
        pip install --user $($pkg.Package)
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Warning: Failed to install $($pkg.Package). Trying without --user flag..." -ForegroundColor Yellow
            pip install $($pkg.Package)
        }
    }
}

# Get script directory and navigate to repo root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Join-Path $scriptPath "\..\..\..\."
Set-Location $repoRoot

Write-Host ""
Write-Host "Starting Virtual Character MCP Server..." -ForegroundColor Green
Write-Host "Server will be available at http://${Host}:${Port}" -ForegroundColor Cyan
Write-Host ""
Write-Host "Available endpoints:" -ForegroundColor Yellow
Write-Host "  POST /set_backend      - Connect to VRChat backend"
Write-Host "  POST /send_animation   - Send emotion/gesture"
Write-Host "  POST /execute_behavior - Execute high-level behavior"
Write-Host "  GET  /receive_state    - Get current state"
Write-Host "  GET  /list_backends    - List available backends"
Write-Host "  GET  /get_backend_status - Get backend status"
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Start the server
try {
    python -m tools.mcp.virtual_character.server --port $Port --host $Host --mode http
}
catch {
    Write-Host "Server stopped or encountered an error" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

if (-not $AutoStart) {
    Read-Host "Press Enter to exit"
}
