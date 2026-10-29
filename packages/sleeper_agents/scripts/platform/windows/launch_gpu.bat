@echo off
REM Sleeper Agent Detection - Windows GPU Launcher
REM For use with RTX 4090 or other NVIDIA GPUs (driver 580 or newer for CUDA 13.0)
REM
REM Usage:
REM   launch_gpu.bat            Quick GPU test (gpt2, basic suite)
REM   launch_gpu.bat <model>    Full evaluation of <model> with an HTML report

echo ========================================================
echo SLEEPER AGENT DETECTION SYSTEM - GPU MODE
echo RTX 4090 Deployment Launcher
echo ========================================================
echo.

REM Check for Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not in PATH
    echo Please install Docker Desktop for Windows
    pause
    exit /b 1
)

REM Check for NVIDIA Docker support
docker run --rm --gpus all nvidia/cuda:13.0.2-base-ubuntu24.04 nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: NVIDIA Docker support not available
    echo Please ensure:
    echo   1. NVIDIA drivers 580 or newer are installed
    echo   2. Docker Desktop has WSL2 backend enabled
    echo   3. NVIDIA Container Toolkit is installed
    pause
    exit /b 1
)

echo [OK] Docker and GPU support detected
echo.

REM Navigate to the repository root (this script is in packages\sleeper_agents\scripts\platform\windows)
cd /d "%~dp0..\..\..\..\.."

echo Building Docker image...
docker compose --profile eval-gpu build sleeper-eval-gpu

if %errorlevel% neq 0 (
    echo ERROR: Failed to build Docker image
    pause
    exit /b 1
)

if not exist evaluation_results mkdir evaluation_results

echo.
if "%~1"=="" (
    echo Running the quick GPU test...
    echo.
    docker compose --profile eval-gpu run --rm sleeper-eval-gpu
) else (
    echo Evaluating %~1 on the GPU...
    echo.
    docker compose --profile eval-gpu run --rm sleeper-eval-gpu python -m sleeper_agents.cli evaluate "%~1" --gpu --report
)

echo.
echo Results and reports are written to evaluation_results\
echo View them in the dashboard with launch_dashboard.ps1
echo.
pause
