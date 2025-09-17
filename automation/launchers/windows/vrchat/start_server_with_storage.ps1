#!/usr/bin/env pwsh
# Virtual Character MCP Server with Storage Service
# Enhanced launcher that includes secure file exchange service for:
# - Audio files (TTS, sound effects, music)
# - Animation data and sequences
# - Avatar assets and configurations
# - Cross-machine file transfer (VM, containers, remote servers)

param(
    [int]$Port = 8020,
    [string]$Host = "0.0.0.0",
    [string]$VRChatHost = "127.0.0.1",
    [int]$StoragePort = 8021,
    [switch]$AutoStart = $false,
    [switch]$NoStorage = $false
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Virtual Character MCP Server with Storage" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Load environment variables from .env file if it exists
$envFile = Join-Path (Split-Path -Parent $PSScriptRoot) "..\..\..\..\..\.env"
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
Write-Host "  MCP Server Port: $Port"
Write-Host "  MCP Server Host: $Host"
Write-Host "  VRChat Host: $VRChatHost"
if (-not $NoStorage) {
    Write-Host "  Storage Service Port: $StoragePort"
    Write-Host "  Storage Service URL: http://localhost:$StoragePort"
}
Write-Host ""

# Set environment variables
$env:VRCHAT_HOST = $VRChatHost
$env:VRCHAT_USE_VRCEMOTE = "true"
$env:VRCHAT_USE_BRIDGE = "true"
$env:VRCHAT_BRIDGE_PORT = "$Port"
$env:MCP_SERVER_PORT = "$Port"
$env:STORAGE_PORT = "$StoragePort"
$env:STORAGE_HOST = "0.0.0.0"
$env:STORAGE_BASE_URL = "http://localhost:$StoragePort"

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

# Start storage service if not disabled
$storageProcess = $null
if (-not $NoStorage) {
    Write-Host ""
    Write-Host "Starting Audio Storage Service..." -ForegroundColor Green

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
            Write-Host "✓ Storage Service started at http://localhost:$StoragePort" -ForegroundColor Green
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
Write-Host "Available endpoints:" -ForegroundColor Yellow
Write-Host "  POST /set_backend      - Connect to VRChat backend"
Write-Host "  POST /send_animation   - Send emotion/gesture"
Write-Host "  POST /execute_behavior - Execute high-level behavior"
Write-Host "  POST /audio/play       - Play audio (with storage URL support)"
Write-Host "  GET  /receive_state    - Get current state"
Write-Host "  GET  /list_backends    - List available backends"
Write-Host "  GET  /get_backend_status - Get backend status"

if (-not $NoStorage) {
    Write-Host ""
    Write-Host "Storage Service endpoints:" -ForegroundColor Yellow
    Write-Host "  POST http://localhost:$StoragePort/upload - Upload audio file"
    Write-Host "  GET  http://localhost:$StoragePort/download/<id> - Download audio"
    Write-Host "  GET  http://localhost:$StoragePort/health - Service health"
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
