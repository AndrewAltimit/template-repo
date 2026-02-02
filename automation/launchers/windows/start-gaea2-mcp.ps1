# Start Gaea2 MCP Server on Windows (Rust version)
# This script starts the Gaea2 MCP server with optional Gaea2 path

param(
    [int]$Port = 8007,
    [string]$Host = "0.0.0.0"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Gaea2 MCP Server Launcher (Rust)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to repository root (3 levels up from this script)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptPath))
Set-Location $repoRoot
Write-Host "Working directory: $repoRoot" -ForegroundColor Gray

# Check if GAEA2_PATH is set, try to auto-detect if not
if (-not $env:GAEA2_PATH) {
    $gaeaPaths = @(
        "C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe",
        "C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe",
        "D:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe",
        "D:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe"
    )

    foreach ($path in $gaeaPaths) {
        if (Test-Path $path) {
            $env:GAEA2_PATH = $path
            Write-Host "Auto-detected Gaea2 at: $path" -ForegroundColor Green
            break
        }
    }

    if (-not $env:GAEA2_PATH) {
        Write-Host "WARNING: GAEA2_PATH not set and Gaea2 not found in common locations" -ForegroundColor Yellow
        Write-Host "CLI automation features will be disabled" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To enable CLI features, set GAEA2_PATH to your Gaea.Swarm.exe location:" -ForegroundColor Cyan
        Write-Host '  $env:GAEA2_PATH = "C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe"' -ForegroundColor Cyan
    }
    Write-Host ""
} else {
    Write-Host "Using Gaea2 at: $env:GAEA2_PATH" -ForegroundColor Green
    Write-Host ""
}

# Look for the Rust binary
$binaryPaths = @(
    "tools\mcp\mcp_gaea2\target\release\mcp-gaea2.exe",
    "tools\mcp\mcp_gaea2\target\debug\mcp-gaea2.exe"
)

$binaryPath = $null
foreach ($path in $binaryPaths) {
    $fullPath = Join-Path $repoRoot $path
    if (Test-Path $fullPath) {
        $binaryPath = $fullPath
        break
    }
}

if (-not $binaryPath) {
    Write-Host "Rust binary not found. Building..." -ForegroundColor Yellow

    # Check if cargo is available
    try {
        $cargoVersion = cargo --version 2>&1
        Write-Host "Cargo found: $cargoVersion" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Cargo (Rust) not found in PATH" -ForegroundColor Red
        Write-Host "Please install Rust from https://rustup.rs/" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }

    # Build the binary
    Push-Location (Join-Path $repoRoot "tools\mcp\mcp_gaea2")
    cargo build --release
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to build mcp-gaea2" -ForegroundColor Red
        Pop-Location
        Read-Host "Press Enter to exit"
        exit 1
    }
    Pop-Location

    $binaryPath = Join-Path $repoRoot "tools\mcp\mcp_gaea2\target\release\mcp-gaea2.exe"
}

Write-Host "Using binary: $binaryPath" -ForegroundColor Green

# Set output directory to a Windows-friendly path
if (-not $env:GAEA2_OUTPUT_DIR) {
    $env:GAEA2_OUTPUT_DIR = Join-Path $env:USERPROFILE "gaea2_output"
}
if (-not (Test-Path $env:GAEA2_OUTPUT_DIR)) {
    New-Item -ItemType Directory -Path $env:GAEA2_OUTPUT_DIR -Force | Out-Null
}

# Start the server
Write-Host "Starting server on http://${Host}:${Port}" -ForegroundColor Green
Write-Host "Output directory: $env:GAEA2_OUTPUT_DIR" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

& $binaryPath --mode standalone --port $Port $args
