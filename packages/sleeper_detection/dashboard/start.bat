@echo off
REM Smart Dashboard Starter - Uses docker-compose if available, falls back to docker
REM Automatically loads .env and configures everything

echo =========================================
echo Sleeper Detection Dashboard Startup
echo =========================================
echo.

REM Check Docker is installed and running
echo [1/6] Checking Docker...
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker not found. Please install Docker Desktop.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker daemon not running. Please start Docker Desktop.
    exit /b 1
)
echo Docker is running.

REM Check for docker-compose
echo [2/6] Detecting docker-compose...
set "USE_COMPOSE=0"
where docker-compose >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "USE_COMPOSE=1"
    echo Found docker-compose: will use docker-compose.yml
) else (
    REM Check for docker compose (v2 syntax)
    docker compose version >nul 2>&1
    if not errorlevel 1 (
        set "USE_COMPOSE=2"
        echo Found docker compose v2: will use docker-compose.yml
    ) else (
        echo docker-compose not found: will use docker run
    )
)
echo.

REM Load environment variables
echo [3/6] Loading configuration...
if not exist .env (
    if exist .env.example (
        echo Creating .env from .env.example...
        copy .env.example .env
        echo.
        echo IMPORTANT: Please edit .env and configure:
        echo   - GPU_API_URL=http://your-gpu-machine-ip:8000
        echo   - GPU_API_KEY=your-api-key
        echo   - DASHBOARD_ADMIN_PASSWORD=your-password
        echo.
        pause
    ) else (
        echo ERROR: No .env or .env.example found
        exit /b 1
    )
)

REM Load .env file
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    REM Skip comments and empty lines
    if not "!line:~0,1!"=="#" (
        if not "%%a"=="" (
            if not "%%b"=="" (
                set "%%a=%%b"
            )
        )
    )
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
    set "DASHBOARD_ADMIN_PASSWORD=admin123"
)

echo Configuration loaded successfully.
echo.

REM Check/build image
echo [4/6] Checking Docker image...
docker image inspect sleeper-dashboard:latest >nul 2>&1
if errorlevel 1 (
    echo Building dashboard image (this may take 2-5 minutes)...
    docker build -t sleeper-dashboard:latest .
    if errorlevel 1 (
        echo ERROR: Failed to build image
        exit /b 1
    )
)
echo.

REM Stop existing container/service
echo [5/6] Stopping existing dashboard...
if %USE_COMPOSE% EQU 1 (
    docker-compose down >nul 2>&1
) else if %USE_COMPOSE% EQU 2 (
    docker compose down >nul 2>&1
) else (
    docker stop sleeper-dashboard >nul 2>&1
    docker rm sleeper-dashboard >nul 2>&1
)
echo.

REM Start dashboard
echo [6/6] Starting dashboard...
echo.

if %USE_COMPOSE% EQU 1 (
    echo Using docker-compose...
    docker-compose up -d
    if errorlevel 1 goto :error
) else if %USE_COMPOSE% EQU 2 (
    echo Using docker compose v2...
    docker compose up -d
    if errorlevel 1 goto :error
) else (
    echo Using docker run...
    docker run -d ^
      --name sleeper-dashboard ^
      -p 8501:8501 ^
      -e GPU_API_URL=%GPU_API_URL% ^
      -e GPU_API_KEY=%GPU_API_KEY% ^
      -e DASHBOARD_ADMIN_PASSWORD=%DASHBOARD_ADMIN_PASSWORD% ^
      sleeper-dashboard:latest
    if errorlevel 1 goto :error
)

REM Wait for startup
timeout /t 3 /nobreak >nul

REM Verify running
docker ps | findstr sleeper-dashboard >nul
if errorlevel 1 (
    echo ERROR: Container not running after startup
    echo.
    echo Logs:
    docker logs sleeper-dashboard
    exit /b 1
)

echo.
echo =========================================
echo Dashboard Started Successfully!
echo =========================================
echo.
echo Access the dashboard at:
echo   - Local: http://localhost:8501
echo.
echo Login:
echo   - Username: admin
echo   - Password: (from .env DASHBOARD_ADMIN_PASSWORD)
echo.
echo GPU Orchestrator: %GPU_API_URL%
echo.
echo Management:
echo   - View logs: docker logs -f sleeper-dashboard
echo   - Stop: docker stop sleeper-dashboard
if %USE_COMPOSE% GTR 0 (
    if %USE_COMPOSE% EQU 1 (
        echo   - Or use: docker-compose down
    ) else (
        echo   - Or use: docker compose down
    )
)
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul
start http://localhost:8501
echo.
echo Dashboard is running. Close this window or press Ctrl+C to stop viewing logs.
echo.

REM Follow logs
docker logs -f sleeper-dashboard
goto :eof

:error
echo.
echo ERROR: Failed to start dashboard
echo.
echo Troubleshooting:
echo   1. Check if port 8501 is in use: netstat -ano ^| findstr :8501
echo   2. View logs: docker logs sleeper-dashboard
echo   3. Check .env configuration
echo   4. Verify GPU Orchestrator API is accessible
exit /b 1
