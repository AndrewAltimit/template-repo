# Sleeper Agent Detection - Windows CPU Mode Launcher
# For testing without GPU
#
# Usage:
#   .\launch_cpu.ps1                 Quick CPU test with gpt2
#   .\launch_cpu.ps1 -Model <model>  Quick CPU test with another model

param(
    [Parameter(HelpMessage="Model for the quick test (default: gpt2)")]
    [string]$Model
)

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

# Navigate to the repository root (5 levels up from this script)
$projectRoot = Join-Path $PSScriptRoot "..\..\..\..\.."
Set-Location $projectRoot

Write-Host "Project root: $(Get-Location)" -ForegroundColor Gray
Write-Host ""

# Results directory (mounted at /results in the container)
if (-not (Test-Path "evaluation_results")) {
    New-Item -ItemType Directory -Path "evaluation_results" -Force | Out-Null
}

Write-Host "Building Docker image for CPU mode..." -ForegroundColor Cyan
docker compose --profile eval-cpu build sleeper-eval-cpu

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build Docker image" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Image built successfully" -ForegroundColor Green
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Running the quick CPU test..." -ForegroundColor Yellow
Write-Host ""
Write-Host "NOTE: CPU mode uses minimal models for testing only" -ForegroundColor Gray
Write-Host "For production use, deploy with GPU support" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Run the quick test (the container exits when it finishes)
if ($Model) {
    docker compose --profile eval-cpu run --rm sleeper-eval-cpu python -m sleeper_agents.cli test --cpu --model $Model
} else {
    docker compose --profile eval-cpu run --rm sleeper-eval-cpu
}
$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "Results are written to evaluation_results\" -ForegroundColor Green
exit $exitCode
