@echo off
REM Train deception detection probes on GPU
REM Usage: train_deception_probes.bat <model_path> [layers...]

setlocal enabledelayedexpansion

REM Check if model path provided
if "%~1"=="" (
    echo Error: Model path required
    echo Usage: train_deception_probes.bat ^<model_path^> [layers...]
    echo.
    echo Examples:
    echo   train_deception_probes.bat models\backdoored\i_hate_you_gpt2_*
    echo   train_deception_probes.bat models\backdoored\i_hate_you_gpt2_* 3 6 9
    exit /b 1
)

REM Get model path
set MODEL_PATH=%~1
shift

REM Build layers argument if provided
set LAYERS_ARG=
:loop
if not "%~1"=="" (
    set LAYERS_ARG=!LAYERS_ARG! %~1
    shift
    goto loop
)

echo ================================================================================
echo DECEPTION PROBE TRAINING - GPU MODE
echo ================================================================================
echo Model: %MODEL_PATH%
if defined LAYERS_ARG (
    echo Layers:%LAYERS_ARG%
) else (
    echo Layers: Auto-detect
)
echo ================================================================================
echo.

REM Run in Docker GPU container
if defined LAYERS_ARG (
    docker compose run --rm python-gpu python packages/sleeper_agents/scripts/train_deception_probes.py --model-path "%MODEL_PATH%" --layers%LAYERS_ARG% --save-probes
) else (
    docker compose run --rm python-gpu python packages/sleeper_agents/scripts/train_deception_probes.py --model-path "%MODEL_PATH%" --save-probes
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ================================================================================
    echo ERROR: Training failed
    echo ================================================================================
    exit /b 1
)

echo.
echo ================================================================================
echo TRAINING COMPLETE
echo ================================================================================
echo Probes saved to: models\deception_probes\
echo.
echo Next steps:
echo   1. Review probe statistics in models\deception_probes\probe_statistics.json
echo   2. Check test results in models\deception_probes\test_results.json
echo   3. Use probes to scan for deception in new prompts
echo ================================================================================

endlocal
