# Sleeper Agent Detection - Windows CPU Mode Launcher
# For testing without GPU

# Ensure script exits on any error
$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "SLEEPER AGENT DETECTION SYSTEM - CPU MODE" -ForegroundColor Yellow
Write-Host "Testing/Development Mode (No GPU Required)" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Check for Docker
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is not installed" -ForegroundColor Red
    Write-Host "Please install Docker Desktop for Windows" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Docker detected" -ForegroundColor Green

# Set environment variables for CPU mode
$env:SLEEPER_CPU_MODE = "true"
$env:SLEEPER_DEVICE = "cpu"
$env:CUDA_VISIBLE_DEVICES = ""

# Navigate to project root
$projectRoot = Join-Path $PSScriptRoot "..\..\..\"
Set-Location $projectRoot

Write-Host "Project root: $(Get-Location)" -ForegroundColor Gray
Write-Host ""

# Create output directories
$outputDirs = @("outputs\sleeper-detection", "outputs\sleeper-detection\cpu-test")
foreach ($dir in $outputDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

Write-Host "Building Docker image for CPU mode..." -ForegroundColor Cyan
docker-compose build sleeper-eval-cpu

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build Docker image" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Image built successfully" -ForegroundColor Green
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting services in CPU mode..." -ForegroundColor Yellow
Write-Host ""
Write-Host "NOTE: CPU mode uses minimal models for testing only" -ForegroundColor Gray
Write-Host "For production use, deploy with GPU support" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services available at:" -ForegroundColor Green
Write-Host "  API:       http://localhost:8021" -ForegroundColor Cyan
Write-Host "  Docs:      http://localhost:8021/docs" -ForegroundColor Cyan
Write-Host "  Health:    http://localhost:8021/health" -ForegroundColor Cyan
Write-Host ""

# Start CPU mode service
docker-compose up sleeper-eval-cpu
