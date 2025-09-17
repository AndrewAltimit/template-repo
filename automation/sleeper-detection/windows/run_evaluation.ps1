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

# Set environment
$env:USER_ID = "1000"
$env:GROUP_ID = "1000"

# Build Docker image
Write-Host "Building evaluation image..." -ForegroundColor Cyan
docker build -f docker/sleeper-evaluation.Dockerfile -t sleeper-eval . 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build Docker image" -ForegroundColor Red
    exit 1
}

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
$dockerArgs += "python", "-m", "packages.sleeper_detection.cli"
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
