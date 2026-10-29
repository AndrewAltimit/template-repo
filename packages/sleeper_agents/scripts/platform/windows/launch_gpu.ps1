# Sleeper Agent Detection - Windows GPU Launcher (PowerShell)
# For use with RTX 4090 or other NVIDIA GPUs (driver 580 or newer for CUDA 13.0)
#
# Usage:
#   .\launch_gpu.ps1                 Quick GPU test (gpt2, basic suite)
#   .\launch_gpu.ps1 -Model <model>  Full evaluation of <model> with an HTML report

param(
    [Parameter(HelpMessage="Model to evaluate; omit for the quick GPU test")]
    [string]$Model
)

# Ensure script exits on any error
$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "SLEEPER AGENT DETECTION SYSTEM - GPU MODE" -ForegroundColor Yellow
Write-Host "RTX 4090 Deployment Launcher" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Function to check command availability
function Test-Command($cmdname) {
    return [bool](Get-Command -Name $cmdname -ErrorAction SilentlyContinue)
}

# Check for Docker
if (-not (Test-Command "docker")) {
    Write-Host "ERROR: Docker is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Docker Desktop for Windows from:" -ForegroundColor Yellow
    Write-Host "https://www.docker.com/products/docker-desktop/" -ForegroundColor Cyan
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Docker detected: " -NoNewline -ForegroundColor Green
docker --version

# Check Docker daemon is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "ERROR: Docker daemon is not running" -ForegroundColor Red
    Write-Host "Please start Docker Desktop" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check for NVIDIA GPU
Write-Host ""
Write-Host "Checking GPU availability..." -ForegroundColor Cyan

$gpuTest = docker run --rm --gpus all nvidia/cuda:13.0.2-base-ubuntu24.04 nvidia-smi 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: NVIDIA Docker support not fully configured" -ForegroundColor Yellow
    Write-Host "Attempting to detect GPU directly..." -ForegroundColor Yellow

    # Try to detect NVIDIA GPU on Windows
    $gpu = Get-WmiObject Win32_VideoController | Where-Object {$_.Name -like "*NVIDIA*"}
    if ($gpu) {
        Write-Host "[OK] NVIDIA GPU detected: $($gpu.Name)" -ForegroundColor Green
        Write-Host "Note: Docker GPU passthrough may need configuration" -ForegroundColor Yellow
    } else {
        Write-Host "ERROR: No NVIDIA GPU detected" -ForegroundColor Red
        Write-Host ""
        Write-Host "To run in CPU mode instead, use:" -ForegroundColor Yellow
        Write-Host "  .\launch_cpu.ps1" -ForegroundColor Cyan
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "[OK] GPU support verified" -ForegroundColor Green
    # Display GPU info
    $gpuInfo = docker run --rm --gpus all nvidia/cuda:13.0.2-base-ubuntu24.04 nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    Write-Host "GPU: $gpuInfo" -ForegroundColor Cyan
}

# Set environment variables
$env:SLEEPER_CPU_MODE = "false"
$env:SLEEPER_DEVICE = "cuda"
$env:CUDA_VISIBLE_DEVICES = "0"
$env:NVIDIA_VISIBLE_DEVICES = "all"

# Navigate to the repository root (5 levels up from this script)
$projectRoot = Join-Path $PSScriptRoot "..\..\..\..\.."
Set-Location $projectRoot
Write-Host ""
Write-Host "Project root: $(Get-Location)" -ForegroundColor Gray

# Results directory (mounted at /results in the container)
if (-not (Test-Path "evaluation_results")) {
    New-Item -ItemType Directory -Path "evaluation_results" -Force | Out-Null
    Write-Host "Created directory: evaluation_results" -ForegroundColor Gray
}

# Build Docker image
Write-Host ""
Write-Host "Building Docker image..." -ForegroundColor Cyan
$buildResult = docker compose --profile eval-gpu build sleeper-eval-gpu 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build Docker image" -ForegroundColor Red
    Write-Host $buildResult
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Docker image built successfully" -ForegroundColor Green

# Run the evaluation (the container exits when it finishes)
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
if ($Model) {
    Write-Host "Evaluating $Model with GPU acceleration..." -ForegroundColor Yellow
} else {
    Write-Host "Running the quick GPU test..." -ForegroundColor Yellow
}
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

if ($Model) {
    docker compose --profile eval-gpu run --rm sleeper-eval-gpu python -m sleeper_agents.cli evaluate $Model --gpu --report
} else {
    docker compose --profile eval-gpu run --rm sleeper-eval-gpu
}
$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "Results and reports are written to evaluation_results\" -ForegroundColor Green
Write-Host "View them in the dashboard with .\launch_dashboard.ps1" -ForegroundColor Cyan
exit $exitCode
