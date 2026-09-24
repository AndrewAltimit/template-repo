@echo off
REM Cross-architecture trigger-string separability check (Windows)
REM Runs validation in Docker container for consistency

setlocal

REM CRITICAL: Save script directory BEFORE any argument parsing
REM The shift command in argument parsing will modify %0
set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%~f0

echo ================================================================================
echo Cross-Architecture Check: Linear Separability of a Trigger String
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
REM Navigate from script location to repo root
REM From: packages\sleeper_agents\scripts\testing\
REM To: repo root (4 levels up)
cd /d "%SCRIPT_DIR%"
cd ..\..\..\..

if not exist docker-compose.yml (
    echo ERROR: docker-compose.yml not found in %CD%
    echo ERROR: Script directory was: %SCRIPT_DIR%
    echo ERROR: Current directory is: %CD%
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker Desktop.
    exit /b 1
)

echo Building Python CI container...
docker compose -f docker-compose.yml build python-ci
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
    docker compose -f docker-compose.yml run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] --quiet && python packages/sleeper_agents/examples/cross_architecture_validation.py --quick --device %DEVICE%"
) else (
    echo Running FULL validation ^(all models: %MODELS%^)...
    echo Installing dependencies and running test...
    echo.
    docker compose -f docker-compose.yml run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] --quiet && python packages/sleeper_agents/examples/cross_architecture_validation.py --models %MODELS% --device %DEVICE% --n-train 200 --n-test 100"
)

if errorlevel 1 (
    echo.
    echo ================================================================================
    echo CHECK FAILED ^(the script exited with an error^)
    echo ================================================================================
    exit /b 1
) else (
    echo.
    echo ================================================================================
    echo CHECK COMPLETE ^(see the summary above^)
    echo ================================================================================
)

echo.
echo How to read the summary:
echo   - The models are unmodified pretrained checkpoints; no backdoor is trained.
echo   - Compare each held-out AUC with the shuffled-label ^(~0.5^) and length-only controls.
echo   - Held-out AUC well above both controls: the trigger string is linearly
echo     decodable from that architecture's activations.
echo   - This does not show that backdoored models or backdoored behavior can be detected.
echo.

exit /b 0
