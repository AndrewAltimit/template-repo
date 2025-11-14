@echo off
REM Helper script to run PyTorch probe GPU tests in Docker
REM Usage: test_pytorch_probe.bat [command]

setlocal enabledelayedexpansion

cd /d "%~dp0..\.."

echo ===========================================================
echo PyTorch Probe GPU Testing
echo ===========================================================

REM Check if nvidia-docker is available
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] nvidia-docker not available or GPU not accessible
    echo [WARNING] This test requires a GPU to run
    echo [WARNING] Falling back to CPU unit tests only
    set GPU_AVAILABLE=false
) else (
    echo [OK] GPU available
    set GPU_AVAILABLE=true
)

REM Parse command
set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=gpu-test

REM Command routing
if "%COMMAND%"=="gpu-test" goto :gputest_handler
if "%COMMAND%"=="unit-test" goto :unittest_handler
if "%COMMAND%"=="all" goto :all_handler
if "%COMMAND%"=="shell" goto :shell_handler
if "%COMMAND%"=="build" goto :build_handler
if "%COMMAND%"=="clean" goto :clean_handler
if "%COMMAND%"=="gpu-info" goto :gpuinfo_handler

REM Unknown command
echo.
echo [WARNING] Unknown command: %COMMAND%
echo.
echo Usage: %~nx0 [command]
echo.
echo Commands:
echo   gpu-test    - Run GPU end-to-end test (default, requires GPU)
echo   unit-test   - Run CPU unit tests (no GPU required)
echo   all         - Run both GPU and CPU tests
echo   shell       - Start interactive shell in container
echo   build       - Build GPU Docker image
echo   clean       - Clean Docker resources
echo   gpu-info    - Show GPU information
exit /b 1

REM ============================================================
REM Command Handlers
REM ============================================================

:gputest_handler
echo.
echo Running PyTorch probe GPU test...
if "!GPU_AVAILABLE!"=="true" (
    docker-compose -f docker\docker-compose.gpu.yml run --rm sleeper-eval-gpu python3 examples/test_pytorch_probe_gpu.py
) else (
    echo [ERROR] GPU not available - cannot run GPU tests
    exit /b 1
)
goto :success

:unittest_handler
echo.
echo Running PyTorch probe unit tests (CPU mode)...
if "!GPU_AVAILABLE!"=="true" (
    docker-compose -f docker\docker-compose.gpu.yml run --rm sleeper-eval-gpu pytest tests/test_torch_probe.py tests/test_probe_factory.py -v
) else (
    echo [INFO] Running locally without GPU
    pytest tests/test_torch_probe.py tests/test_probe_factory.py -v
)
goto :success

:all_handler
echo.
echo Running all PyTorch probe tests...
if "!GPU_AVAILABLE!"=="true" (
    echo [1/2] Running unit tests...
    docker-compose -f docker\docker-compose.gpu.yml run --rm sleeper-eval-gpu pytest tests/test_torch_probe.py tests/test_probe_factory.py -v
    echo.
    echo [2/2] Running GPU end-to-end test...
    docker-compose -f docker\docker-compose.gpu.yml run --rm sleeper-eval-gpu python3 examples/test_pytorch_probe_gpu.py
) else (
    echo [ERROR] GPU not available - cannot run all tests
    exit /b 1
)
goto :success

:shell_handler
echo.
echo Starting interactive shell...
if "!GPU_AVAILABLE!"=="true" (
    docker-compose -f docker\docker-compose.gpu.yml run --rm sleeper-eval-gpu /bin/bash
) else (
    echo [WARNING] GPU not available, starting local shell
    cmd
)
goto :success

:build_handler
echo.
echo Building GPU Docker image...
docker-compose -f docker\docker-compose.gpu.yml build
goto :success

:clean_handler
echo.
echo Cleaning Docker resources...
docker-compose -f docker\docker-compose.gpu.yml down -v
goto :success

:gpuinfo_handler
echo.
echo GPU Information:
if "!GPU_AVAILABLE!"=="true" (
    docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
) else (
    echo [WARNING] GPU not available
)
goto :success

:success
echo.
echo [OK] Complete
exit /b 0
