@echo off
REM Host GPU Setup and Testing Script
REM Run this on the Windows host with WSL2 and RTX 4090

setlocal enabledelayedexpansion

echo ===========================================================
echo Sleeper Detection - Host GPU Setup
echo ===========================================================

REM Step 1: Check prerequisites
echo.
echo Step 1: Checking Prerequisites

REM Check Docker
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker not found
    echo Please install Docker Desktop for Windows with WSL2 backend
    exit /b 1
) else (
    echo [OK] Docker installed
    docker --version
)

REM Check nvidia-docker
echo.
echo Checking NVIDIA Docker support...
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] NVIDIA Docker runtime not available
    echo.
    echo To enable GPU support in Docker:
    echo 1. Install NVIDIA drivers for Windows
    echo 2. Install NVIDIA Container Toolkit:
    echo    https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
    echo 3. Ensure Docker Desktop WSL2 backend is enabled
    exit /b 1
) else (
    echo [OK] NVIDIA Docker runtime available
)

REM Step 2: Show GPU info
echo.
echo Step 2: GPU Information
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi

REM Step 3: Build GPU image
echo.
echo Step 3: Building GPU Docker Image
REM Navigate up 3 levels from scripts\setup\gpu\ to sleeper_agents\
cd /d "%~dp0..\..\..\"
docker-compose -f docker/docker-compose.gpu.yml build

REM Step 4: Run validation
echo.
echo Step 4: Running Foundation Validation on GPU
docker-compose -f docker/docker-compose.gpu.yml run --rm validate

REM Step 5: Test resource detection
echo.
echo Step 5: Testing Resource Detection
docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu python3 -c "from models import get_resource_manager; rm = get_resource_manager(); rm.print_system_info(); print('\n=== RTX 4090 Compatibility ==='); from models import get_registry; registry = get_registry(); [print(f'{model.short_name:20} {rm.recommend_quantization(model.estimated_vram_gb).value:8} batch={rm.get_optimal_batch_size(model.estimated_vram_gb)}') for model in registry.list_rtx4090_compatible()]"

REM Step 6: Download a test model
echo.
echo Step 6: Test Model Download
set /p REPLY="Download gpt2 model for testing? (y/n) "
if /i "!REPLY!"=="y" (
    docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu python3 -c "from models import ModelDownloader; dl = ModelDownloader(); path, quant = dl.download_with_fallback('gpt2', max_vram_gb=24.0, show_progress=True); print(f'\nDownloaded to: {path}'); print(f'Quantization: {quant or \"none\"}')"
)

echo.
echo ===========================================================
echo GPU Setup Complete!
echo ===========================================================
echo.
echo Next steps:
echo   1. Run evaluations: scripts\run_gpu_eval.bat test
echo   2. Download models: scripts\run_gpu_eval.bat download mistral-7b
echo   3. Interactive shell: scripts\run_gpu_eval.bat shell
echo.
echo The GPU container is ready for model inference (Real Model Inference)
