@echo off
REM Sleeper Agent Detection - Windows GPU Launcher
REM For use with RTX 4090 or other NVIDIA GPUs

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
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: NVIDIA Docker support not available
    echo Please ensure:
    echo   1. NVIDIA drivers are installed
    echo   2. Docker Desktop has WSL2 backend enabled
    echo   3. NVIDIA Container Toolkit is installed
    pause
    exit /b 1
)

echo [OK] Docker and GPU support detected
echo.

REM Set environment variables
set SLEEPER_CPU_MODE=false
set SLEEPER_DEVICE=cuda
set CUDA_VISIBLE_DEVICES=0

REM Navigate to project root
cd /d "%~dp0\..\..\..\"

echo Building Docker image...
docker compose build sleeper-eval-gpu

if %errorlevel% neq 0 (
    echo ERROR: Failed to build Docker image
    pause
    exit /b 1
)

echo.
echo Starting Sleeper Detection with GPU support...
echo.
echo Services will be available at:
echo   - Main API: http://localhost:8021
echo   - Dashboard: http://localhost:8022
echo   - Monitoring: http://localhost:8023
echo   - Vector DB: http://localhost:8024
echo.

REM Start the GPU-enabled service
docker compose --profile eval-gpu up sleeper-eval-gpu sleeper-vectordb

pause
