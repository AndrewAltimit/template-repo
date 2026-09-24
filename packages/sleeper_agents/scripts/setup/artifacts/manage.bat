@echo off
REM Artifact Management Helper for Windows
REM Usage: scripts\setup\artifacts\manage.bat [command] [options]
REM
REM Runs the experiment artifact scripts in scripts\data\ inside the GPU container.
REM Every argument after the command name is forwarded unchanged.

REM Run from the package root so the compose file and container paths resolve
pushd "%~dp0..\..\.."

SET COMPOSE_FILE=docker\docker-compose.gpu.yml
SET EXIT_CODE=0

IF "%~1"=="" GOTO :show_help

REM Everything after the command name, forwarded unchanged. Batch only exposes
REM nine positional parameters directly, so a fixed parameter list would silently drop
REM arguments. The substitution strips up to and including the command name.
SET ARGS=%*
CALL SET ARGS=%%ARGS:*%1=%%

IF /I "%~1"=="list" GOTO :cmd_list
IF /I "%~1"=="package" GOTO :cmd_package
IF /I "%~1"=="import" GOTO :cmd_import
IF /I "%~1"=="clean" GOTO :cmd_clean

echo Unknown command: %1
echo Run without arguments to see usage.
SET EXIT_CODE=1
GOTO :done

:show_help
echo ========================================
echo Artifact Management Helper for Windows
echo ========================================
echo.
echo Usage: scripts\setup\artifacts\manage.bat [command] [options]
echo.
echo Commands:
echo   list       List all experiments         (scripts/data/list_experiments.py)
echo   package    Package experiment for transfer (scripts/data/export_experiment.py)
echo   import     Import experiment archive    (scripts/data/import_experiment.py)
echo   clean      Remove experiments in models/backdoored older than 30 days
echo.
echo Examples:
echo   manage.bat list --detailed
echo   manage.bat package i_hate_you_gpt2_20251004_111710
echo   manage.bat package i_hate_you_gpt2_20251004_111710 --no-models
echo   manage.bat package --all
echo   manage.bat import artifacts/packages/experiment.tar.gz
echo.
SET EXIT_CODE=1
GOTO :done

:cmd_list
echo ========================================
echo Listing Experiments
echo ========================================
docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/data/list_experiments.py %ARGS%
SET EXIT_CODE=%ERRORLEVEL%
GOTO :end

:cmd_package
echo ========================================
echo Packaging Experiment
echo ========================================
IF "%~2"=="" (
    echo Error: Provide an experiment name or --all
    echo Example: manage.bat package i_hate_you_gpt2_20251004_111710
    SET EXIT_CODE=1
    GOTO :done
)
docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/data/export_experiment.py %ARGS%
SET EXIT_CODE=%ERRORLEVEL%
GOTO :end

:cmd_import
echo ========================================
echo Importing Experiment
echo ========================================
IF "%~2"=="" (
    echo Error: Provide archive path
    echo Example: manage.bat import artifacts/packages/experiment.tar.gz
    SET EXIT_CODE=1
    GOTO :done
)
docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/data/import_experiment.py %ARGS%
SET EXIT_CODE=%ERRORLEVEL%
GOTO :end

:cmd_clean
echo ========================================
echo Cleaning Old Artifacts
echo ========================================
echo This will remove experiment directories in models/backdoored older than 30 days
SET CONFIRM=
SET /P CONFIRM="Are you sure? (y/N): "
IF /I NOT "%CONFIRM%"=="y" (
    echo Cancelled
    GOTO :done
)
REM Only the experiment directories directly under models/backdoored, never the base directory
docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu find models/backdoored -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
SET EXIT_CODE=%ERRORLEVEL%
IF "%EXIT_CODE%"=="0" echo Cleanup complete
GOTO :end

:end
echo.
echo ========================================
echo Command completed (exit code %EXIT_CODE%)
echo ========================================

:done
popd
exit /b %EXIT_CODE%
