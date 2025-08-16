@echo off
REM Start AI Toolkit Full Application (Web UI + MCP Server) in Docker
REM Automatically opens the web UI in your default browser

echo ========================================
echo AI Toolkit Full Application Launcher
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

echo Building AI Toolkit container...
echo This may take a while on first run or after updates
docker-compose build mcp-ai-toolkit

echo.
echo Starting AI Toolkit container...
docker-compose --profile ai-services up -d mcp-ai-toolkit

REM Check if the container started successfully
docker ps | findstr ai-toolkit >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to start AI Toolkit container
    echo Check Docker Desktop and try again
    docker-compose logs mcp-ai-toolkit
    pause
    exit /b 1
)

echo.
echo ========================================
echo AI Toolkit is starting up...
echo ========================================
echo.
echo Services:
echo   Web UI:     http://localhost:7860
echo   MCP Server: http://localhost:8012
echo.

REM Wait a bit for services to initialize
echo Waiting for services to initialize...
timeout /t 10 /nobreak >nul

REM Open the web UI in default browser
echo Opening AI Toolkit Web UI in your browser...
start http://localhost:7860

echo.
echo ========================================
echo AI Toolkit is running!
echo ========================================
echo.
echo Commands:
echo   View logs:  docker-compose logs -f mcp-ai-toolkit
echo   Stop:       docker-compose --profile ai-services stop mcp-ai-toolkit
echo   Restart:    docker-compose --profile ai-services restart mcp-ai-toolkit
echo.
echo Press any key to view logs (Ctrl+C to exit logs)...
pause >nul

REM Show logs
docker-compose logs -f mcp-ai-toolkit
