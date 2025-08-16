# Start AI Toolkit Full Application (Web UI + MCP Server) in Docker
# Automatically opens the web UI in your default browser

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI Toolkit Full Application Launcher" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is available
try {
    docker --version | Out-Null
} catch {
    Write-Host "ERROR: Docker not found" -ForegroundColor Red
    Write-Host "Please install Docker Desktop for Windows"
    Write-Host "Download from: https://www.docker.com/products/docker-desktop"
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if docker-compose is available
try {
    docker-compose --version | Out-Null
} catch {
    Write-Host "ERROR: docker-compose not found" -ForegroundColor Red
    Write-Host "Please ensure Docker Desktop is properly installed"
    Read-Host "Press Enter to exit"
    exit 1
}

# Navigate to repository root (3 levels up from this script)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Join-Path $scriptPath "../../.."
Set-Location $repoRoot

Write-Host "Building AI Toolkit container..." -ForegroundColor Yellow
Write-Host "This may take a while on first run or after updates"
docker-compose build mcp-ai-toolkit

Write-Host ""
Write-Host "Starting AI Toolkit container..." -ForegroundColor Yellow
docker-compose --profile ai-services up -d mcp-ai-toolkit

# Check if the container started successfully
$running = docker ps --format "table {{.Names}}" | Select-String "ai-toolkit"
if (-not $running) {
    Write-Host "ERROR: Failed to start AI Toolkit container" -ForegroundColor Red
    Write-Host "Check Docker Desktop and try again"
    docker-compose logs mcp-ai-toolkit
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI Toolkit is starting up..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  Web UI:     http://localhost:8675" -ForegroundColor Cyan
Write-Host "  MCP Server: http://localhost:8012" -ForegroundColor Cyan
Write-Host ""

# Wait for services to initialize with healthcheck polling
Write-Host "Waiting for AI Toolkit to initialize..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8675/" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "`nAI Toolkit is ready!" -ForegroundColor Green
            break
        }
    } catch {
        # Service not ready yet
    }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
    $attempt++
}
if ($attempt -eq $maxAttempts) {
    Write-Host ""
    Write-Host "Warning: AI Toolkit may still be starting up" -ForegroundColor Yellow
}

# Open the web UI in default browser
Write-Host "Opening AI Toolkit Web UI in your browser..." -ForegroundColor Green
Start-Process "http://localhost:8675"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI Toolkit is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  View logs:  docker-compose logs -f mcp-ai-toolkit"
Write-Host "  Stop:       docker-compose --profile ai-services stop mcp-ai-toolkit"
Write-Host "  Restart:    docker-compose --profile ai-services restart mcp-ai-toolkit"
Write-Host ""
Write-Host "Press any key to view logs (Ctrl+C to exit logs)..." -ForegroundColor Yellow
Read-Host

# Show logs
docker-compose logs -f mcp-ai-toolkit
