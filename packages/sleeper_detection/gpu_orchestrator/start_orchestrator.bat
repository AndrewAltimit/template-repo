@echo off
REM Start GPU Orchestrator API
REM This script should run on the Windows GPU machine

echo =========================================
echo GPU Orchestrator API Startup
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
docker info >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker daemon not running. Please start Docker Desktop.
    exit /b 1
)

REM Check NVIDIA GPU
where nvidia-smi >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: nvidia-smi not found. GPU may not be available.
) else (
    echo GPU detected:
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
)

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found. Please install Python 3.8+.
    exit /b 1
)

echo [2/5] Setting up environment...

REM Create .env if it doesn't exist
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo WARNING: Please edit .env and set your API_KEY!
)

REM Create virtual environment if it doesn't exist
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo [3/5] Installing dependencies...
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

REM Check Docker image
echo [4/5] Checking Docker image...
docker image inspect sleeper-detection:gpu >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: sleeper-detection:gpu image not found.
    echo You need to build it first. Run:
    echo   cd ..\..
    echo   docker build -t sleeper-detection:gpu -f docker\Dockerfile.gpu .
    echo.
    echo Continuing anyway (API will start but jobs will fail)...
)

REM Get IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do set IP=%%a
set IP=%IP:~1%

REM Start API
echo [5/5] Starting GPU Orchestrator API...
echo.
echo API will be available at:
echo   - Local: http://localhost:8000
echo   - Network: http://%IP%:8000
echo   - Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo.

REM Run with uvicorn
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level info
