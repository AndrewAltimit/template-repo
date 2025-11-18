@echo off
REM Phase 3D Cross-Architecture Validation Test Script (Windows)
REM Runs validation in Docker container for consistency

setlocal

echo ================================================================================
echo Phase 3D: Cross-Architecture Method Validation Test
echo ================================================================================
echo.

REM Parse command line arguments
set MODE=quick
set MODELS=gpt2
set DEVICE=cpu

:parse_args
if "%1"=="" goto end_parse
if /i "%1"=="--full" (
    set MODE=full
    set MODELS=gpt2 llama3 mistral qwen
    shift
    goto parse_args
)
if /i "%1"=="--gpu" (
    set DEVICE=cuda
    shift
    goto parse_args
)
if /i "%1"=="--models" (
    shift
    set MODELS=%1
    shift
    goto parse_args
)
shift
goto parse_args
:end_parse

echo Configuration:
echo   Mode: %MODE%
echo   Models: %MODELS%
echo   Device: %DEVICE%
echo.

REM Change to repo root
REM Path: scripts/testing -> scripts -> sleeper_agents -> packages -> repo_root
cd /d %~dp0\..\..\..\..
echo Current directory: %CD%
echo Looking for docker-compose.yml...
if not exist docker-compose.yml (
    echo ERROR: docker-compose.yml not found in %CD%
    echo Expected to be in repo root
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker Desktop.
    exit /b 1
)

echo Building Python CI container...
docker-compose -f docker-compose.yml build python-ci
if errorlevel 1 (
    echo ERROR: Failed to build container
    exit /b 1
)
echo.

REM Run test based on mode
REM Note: Install package and run test in same container to persist dependencies
if "%MODE%"=="quick" (
    echo Running QUICK test ^(GPT-2 only, 50 samples^)...
    echo Installing dependencies and running test...
    echo.
    docker-compose -f docker-compose.yml run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] --quiet && python packages/sleeper_agents/examples/phase3d_cross_architecture_validation.py --quick --device %DEVICE%"
) else (
    echo Running FULL validation ^(all models: %MODELS%^)...
    echo Installing dependencies and running test...
    echo.
    docker-compose -f docker-compose.yml run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] --quiet && python packages/sleeper_agents/examples/phase3d_cross_architecture_validation.py --models %MODELS% --device %DEVICE% --n-train 200 --n-test 100"
)

if errorlevel 1 (
    echo.
    echo ================================================================================
    echo TEST FAILED
    echo ================================================================================
    exit /b 1
) else (
    echo.
    echo ================================================================================
    echo TEST PASSED
    echo ================================================================================
)

echo.
echo Interpretation Guide:
echo   - AUC at least 0.9 on all models: SUCCESS ^(method generalizes^)
echo   - AUC 0.7-0.9: PARTIAL ^(needs tuning^)
echo   - AUC below 0.7: FAILURE ^(architecture-specific quirks^)
echo.

exit /b 0
