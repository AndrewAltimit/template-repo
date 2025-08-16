@echo off
REM Start ComfyUI Full Application (Web UI + MCP Server) in Docker
REM Automatically opens the web UI in your default browser

echo ========================================
echo ComfyUI Full Application Launcher
echo ========================================
echo.

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker not found
    echo Please install Docker Desktop for Windows
    echo Download from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: docker-compose not found
    echo Please ensure Docker Desktop is properly installed
    pause
    exit /b 1
)

REM Navigate to repository root (3 levels up from this script)
cd /d "%~dp0\..\..\..\"

echo Starting ComfyUI container...
echo This may take a while on first run as it builds the container
echo.

REM Start the ComfyUI service
docker-compose --profile ai-services up -d mcp-comfyui

REM Check if the container started successfully
docker ps | findstr comfyui >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to start ComfyUI container
    echo Check Docker Desktop and try again
    docker-compose logs mcp-comfyui
    pause
    exit /b 1
)

echo.
echo ========================================
echo ComfyUI is starting up...
echo ========================================
echo.
echo Services:
echo   Web UI:     http://localhost:8188
echo   MCP Server: http://localhost:8013
echo.

REM Wait a bit for services to initialize
echo Waiting for services to initialize...
timeout /t 15 /nobreak >nul

REM Open the web UI in default browser
echo Opening ComfyUI Web UI in your browser...
start http://localhost:8188

echo.
echo ========================================
echo ComfyUI is running!
echo ========================================
echo.
echo Commands:
echo   View logs:  docker-compose logs -f mcp-comfyui
echo   Stop:       docker-compose --profile ai-services stop mcp-comfyui
echo   Restart:    docker-compose --profile ai-services restart mcp-comfyui
echo.
echo Press any key to view logs (Ctrl+C to exit logs)...
pause >nul

REM Show logs
docker-compose logs -f mcp-comfyui
