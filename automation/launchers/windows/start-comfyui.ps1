# Start ComfyUI Full Application (Web UI + MCP Server) in Docker
# Automatically opens the web UI in your default browser

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ComfyUI Full Application Launcher" -ForegroundColor Green
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

Write-Host "Building ComfyUI container..." -ForegroundColor Yellow
Write-Host "This may take a while on first run or after updates"
docker-compose build mcp-comfyui

Write-Host ""
Write-Host "Starting ComfyUI container..." -ForegroundColor Yellow
docker-compose --profile ai-services up -d mcp-comfyui

# Check if the container started successfully
$running = docker ps --format "table {{.Names}}" | Select-String "comfyui"
if (-not $running) {
    Write-Host "ERROR: Failed to start ComfyUI container" -ForegroundColor Red
    Write-Host "Check Docker Desktop and try again"
    docker-compose logs mcp-comfyui
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ComfyUI is starting up..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  Web UI:     http://localhost:8188" -ForegroundColor Cyan
Write-Host "  MCP Server: http://localhost:8013" -ForegroundColor Cyan
Write-Host ""

# Wait for services to initialize with healthcheck polling
Write-Host "Waiting for ComfyUI to initialize..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8188/system_stats" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "`nComfyUI is ready!" -ForegroundColor Green
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
    Write-Host "Warning: ComfyUI may still be starting up" -ForegroundColor Yellow
}

# Open the web UI in default browser
Write-Host "Opening ComfyUI Web UI in your browser..." -ForegroundColor Green
Start-Process "http://localhost:8188"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ComfyUI is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  View logs:  docker-compose logs -f mcp-comfyui"
Write-Host "  Stop:       docker-compose --profile ai-services stop mcp-comfyui"
Write-Host "  Restart:    docker-compose --profile ai-services restart mcp-comfyui"
Write-Host ""
Write-Host "Press any key to view logs (Ctrl+C to exit logs)..." -ForegroundColor Yellow
Read-Host

# Show logs
docker-compose logs -f mcp-comfyui
