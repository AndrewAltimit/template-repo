@echo off
REM Helper script to run GPU evaluations in Docker
REM Usage: run_gpu_eval.bat [command]

setlocal enabledelayedexpansion

cd /d "%~dp0.."

echo ===========================================================
echo Sleeper Detection - GPU Evaluation
echo ===========================================================

REM Check if nvidia-docker is available
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] nvidia-docker not available or GPU not accessible
    echo [WARNING] Falling back to CPU mode
    set GPU_AVAILABLE=false
) else (
    echo [OK] GPU available
    set GPU_AVAILABLE=true
)

REM Parse command
set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=validate

if "%COMMAND%"=="validate" (
    echo.
    echo Running Phase 1 validation...
    if "!GPU_AVAILABLE!"=="true" (
        docker-compose -f docker/docker-compose.gpu.yml run --rm validate
    ) else (
        python scripts/validate_phase1.py
    )
    goto :end
)

if "%COMMAND%"=="test" (
    echo.
    echo Running model management tests...
    if "!GPU_AVAILABLE!"=="true" (
        docker-compose -f docker/docker-compose.gpu.yml run --rm evaluate
    ) else (
        python scripts/test_model_management.py
    )
    goto :end
)

if "%COMMAND%"=="download" (
    set MODEL=%2
    if "!MODEL!"=="" set MODEL=gpt2
    echo.
    echo Downloading model: !MODEL!
    if "!GPU_AVAILABLE!"=="true" (
        docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu python3 -c "from models import ModelDownloader; dl = ModelDownloader(); dl.download('!MODEL!', show_progress=True)"
    ) else (
        python -c "from models import ModelDownloader; dl = ModelDownloader(); dl.download('!MODEL!', show_progress=True)"
    )
    goto :end
)

if "%COMMAND%"=="shell" (
    echo.
    echo Starting interactive shell...
    if "!GPU_AVAILABLE!"=="true" (
        docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu /bin/bash
    ) else (
        echo [WARNING] GPU not available, starting local shell
        cmd
    )
    goto :end
)

if "%COMMAND%"=="build" (
    echo.
    echo Building GPU Docker image...
    docker-compose -f docker/docker-compose.gpu.yml build
    goto :end
)

if "%COMMAND%"=="clean" (
    echo.
    echo Cleaning Docker resources...
    docker-compose -f docker/docker-compose.gpu.yml down -v
    goto :end
)

if "%COMMAND%"=="gpu-info" (
    echo.
    echo GPU Information:
    if "!GPU_AVAILABLE!"=="true" (
        docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
    ) else (
        echo [WARNING] GPU not available
    )
    goto :end
)

REM Unknown command
echo [WARNING] Unknown command: %COMMAND%
echo.
echo Usage: %~nx0 [command]
echo.
echo Commands:
echo   validate    - Run Phase 1 validation (default)
echo   test        - Run model management tests
echo   download    - Download a model (usage: %~nx0 download [model_id])
echo   shell       - Start interactive shell in container
echo   build       - Build GPU Docker image
echo   clean       - Clean Docker resources
echo   gpu-info    - Show GPU information
exit /b 1

:end
echo.
echo [OK] Complete
