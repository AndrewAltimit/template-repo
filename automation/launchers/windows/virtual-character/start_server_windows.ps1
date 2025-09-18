#!/usr/bin/env pwsh
# Virtual Character MCP Server with Storage Service
# Unified launcher for AI agent embodiment platform
# Supports VRChat, Unity, Unreal, Blender backends

param(
    [int]$Port = 8020,
    [string]$Host = "0.0.0.0",
    [string]$BackendHost = "127.0.0.1",
    [int]$StoragePort = 8021,
    [switch]$NoStorage = $false,
    [switch]$AutoStart = $false,
    [switch]$Help = $false
)

# Show help if requested
if ($Help) {
    Write-Host ""
    Write-Host "Virtual Character Platform Launcher"
    Write-Host "====================================="
    Write-Host ""
    Write-Host "Usage: .\start_server_windows.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Port <int>         MCP server port (default: 8020)"
    Write-Host "  -Host <string>      MCP server host (default: 0.0.0.0)"
    Write-Host "  -BackendHost <string> Backend host for VRChat/Unity (default: 127.0.0.1)"
    Write-Host "  -StoragePort <int>  Storage service port (default: 8021)"
    Write-Host "  -NoStorage          Disable storage service"
    Write-Host "  -AutoStart          Don't pause at the end"
    Write-Host "  -Help               Show this help message"
    Write-Host ""
    Write-Host "Example:"
    Write-Host "  .\start_server_windows.ps1 -Port 8020 -BackendHost 192.168.1.100"
    Write-Host ""
    exit 0
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Virtual Character Platform" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and navigate to repo root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Join-Path $scriptPath "\..\..\..\."
Set-Location $repoRoot

# Load environment variables from .env file if it exists
$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    Write-Host "Loading environment from .env file..." -ForegroundColor Yellow
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Host "Environment loaded" -ForegroundColor Green
    Write-Host ""
}

# Check for storage secret key
if (-not $env:STORAGE_SECRET_KEY) {
    Write-Host "WARNING: STORAGE_SECRET_KEY not set in .env file" -ForegroundColor Yellow
    Write-Host "Generating temporary key for this session..." -ForegroundColor Yellow
    $tempKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
    $env:STORAGE_SECRET_KEY = $tempKey
    Write-Host "Temporary key generated (will not persist)" -ForegroundColor Yellow
    Write-Host ""
}

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
Write-Host "  MCP Server: http://${Host}:${Port}"
Write-Host "  Backend Host: $BackendHost"
if (-not $NoStorage) {
    Write-Host "  Storage Service: http://localhost:$StoragePort"
}
Write-Host ""

# Set environment variables
$env:VRCHAT_HOST = $BackendHost
$env:VRCHAT_USE_VRCEMOTE = "true"
$env:VRCHAT_USE_BRIDGE = "true"
$env:VRCHAT_BRIDGE_PORT = "$Port"
$env:MCP_SERVER_PORT = "$Port"
$env:STORAGE_PORT = "$StoragePort"
$env:STORAGE_HOST = "0.0.0.0"
$env:STORAGE_BASE_URL = "http://localhost:$StoragePort"
$env:VIRTUAL_CHARACTER_SERVER = "http://${Host}:${Port}"

# Check and install dependencies
Write-Host "Checking dependencies..." -ForegroundColor Yellow

$packages = @(
    @{Name="pythonosc"; Package="python-osc"},
    @{Name="fastapi"; Package="fastapi uvicorn[standard] python-multipart"},
    @{Name="aiohttp"; Package="aiohttp"},
    @{Name="requests"; Package="requests"}
)

foreach ($pkg in $packages) {
    $testResult = python -c "import $($pkg.Name)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $($pkg.Name) installed" -ForegroundColor Green
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

# Start storage service if not disabled
$storageProcess = $null
if (-not $NoStorage) {
    Write-Host ""
    Write-Host "Starting Storage Service..." -ForegroundColor Green

    # Create storage directory
    $storageDir = Join-Path $env:TEMP "audio_storage"
    if (-not (Test-Path $storageDir)) {
        New-Item -ItemType Directory -Path $storageDir | Out-Null
    }

    # Start storage service in background
    $storageScript = @"
import os
os.chdir('$repoRoot')
exec(open('tools/mcp/virtual_character/storage_service/server.py').read())
"@

    $storageProcess = Start-Process python -ArgumentList "-c", $storageScript -PassThru -WindowStyle Hidden

    # Wait for storage service to start
    Start-Sleep -Seconds 2

    # Check if storage service is running
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$StoragePort/health" -Method GET -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] Storage Service started at http://localhost:$StoragePort" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "Warning: Storage service may not be running properly" -ForegroundColor Yellow
        Write-Host "Continuing without storage service..." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Starting Virtual Character MCP Server..." -ForegroundColor Green
Write-Host "Server will be available at http://${Host}:${Port}" -ForegroundColor Cyan
Write-Host ""
Write-Host "Platform Support:" -ForegroundColor Yellow
Write-Host "  - VRChat (OSC protocol) - Active"
Write-Host "  - Unity (WebSocket) - Coming Soon"
Write-Host "  - Unreal Engine (HTTP API) - Coming Soon"
Write-Host "  - Blender (Python API) - Coming Soon"
Write-Host ""
Write-Host "Available Endpoints:" -ForegroundColor Yellow
Write-Host "  POST /set_backend       - Connect to platform backend"
Write-Host "  POST /send_animation    - Send animation data"
Write-Host "  POST /execute_behavior  - Execute behaviors"
Write-Host "  POST /audio/play        - Play audio with storage support"
Write-Host "  POST /create_sequence   - Create event sequences"
Write-Host "  POST /add_sequence_event - Add events to sequence"
Write-Host "  POST /play_sequence     - Play event sequence"
Write-Host "  GET  /get_backend_status - Get backend status"
Write-Host "  GET  /list_backends     - List available backends"

if (-not $NoStorage) {
    Write-Host ""
    Write-Host "Storage Service Endpoints:" -ForegroundColor Yellow
    Write-Host "  POST http://localhost:$StoragePort/upload - Upload files"
    Write-Host "  POST http://localhost:$StoragePort/upload_base64 - Upload base64 data"
    Write-Host "  GET  http://localhost:$StoragePort/download/<id> - Download files"
    Write-Host "  GET  http://localhost:$StoragePort/health - Service health check"
}

Write-Host ""
Write-Host "Press Ctrl+C to stop the servers" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Register cleanup handler
$cleanupScript = {
    if ($storageProcess -and -not $storageProcess.HasExited) {
        Write-Host "Stopping storage service..." -ForegroundColor Yellow
        Stop-Process -Id $storageProcess.Id -Force
    }
}

# Handle Ctrl+C
[Console]::TreatControlCAsInput = $false
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanupScript | Out-Null

# Start the MCP server
try {
    python -m tools.mcp.virtual_character.server --port $Port --host $Host --mode http
}
catch {
    Write-Host "Server stopped or encountered an error" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}
finally {
    # Cleanup storage service
    if ($storageProcess -and -not $storageProcess.HasExited) {
        Write-Host "Stopping storage service..." -ForegroundColor Yellow
        Stop-Process -Id $storageProcess.Id -Force
    }
}

if (-not $AutoStart) {
    Read-Host "Press Enter to exit"
}
