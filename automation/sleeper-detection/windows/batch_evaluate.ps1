# PowerShell Batch Evaluation Script for Multiple Models
# Automates evaluation of multiple models with comprehensive reporting

param(
    [Parameter(HelpMessage="JSON config file or comma-separated model list")]
    [string]$Config,

    [Parameter(HelpMessage="Models to evaluate (if not using config)")]
    [string[]]$Models = @("gpt2", "distilgpt2", "gpt2-medium"),

    [Parameter(HelpMessage="Test suites to run")]
    [string[]]$Suites = @("basic", "code_vulnerability", "robustness", "chain_of_thought"),

    [Parameter(HelpMessage="Use GPU acceleration")]
    [switch]$GPU,

    [Parameter(HelpMessage="Generate comparison report after all evaluations")]
    [switch]$CompareResults,

    [Parameter(HelpMessage="Output directory for results")]
    [string]$OutputDir = "batch_evaluation_results",

    [Parameter(HelpMessage="Open final report in browser")]
    [switch]$OpenReport,

    [Parameter(HelpMessage="Use Docker for execution")]
    [switch]$Docker,

    [Parameter(HelpMessage="Continue on error")]
    [switch]$ContinueOnError
)

$ErrorActionPreference = if ($ContinueOnError) { "Continue" } else { "Stop" }
$script:ProjectRoot = Join-Path $PSScriptRoot "..\..\..\"
$script:StartTime = Get-Date

# Color functions
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Progress { Write-Host $args -ForegroundColor Magenta }

Write-Success "========================================="
Write-Success "  Sleeper Detection Batch Evaluation"
Write-Success "========================================="
Write-Host ""

# Create output directory
$OutputPath = Join-Path $ProjectRoot $OutputDir
if (-not (Test-Path $OutputPath)) {
    New-Item -ItemType Directory -Path $OutputPath | Out-Null
    Write-Info "Created output directory: $OutputPath"
}

# Generate or load configuration
$configData = $null

if ($Config) {
    if ($Config.EndsWith(".json")) {
        # Load JSON config file
        if (Test-Path $Config) {
            $configData = Get-Content $Config | ConvertFrom-Json
            $Models = $configData.models
            if ($configData.test_suites) {
                $Suites = $configData.test_suites
            }
            Write-Info "Loaded configuration from: $Config"
        } else {
            Write-Error "Config file not found: $Config"
            exit 1
        }
    } else {
        # Parse comma-separated model list
        $Models = $Config -split ","
    }
}

# Create batch config if not provided
if (-not $configData) {
    $configData = @{
        models = $Models
        test_suites = $Suites
        output_dir = $OutputPath
        gpu_mode = $GPU.IsPresent
        reporting = @{
            generate_comparison_report = $CompareResults.IsPresent
            report_format = "html"
        }
    }
}

# Save config for reference
$configPath = Join-Path $OutputPath "batch_config.json"
$configData | ConvertTo-Json -Depth 10 | Set-Content $configPath
Write-Info "Saved batch configuration to: $configPath"

Write-Host ""
Write-Info "Models to evaluate: $($Models -join ', ')"
Write-Info "Test suites: $($Suites -join ', ')"
Write-Info "GPU Mode: $($GPU.IsPresent)"
Write-Info "Docker Mode: $($Docker.IsPresent)"
Write-Host ""

# Initialize results tracking
$results = @{
    successful = @()
    failed = @()
    skipped = @()
    timings = @{}
}

# Evaluate each model
$modelCount = $Models.Count
$currentModel = 0

foreach ($model in $Models) {
    $currentModel++
    Write-Progress "[$currentModel/$modelCount] Evaluating model: $model"
    Write-Host ""

    $modelStart = Get-Date
    $modelOutput = Join-Path $OutputPath $model

    try {
        # Create model-specific output directory
        if (-not (Test-Path $modelOutput)) {
            New-Item -ItemType Directory -Path $modelOutput | Out-Null
        }

        # Build evaluation command
        $evalArgs = @{
            Command = "evaluate"
            Models = @($model)
            Suites = $Suites
            GPU = $GPU
            GenerateReport = $true
            Output = $modelOutput
            Docker = $Docker
        }

        # Run evaluation
        Write-Info "Starting evaluation of $model..."
        & (Join-Path $PSScriptRoot "run_cli.ps1") @evalArgs

        $modelTime = (Get-Date) - $modelStart
        $results.successful += $model
        $results.timings[$model] = $modelTime.TotalMinutes

        Write-Success "✓ Completed $model in $([Math]::Round($modelTime.TotalMinutes, 2)) minutes"

        # Generate individual model report
        $reportArgs = @{
            Command = "report"
            Models = @($model)
            Format = "html"
            Output = Join-Path $modelOutput "report.html"
        }

        & (Join-Path $PSScriptRoot "run_cli.ps1") @reportArgs

    } catch {
        Write-Error "✗ Failed to evaluate $model: $_"
        $results.failed += $model

        if (-not $ContinueOnError) {
            Write-Error "Stopping batch evaluation due to error"
            break
        }
    }

    Write-Host ""
}

# Generate comparison report if requested and multiple models succeeded
if ($CompareResults -and $results.successful.Count -gt 1) {
    Write-Progress "Generating model comparison report..."

    try {
        $compareArgs = @{
            Command = "compare"
            Models = $results.successful
            Output = Join-Path $OutputPath "comparison_report.html"
        }

        & (Join-Path $PSScriptRoot "run_cli.ps1") @compareArgs

        Write-Success "✓ Generated comparison report"

        if ($OpenReport) {
            Start-Process (Join-Path $OutputPath "comparison_report.html")
        }

    } catch {
        Write-Warning "Failed to generate comparison report: $_"
    }
}

# Generate summary
$totalTime = (Get-Date) - $StartTime

Write-Host ""
Write-Success "========================================="
Write-Success "  Batch Evaluation Complete"
Write-Success "========================================="
Write-Host ""

Write-Info "Summary:"
Write-Success "  Successful: $($results.successful.Count) models"
if ($results.failed.Count -gt 0) {
    Write-Error "  Failed: $($results.failed.Count) models ($($results.failed -join ', '))"
}
if ($results.skipped.Count -gt 0) {
    Write-Warning "  Skipped: $($results.skipped.Count) models"
}

Write-Info "  Total time: $([Math]::Round($totalTime.TotalMinutes, 2)) minutes"
Write-Info "  Results saved to: $OutputPath"

# Save summary to file
$summaryPath = Join-Path $OutputPath "batch_summary.json"
$summary = @{
    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    models_evaluated = $results.successful
    models_failed = $results.failed
    test_suites = $Suites
    gpu_mode = $GPU.IsPresent
    total_time_minutes = [Math]::Round($totalTime.TotalMinutes, 2)
    individual_timings = $results.timings
    output_directory = $OutputPath
}

$summary | ConvertTo-Json -Depth 10 | Set-Content $summaryPath
Write-Info "  Summary saved to: $summaryPath"

# Exit with appropriate code
if ($results.failed.Count -gt 0 -and -not $ContinueOnError) {
    exit 1
} else {
    exit 0
}
