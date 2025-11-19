@echo off
REM Phase 3E Gradient Attack Audit Test Script (Windows)
setlocal

REM CRITICAL: Save script directory BEFORE any argument parsing
set SCRIPT_DIR=%~dp0

REM Parse command line arguments
set MODE=quick
set DEVICE=cpu
set EPSILON=0.1

:parse_args
if "%1"=="" goto end_parse
if /i "%1"=="--full" (
    set MODE=full
    shift
    goto parse_args
)
if /i "%1"=="--gpu" (
    set DEVICE=cuda
    shift
    goto parse_args
)
if /i "%1"=="--epsilon" (
    set EPSILON=%2
    shift
    shift
    goto parse_args
)
shift
goto parse_args
:end_parse

REM Navigate from script location to repo root
cd /d "%SCRIPT_DIR%"
cd ..\..\..\..

echo ============================================================
echo Phase 3E: Gradient Attack Audit
echo ============================================================
echo Configuration:
echo   Mode: %MODE%
echo   Device: %DEVICE%
echo   Epsilon: %EPSILON%
echo ============================================================
echo.

REM Run test based on mode
if "%MODE%"=="quick" (
    echo Running QUICK audit ^(50 samples, recommended^)...
    echo Installing dependencies and running audit...
    echo.
    docker-compose -f docker-compose.yml run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] adversarial-robustness-toolbox --quiet && python packages/sleeper_agents/examples/phase3e_gradient_attack_audit.py --quick --device %DEVICE% --epsilon %EPSILON%"
) else (
    echo Running FULL audit ^(100 samples^)...
    echo Installing dependencies and running audit...
    echo.
    docker-compose -f docker-compose.yml run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] adversarial-robustness-toolbox --quiet && python packages/sleeper_agents/examples/phase3e_gradient_attack_audit.py --n-samples 100 --device %DEVICE% --epsilon %EPSILON%"
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo Audit completed successfully!
    echo Results saved to: outputs/phase3e_audit/
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo Audit failed with error code: %ERRORLEVEL%
    echo ============================================================
    exit /b %ERRORLEVEL%
)
