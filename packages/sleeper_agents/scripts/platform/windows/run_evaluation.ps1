# Sleeper Agent Detection - Windows Evaluation Launcher
# Comprehensive model evaluation system for RTX 4090

# Ensure script exits on any error
$ErrorActionPreference = "Stop"

param(
    [Parameter()]
    [string]$Model = "gpt2",

    [Parameter()]
    [string[]]$TestSuites = @("basic", "code_vulnerability"),

    [Parameter()]
    [switch]$GPU,

    [Parameter()]
    [switch]$Batch,

    [Parameter()]
    [string]$Config,

    [Parameter()]
    [switch]$Report
)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "SLEEPER AGENT DETECTION - EVALUATION SYSTEM" -ForegroundColor Yellow
Write-Host "Model Safety Assessment Framework" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker not installed" -ForegroundColor Red
    exit 1
}

# Navigate to project root
$projectRoot = Join-Path $PSScriptRoot "..\..\..\"
Set-Location $projectRoot

# Create output directory
$resultsDir = "evaluation_results"
if (-not (Test-Path $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
    Write-Host "Created results directory: $resultsDir" -ForegroundColor Gray
}

# ============================================================================
# IMPORTANT: USER ID CONFIGURATION
# ============================================================================
# The USER_ID and GROUP_ID below are hardcoded to 1000, which is the default
# for most Docker Desktop installations on Windows. However, if you encounter
# file permission errors when writing to mounted volumes, you may need to
# adjust these values.
#
# To find your correct IDs in WSL2 or Docker environment:
#   1. Open WSL2 terminal or Git Bash
#   2. Run: id -u  (to get your user ID)
#   3. Run: id -g  (to get your group ID)
#   4. Replace the values below with your actual IDs
#
# Example: If your IDs are different, uncomment and modify:
# $env:USER_ID = "501"   # Your actual user ID
# $env:GROUP_ID = "501"  # Your actual group ID
# ============================================================================

# Set environment (Default: 1000 for standard Docker Desktop installations)
$env:USER_ID = "1000"
$env:GROUP_ID = "1000"

# Check if running in WSL2 and warn if IDs might be different
if (Test-Path "/proc/version") {
    $actualUID = & bash -c "id -u" 2>$null
    $actualGID = & bash -c "id -g" 2>$null

    if ($actualUID -and $actualUID -ne "1000") {
        Write-Host "WARNING: Your actual user ID is $actualUID, but using 1000." -ForegroundColor Yellow
        Write-Host "If you encounter permission errors, update USER_ID in this script." -ForegroundColor Yellow
        Write-Host ""
    }
}

# Build Docker image using docker compose for consistency
Write-Host "Building evaluation image..." -ForegroundColor Cyan

# Determine which image to build based on GPU flag
if ($GPU) {
    docker compose build sleeper-eval-gpu 2>&1 | Out-Null
    $imageName = "sleeper-eval-gpu"
} else {
    docker compose build sleeper-eval-cpu 2>&1 | Out-Null
    $imageName = "sleeper-eval-cpu"
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build Docker image" -ForegroundColor Red
    exit 1
}

# Tag the built image for use in the script
docker tag $imageName`:latest sleeper-eval:latest

Write-Host "[OK] Image built" -ForegroundColor Green
Write-Host ""

# Prepare command based on mode
if ($Batch) {
    # Batch evaluation mode
    if (-not $Config) {
        $Config = "configs/batch_eval_example.json"
    }

    Write-Host "Running BATCH EVALUATION" -ForegroundColor Yellow
    Write-Host "Config: $Config" -ForegroundColor Gray
    Write-Host ""

    $command = "batch"
    $args = @($Config)
    if ($GPU) { $args += "--gpu" }

} else {
    # Single model evaluation
    Write-Host "Evaluating Model: $Model" -ForegroundColor Yellow
    Write-Host "Test Suites: $($TestSuites -join ', ')" -ForegroundColor Gray
    Write-Host "GPU Mode: $GPU" -ForegroundColor Gray
    Write-Host ""

    $command = "evaluate"
    $args = @($Model)

    if ($TestSuites.Count -gt 0) {
        $args += "--suites"
        $args += $TestSuites
    }

    if ($GPU) { $args += "--gpu" }
    if ($Report) { $args += "--report" }
}

# Build Docker command
$dockerArgs = @(
    "run",
    "--rm",
    "-it",
    "-v", "${pwd}/evaluation_results:/results",
    "-v", "${pwd}:/app:ro"
)

# Add GPU support if requested
if ($GPU) {
    $dockerArgs += "--gpus", "all"
    Write-Host "Using GPU acceleration (RTX 4090)" -ForegroundColor Green
} else {
    Write-Host "Using CPU mode" -ForegroundColor Yellow
}

$dockerArgs += "sleeper-eval"
$dockerArgs += "python", "-m", "packages.sleeper_agents.cli"
$dockerArgs += $command
$dockerArgs += $args

# Display command for debugging
Write-Host "Command: docker $($dockerArgs -join ' ')" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Starting evaluation..." -ForegroundColor Cyan
Write-Host "="*60 -ForegroundColor Cyan
Write-Host ""

# Run evaluation
& docker @dockerArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "="*60 -ForegroundColor Green
    Write-Host "EVALUATION COMPLETE" -ForegroundColor Green

    # Show results location
    $latestReport = Get-ChildItem $resultsDir -Filter "*.html" |
                    Sort-Object LastWriteTime -Descending |
                    Select-Object -First 1

    if ($latestReport) {
        Write-Host "Report: $($latestReport.FullName)" -ForegroundColor Cyan

        # Offer to open report
        $open = Read-Host "Open report in browser? (Y/N)"
        if ($open -eq "Y" -or $open -eq "y") {
            Start-Process $latestReport.FullName
        }
    }
} else {
    Write-Host ""
    Write-Host "EVALUATION FAILED" -ForegroundColor Red
    exit 1
}
