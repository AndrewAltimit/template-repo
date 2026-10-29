# PowerShell CLI Runner for Sleeper Detection System
# Provides all CLI operations with GPU/CPU support

param(
    [Parameter(Position=0, Mandatory=$true, HelpMessage="Command to run")]
    [ValidateSet("evaluate", "compare", "batch", "report", "test", "list", "clean", "dashboard")]
    [string]$Command,

    [Parameter(Position=1, HelpMessage="Model name(s) or config file")]
    [string[]]$Models = @(),

    [Parameter(HelpMessage="Test suites to run")]
    [ValidateSet("basic", "code_vulnerability", "chain_of_thought", "robustness", "attention", "intervention", "all")]
    [string[]]$Suites = @("basic", "code_vulnerability"),

    [Parameter(HelpMessage="Use GPU acceleration")]
    [switch]$GPU,

    [Parameter(HelpMessage="Output format for reports")]
    [ValidateSet("html", "pdf", "json")]
    [string]$Format = "html",

    [Parameter(HelpMessage="Output directory/file")]
    [string]$Output,

    [Parameter(HelpMessage="Generate report after evaluation")]
    [switch]$GenerateReport,

    [Parameter(HelpMessage="Open report/dashboard after completion")]
    [switch]$Open,

    [Parameter(HelpMessage="Use Docker for execution")]
    [switch]$Docker
)

# [Parameter()] makes this an advanced script, so -Verbose is the built-in common
# parameter; declaring our own $Verbose switch would fail with "defined multiple times".
$ShowCommands = $PSBoundParameters.ContainsKey("Verbose")

$ErrorActionPreference = "Stop"
$script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..\..")).Path

# Color functions
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }

Write-Success "=== Sleeper Agent Detection CLI ==="
Write-Info "Command: $Command"
if ($GPU) { Write-Info "Mode: GPU Acceleration" } else { Write-Info "Mode: CPU" }
Write-Host ""

# Helper function to build Python command
function Build-PythonCommand {
    $cmdArgs = @("-m", "sleeper_agents.cli", $Command)

    switch ($Command) {
        "evaluate" {
            if ($Models.Count -eq 0) {
                Write-Error "Model name required for evaluate command"
                exit 1
            }
            $cmdArgs += $Models[0]

            if ($Suites.Count -gt 0 -and $Suites[0] -ne "all") {
                $cmdArgs += @("--suites") + $Suites
            }

            if ($GPU) { $cmdArgs += "--gpu" }
            if ($GenerateReport) { $cmdArgs += "--report" }
            if ($Output) { $cmdArgs += @("--output", $Output) }
        }

        "compare" {
            if ($Models.Count -lt 2) {
                Write-Error "At least 2 models required for compare command"
                exit 1
            }
            $cmdArgs += $Models
            if ($Output) { $cmdArgs += @("--output", $Output) }
        }

        "batch" {
            if ($Models.Count -eq 0) {
                Write-Error "Config file path required for batch command"
                exit 1
            }
            $cmdArgs += $Models[0]
            if ($GPU) { $cmdArgs += "--gpu" }
        }

        "report" {
            if ($Models.Count -eq 0) {
                Write-Error "Model name required for report command"
                exit 1
            }
            $cmdArgs += $Models[0]
            $cmdArgs += @("--format", $Format)
            if ($Output) { $cmdArgs += @("--output", $Output) }
        }

        "test" {
            if (-not $GPU) { $cmdArgs += "--cpu" }
            if ($Models.Count -gt 0) {
                $cmdArgs += @("--model", $Models[0])
            }
        }

        "list" {
            if ($Models.Count -gt 0 -and $Models[0] -eq "models") {
                $cmdArgs += "--models"
            } elseif ($Models.Count -gt 0 -and $Models[0] -eq "results") {
                $cmdArgs += "--results"
            } else {
                $cmdArgs += "--models"
            }
        }

        "clean" {
            if ($Models.Count -gt 0) {
                $cmdArgs += @("--model", $Models[0])
            }
        }

        "dashboard" {
            # Special case - launch dashboard instead
            & (Join-Path $PSScriptRoot "launch_dashboard.ps1") -OpenBrowser:$Open
            return
        }
    }

    return $cmdArgs
}

try {
    Push-Location $ProjectRoot

    # Build Python command arguments
    $pythonArgs = Build-PythonCommand

    if ($Docker) {
        Write-Info "Running in Docker container..."

        # Run through the compose service, which supplies the image, the GPU,
        # the results/model-cache/database mounts and EVAL_* settings. The repo
        # is mounted read-only at /app and evaluation_results at /results.
        $service = if ($GPU) { "sleeper-eval-gpu" } else { "sleeper-eval-cpu" }
        $composeProfile = if ($GPU) { "eval-gpu" } else { "eval-cpu" }

        $resultsPath = Join-Path $ProjectRoot "evaluation_results"
        if (-not (Test-Path $resultsPath)) {
            New-Item -ItemType Directory -Path $resultsPath | Out-Null
        }

        # Host paths mean nothing inside the container: map an --output under
        # evaluation_results to /results, and reject anything else.
        $containerArgs = @()
        for ($i = 0; $i -lt $pythonArgs.Count; $i++) {
            $arg = $pythonArgs[$i]
            if ($i -gt 0 -and $pythonArgs[$i - 1] -eq "--output") {
                $full = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $arg))
                $resultsFull = [System.IO.Path]::GetFullPath($resultsPath)
                if (-not $full.StartsWith($resultsFull, [System.StringComparison]::OrdinalIgnoreCase)) {
                    throw "With -Docker, -Output must be inside $resultsFull (got $full)"
                }
                $arg = "/results" + ($full.Substring($resultsFull.Length) -replace '\\', '/')
            }
            $containerArgs += $arg
        }

        $dockerArgs = @("compose", "--profile", $composeProfile, "run", "--rm", $service, "python") + $containerArgs

        if ($ShowCommands) {
            Write-Info "Docker command: docker $($dockerArgs -join ' ')"
        }

        # Run Docker command (from the repo root, where docker-compose.yml is)
        & docker $dockerArgs

        if ($LASTEXITCODE -ne 0) {
            throw "Docker command failed with exit code $LASTEXITCODE"
        }

    } else {
        Write-Info "Running locally with Python..."

        # Check Python installation
        try {
            python --version | Out-Null
        } catch {
            throw "Python is not installed or not in PATH"
        }

        # Set environment variables
        $env:EVAL_RESULTS_DIR = Join-Path $ProjectRoot "evaluation_results"
        $env:EVAL_DB_PATH = Join-Path $env:EVAL_RESULTS_DIR "evaluation_results.db"

        # Create results directory if it doesn't exist
        if (-not (Test-Path $env:EVAL_RESULTS_DIR)) {
            New-Item -ItemType Directory -Path $env:EVAL_RESULTS_DIR | Out-Null
        }

        if ($ShowCommands) {
            Write-Info "Python command: python $($pythonArgs -join ' ')"
        }

        # Run Python command
        & python $pythonArgs

        if ($LASTEXITCODE -ne 0) {
            throw "Python command failed with exit code $LASTEXITCODE"
        }
    }

    # Handle post-execution actions
    if ($GenerateReport -or $Command -eq "report") {
        $reportPath = if ($Output) {
            $Output
        } else {
            Join-Path $env:EVAL_RESULTS_DIR "report_$($Models[0]).html"
        }

        if (Test-Path $reportPath) {
            Write-Success "Report generated: $reportPath"

            if ($Open) {
                Start-Process $reportPath
                Write-Success "Opened report in browser"
            }
        }
    }

    Write-Host ""
    Write-Success "Operation completed successfully!"

} catch {
    Write-Error "Error: $_"
    exit 1
} finally {
    Pop-Location
}
