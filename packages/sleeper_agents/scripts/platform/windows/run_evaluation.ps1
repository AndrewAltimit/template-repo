# Sleeper Agent Detection - Windows Evaluation Launcher
# Comprehensive model evaluation system for RTX 4090

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

# Ensure script exits on any error (after param: it must be the first statement)
$ErrorActionPreference = "Stop"

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

# Navigate to the repository root (5 levels up from this script)
$projectRoot = Join-Path $PSScriptRoot "..\..\..\..\.."
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

# Build the image through docker compose
Write-Host "Building evaluation image..." -ForegroundColor Cyan

$service = if ($GPU) { "sleeper-eval-gpu" } else { "sleeper-eval-cpu" }
$composeProfile = if ($GPU) { "eval-gpu" } else { "eval-cpu" }

docker compose --profile $composeProfile build $service
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build Docker image" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Image built" -ForegroundColor Green
Write-Host ""

# Prepare command based on mode
if ($Batch) {
    # Batch evaluation mode; paths are relative to the repo root (/app in the container)
    if (-not $Config) {
        $Config = "packages/sleeper_agents/src/sleeper_agents/configs/batch_eval_example.json"
    }

    Write-Host "Running BATCH EVALUATION" -ForegroundColor Yellow
    Write-Host "Config: $Config" -ForegroundColor Gray
    Write-Host ""

    $command = "batch"
    $cliArgs = @($Config -replace '\\', '/')
    if ($GPU) { $cliArgs += "--gpu" }

} else {
    # Single model evaluation
    Write-Host "Evaluating Model: $Model" -ForegroundColor Yellow
    Write-Host "Test Suites: $($TestSuites -join ', ')" -ForegroundColor Gray
    Write-Host "GPU Mode: $GPU" -ForegroundColor Gray
    Write-Host ""

    $command = "evaluate"
    $cliArgs = @($Model)

    if ($TestSuites.Count -gt 0) {
        $cliArgs += "--suites"
        $cliArgs += $TestSuites
    }

    if ($GPU) { $cliArgs += "--gpu" }
    if ($Report) { $cliArgs += "--report" }
}

# The compose service mounts the repo read-only at /app, evaluation_results at
# /results, and provides the GPU, model cache and database.
$dockerArgs = @("compose", "--profile", $composeProfile, "run", "--rm", $service)

if ($GPU) {
    Write-Host "Using GPU acceleration (RTX 4090)" -ForegroundColor Green
} else {
    Write-Host "Using CPU mode" -ForegroundColor Yellow
}

$dockerArgs += "python", "-m", "sleeper_agents.cli"
$dockerArgs += $command
$dockerArgs += $cliArgs

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
    $latestReport = Get-ChildItem $resultsDir -Filter "*.html" -Recurse |
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
