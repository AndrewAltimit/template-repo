# Sleeper Agent Detection - Windows GPU Launcher (PowerShell)
# For use with RTX 4090 or other NVIDIA GPUs

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

$gpuTest = docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi 2>&1
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
    $gpuInfo = docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    Write-Host "GPU: $gpuInfo" -ForegroundColor Cyan
}

# Set environment variables
$env:SLEEPER_CPU_MODE = "false"
$env:SLEEPER_DEVICE = "cuda"
$env:CUDA_VISIBLE_DEVICES = "0"
$env:NVIDIA_VISIBLE_DEVICES = "all"

# Navigate to project root (3 levels up from this script)
$projectRoot = Join-Path $PSScriptRoot "..\..\..\"
Set-Location $projectRoot
Write-Host ""
Write-Host "Project root: $(Get-Location)" -ForegroundColor Gray

# Create output directories if they don't exist
$outputDirs = @(
    "outputs\sleeper-agents",
    "outputs\sleeper-agents\models",
    "outputs\sleeper-agents\results",
    "outputs\sleeper-agents\cache"
)

foreach ($dir in $outputDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created directory: $dir" -ForegroundColor Gray
    }
}

# Build Docker image
Write-Host ""
Write-Host "Building Docker image..." -ForegroundColor Cyan
$buildResult = docker-compose build sleeper-eval-gpu 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build Docker image" -ForegroundColor Red
    Write-Host $buildResult
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Docker image built successfully" -ForegroundColor Green

# Display service URLs
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting services with GPU acceleration..." -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services will be available at:" -ForegroundColor Green
Write-Host "  Main API:    " -NoNewline -ForegroundColor White
Write-Host "http://localhost:8021" -ForegroundColor Cyan
Write-Host "  Dashboard:   " -NoNewline -ForegroundColor White
Write-Host "http://localhost:8022" -ForegroundColor Cyan
Write-Host "  Monitoring:  " -NoNewline -ForegroundColor White
Write-Host "http://localhost:8023" -ForegroundColor Cyan
Write-Host "  Vector DB:   " -NoNewline -ForegroundColor White
Write-Host "http://localhost:8024" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Documentation: " -NoNewline -ForegroundColor White
Write-Host "http://localhost:8021/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop services" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Start services
docker-compose up sleeper-eval-gpu
