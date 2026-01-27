@echo off
REM Smart Dashboard Starter - Uses docker compose if available, falls back to docker
REM Automatically loads .env and configures everything

REM Parse command-line flags
set "FOLLOW_LOGS=true"
if "%~1"=="--no-logs" set "FOLLOW_LOGS=false"

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
where docker compose >nul 2>nul
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
        echo docker compose not found: will use docker run
    )
)
echo.

REM Check configuration
echo [3/6] Checking configuration...
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

echo [3a/7] Creating data directories...
REM Create data directories for volume mounts
if not exist auth mkdir auth
if not exist data mkdir data
echo Directories ensured.
echo.

echo Configuration file found: .env
echo Note: docker compose will load environment variables from .env
echo.

REM Ensure required Docker volumes exist
echo [4/7] Checking Docker volumes...
docker volume inspect sleeper-results >nul 2>&1
if errorlevel 1 (
    echo Creating sleeper-results volume...
    docker volume create sleeper-results
    if errorlevel 1 (
        echo ERROR: Failed to create sleeper-results volume
        exit /b 1
    )
    echo Created sleeper-results volume
) else (
    echo Volume sleeper-results already exists
)
echo.

REM Build image
echo [5/7] Building Docker image...
if %USE_COMPOSE% EQU 1 (
    echo Building with docker-compose...
    docker compose build
    if errorlevel 1 (
        echo ERROR: Failed to build image
        exit /b 1
    )
) else if %USE_COMPOSE% EQU 2 (
    echo Building with docker compose...
    docker compose build
    if errorlevel 1 (
        echo ERROR: Failed to build image
        exit /b 1
    )
) else (
    echo Building with docker...
    docker build -t sleeper-dashboard:latest .
    if errorlevel 1 (
        echo ERROR: Failed to build image
        exit /b 1
    )
)
echo.

REM Stop existing container/service
echo [6/7] Stopping existing dashboard...
if %USE_COMPOSE% EQU 1 (
    docker compose down >nul 2>&1
) else if %USE_COMPOSE% EQU 2 (
    docker compose down >nul 2>&1
) else (
    docker stop sleeper-dashboard >nul 2>&1
    docker rm sleeper-dashboard >nul 2>&1
)
echo.

REM Start dashboard
echo [7/7] Starting dashboard...
echo.

REM Set default user permissions if not in .env (Windows doesn't have id command)
REM These defaults ensure consistent behavior across docker compose and docker run paths
if not defined USER_ID set "USER_ID=1000"
if not defined GROUP_ID set "GROUP_ID=1000"

if %USE_COMPOSE% EQU 1 (
    echo Using docker-compose...
    docker compose up -d
    if errorlevel 1 goto :error
) else if %USE_COMPOSE% EQU 2 (
    echo Using docker compose v2...
    docker compose up -d
    if errorlevel 1 goto :error
) else (
    echo Using docker run...
    echo Note: Loading environment variables from .env for docker run...
    REM Load .env only for docker run case
    for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
        if not "%%a"=="" set "%%a=%%b"
    )
    docker run -d ^
      --user %USER_ID%:%GROUP_ID% ^
      --name sleeper-dashboard ^
      -p 8501:8501 ^
      --env-file .env ^
      -v sleeper-results:/results:rw ^
      -v ./auth:/home/dashboard/app/auth ^
      -v ./data:/home/dashboard/app/data ^
      sleeper-dashboard:latest
    if errorlevel 1 goto :error
)

REM Wait for startup with polling
echo Waiting for container to be ready...
set WAIT_COUNT=0
:wait_startup_loop
docker ps --filter "name=sleeper-dashboard" --format "{{.Names}}" | findstr /C:"sleeper-dashboard" >nul
if %ERRORLEVEL% EQU 0 (
    echo Container is ready.
    goto startup_complete
)
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 30 (
    echo ERROR: Container failed to become ready within 60 seconds.
    echo.
    echo Recent container logs:
    docker logs --tail 30 sleeper-dashboard 2^>^&1
    if errorlevel 1 echo Could not retrieve logs
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_startup_loop

:startup_complete

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
echo GPU Orchestrator: (configured in .env GPU_API_URL)
echo.
echo Management:
echo   - View logs: docker logs -f sleeper-dashboard
echo   - Stop: docker stop sleeper-dashboard
if %USE_COMPOSE% GTR 0 (
    if %USE_COMPOSE% EQU 1 (
        echo   - Or use: docker compose down
    ) else (
        echo   - Or use: docker compose down
    )
)
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul
start http://localhost:8501
echo.

if "%FOLLOW_LOGS%"=="true" (
    echo Dashboard is running. Close this window or press Ctrl+C to stop viewing logs.
    echo.
    REM Follow logs
    docker logs -f sleeper-dashboard
) else (
    echo Dashboard is running in the background.
)
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
