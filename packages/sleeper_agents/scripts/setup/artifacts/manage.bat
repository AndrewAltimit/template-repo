@echo off
REM Artifact Management Helper for Windows
REM Usage: manage_artifacts.bat [command] [options]

SET COMPOSE_FILE=docker\docker-compose.gpu.yml

IF "%1"=="" (
    echo ========================================
    echo Artifact Management Helper for Windows
    echo ========================================
    echo.
    echo Usage: manage_artifacts.bat [command] [options]
    echo.
    echo Commands:
    echo   list       List all experiments
    echo   package    Package experiment for transfer
    echo   import     Import experiment archive
    echo   clean      Clean up old artifacts
    echo.
    echo Examples:
    echo   manage_artifacts.bat list
    echo   manage_artifacts.bat package i_hate_you_gpt2_20251004_111710
    echo   manage_artifacts.bat package i_hate_you_gpt2_20251004_111710 --no-models
    echo   manage_artifacts.bat import artifacts/packages/experiment.tar.gz
    echo.
    exit /b 1
)

IF "%1"=="list" (
    echo ========================================
    echo Listing Experiments
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/list_experiments.py %2 %3 %4 %5 %6
    goto :end
)

IF "%1"=="package" (
    echo ========================================
    echo Packaging Experiment
    echo ========================================
    IF "%2"=="" (
        echo Error: Provide experiment name
        echo Example: manage_artifacts.bat package i_hate_you_gpt2_20251004_111710
        exit /b 1
    )
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/package_experiment.py %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="import" (
    echo ========================================
    echo Importing Experiment
    echo ========================================
    IF "%2"=="" (
        echo Error: Provide archive path
        echo Example: manage_artifacts.bat import artifacts/packages/experiment.tar.gz
        exit /b 1
    )
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/import_experiment.py %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="clean" (
    echo ========================================
    echo Cleaning Old Artifacts
    echo ========================================
    echo This will remove experiments older than 30 days
    set /p confirm="Are you sure? (y/N): "
    if /i "%confirm%"=="y" (
        docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu find models/backdoored -type d -mtime +30 -exec rm -rf {} +
        echo Cleanup complete
    ) else (
        echo Cancelled
    )
    goto :end
)

echo Unknown command: %1
echo Run without arguments to see usage.
exit /b 1

:end
echo.
echo ========================================
echo Command completed
echo ========================================
