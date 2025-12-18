# Start Gaea2 MCP Server on Windows
# This script starts the Gaea2 MCP server with optional Gaea2 path

param(
    [int]$Port = 8007,
    [string]$Host = "0.0.0.0"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Gaea2 MCP Server Launcher" -ForegroundColor Cyan
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

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.10+ and add it to PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if mcp_core package is installed (dependency)
$coreCheck = python -c "import mcp_core" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing mcp_core package..." -ForegroundColor Yellow
    pip install -e tools\mcp\mcp_core -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install mcp_core package" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Check if mcp_gaea2 package is installed
$packageCheck = python -c "import mcp_gaea2" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing mcp_gaea2 package..." -ForegroundColor Yellow
    pip install -e tools\mcp\mcp_gaea2 -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install mcp_gaea2 package" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "Packages installed successfully." -ForegroundColor Green
    Write-Host ""
}

# Start the server
Write-Host "Starting server on http://${Host}:${Port}" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python -m mcp_gaea2.server --mode http --port $Port $args
