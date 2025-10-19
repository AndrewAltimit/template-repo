@echo off
REM Start Sleeper Detection Dashboard in Docker
REM Automatically loads .env file and starts container

echo =========================================
echo Sleeper Detection Dashboard Startup
echo =========================================
echo.

REM Check prerequisites
echo [1/5] Checking prerequisites...

REM Check Docker
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker not found. Please install Docker Desktop.
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker daemon not running. Please start Docker Desktop.
    exit /b 1
)

echo [2/5] Loading configuration...

REM Create .env if it doesn't exist
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo.
    echo WARNING: Please edit .env and configure:
    echo   - GPU_API_URL (your Windows GPU machine IP)
    echo   - GPU_API_KEY (must match GPU Orchestrator)
    echo   - DASHBOARD_ADMIN_PASSWORD (dashboard login password)
    echo.
    pause
)

REM Load .env file and set environment variables
echo Loading environment variables from .env...
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
    if not "%%a"=="" set "%%a=%%b"
)

REM Verify required variables
if "%GPU_API_URL%"=="" (
    echo ERROR: GPU_API_URL not set in .env
    exit /b 1
)

if "%GPU_API_KEY%"=="" (
    echo ERROR: GPU_API_KEY not set in .env
    exit /b 1
)

if "%DASHBOARD_ADMIN_PASSWORD%"=="" (
    echo WARNING: DASHBOARD_ADMIN_PASSWORD not set, using default
    set "DASHBOARD_ADMIN_PASSWORD=admin123"
)

echo Configuration loaded:
echo   - GPU_API_URL: %GPU_API_URL%
echo   - GPU_API_KEY: [HIDDEN]
echo   - DASHBOARD_ADMIN_PASSWORD: [HIDDEN]
echo.

echo [3/5] Checking Docker image...

REM Check if dashboard image exists
docker image inspect sleeper-dashboard:latest >nul 2>&1
if errorlevel 1 (
    echo Dashboard image not found. Building image...
    echo This will take 2-5 minutes...
    echo.
    docker build -t sleeper-dashboard:latest .
    if errorlevel 1 (
        echo ERROR: Failed to build dashboard image
        exit /b 1
    )
    echo Image built successfully!
) else (
    echo Dashboard image found.
)
echo.

echo [4/5] Stopping existing container (if any)...

REM Stop and remove existing container if it exists
docker stop sleeper-dashboard >nul 2>&1
docker rm sleeper-dashboard >nul 2>&1

echo [5/5] Starting dashboard container...
echo.

REM Start dashboard container with environment variables
docker run -d ^
  --name sleeper-dashboard ^
  -p 8501:8501 ^
  -e GPU_API_URL=%GPU_API_URL% ^
  -e GPU_API_KEY=%GPU_API_KEY% ^
  -e DASHBOARD_ADMIN_PASSWORD=%DASHBOARD_ADMIN_PASSWORD% ^
  sleeper-dashboard:latest

if errorlevel 1 (
    echo ERROR: Failed to start dashboard container
    echo.
    echo Troubleshooting:
    echo   1. Check if port 8501 is already in use
    echo   2. View Docker logs: docker logs sleeper-dashboard
    echo   3. Verify .env configuration
    exit /b 1
)

REM Wait a moment for container to start
timeout /t 3 /nobreak >nul

REM Verify container is running
docker ps | findstr sleeper-dashboard >nul
if errorlevel 1 (
    echo ERROR: Container started but is not running
    echo.
    echo Container logs:
    docker logs sleeper-dashboard
    exit /b 1
)

echo =========================================
echo Dashboard Started Successfully!
echo =========================================
echo.
echo Dashboard is available at:
echo   - Local: http://localhost:8501
echo   - Network: http://%COMPUTERNAME%:8501
echo.
echo Login credentials:
echo   - Username: admin
echo   - Password: [from .env DASHBOARD_ADMIN_PASSWORD]
echo.
echo GPU Orchestrator API:
echo   - Connecting to: %GPU_API_URL%
echo.
echo Container management:
echo   - View logs: docker logs -f sleeper-dashboard
echo   - Stop: docker stop sleeper-dashboard
echo   - Restart: docker restart sleeper-dashboard
echo.
echo Press Ctrl+C to stop following logs, or close window to leave running.
echo.

REM Follow logs
docker logs -f sleeper-dashboard
