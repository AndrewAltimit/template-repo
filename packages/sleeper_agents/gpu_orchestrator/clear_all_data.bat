@echo off
REM Comprehensive Data Cleanup Script for Sleeper Agents GPU Orchestrator
REM This script removes ALL data including evaluation results, models, logs, and databases
REM WARNING: This is irreversible! Make backups if needed.

echo =========================================
echo Sleeper Agents - Complete Data Cleanup
echo =========================================
echo.
echo WARNING: This will DELETE ALL:
echo - Evaluation databases (evaluation_results.db, users.db, orchestrator.db)
echo - Model checkpoints and caches
echo - Validation results (outputs/, results/)
echo - Training checkpoints
echo - Logs and temporary files
echo - Docker volumes
echo.
set /p CONFIRM="Are you sure you want to proceed? (yes/no): "
if /i not "%CONFIRM%"=="yes" (
    echo Cleanup cancelled.
    exit /b 0
)

echo.
echo Starting cleanup...
echo.

REM Navigate to package root (one level up from gpu_orchestrator)
cd /d %~dp0
cd ..

REM ========================================
REM 1. Stop all Docker containers
REM ========================================
echo [1/10] Stopping Docker containers...
docker stop sleeper-gpu-worker 2>nul
docker stop sleeper-orchestrator-api 2>nul
echo Containers stopped.

REM ========================================
REM 2. Remove Docker volumes
REM ========================================
echo [2/10] Removing Docker volumes...
echo   This is where evaluation_results.db actually lives!

REM Remove specific named volumes (from docker-compose.gpu.yml)
docker volume rm sleeper-results 2>nul
if %errorlevel% equ 0 (
    echo   - Removed sleeper-results volume ^(contains /results/evaluation_results.db^)
) else (
    echo   - sleeper-results volume not found or already removed
)

docker volume rm sleeper-models 2>nul
if %errorlevel% equ 0 (
    echo   - Removed sleeper-models volume ^(contains model cache^)
) else (
    echo   - sleeper-models volume not found or already removed
)

docker volume rm sleeper-gpu-cache 2>nul
if %errorlevel% equ 0 (
    echo   - Removed sleeper-gpu-cache volume
) else (
    echo   - sleeper-gpu-cache volume not found or already removed
)

REM Remove any other sleeper-related volumes
for /f "tokens=2" %%v in ('docker volume ls ^| findstr sleeper') do (
    docker volume rm %%v 2>nul
    if %errorlevel% equ 0 echo   - Removed additional volume: %%v
)

echo Docker volumes removed.

REM ========================================
REM 3. Remove evaluation databases
REM ========================================
echo [3/10] Removing evaluation databases...

REM Main evaluation database (dashboard)
if exist "dashboard\evaluation_results.db" (
    del /f /q "dashboard\evaluation_results.db"
    echo   - Deleted dashboard\evaluation_results.db
)

REM Mock database
if exist "dashboard\evaluation_results_mock.db" (
    del /f /q "dashboard\evaluation_results_mock.db"
    echo   - Deleted dashboard\evaluation_results_mock.db
)

REM Test database
if exist "dashboard\tests\test_evaluation_results.db" (
    del /f /q "dashboard\tests\test_evaluation_results.db"
    echo   - Deleted dashboard\tests\test_evaluation_results.db
)

REM Orchestrator databases
if exist "gpu_orchestrator\users.db" (
    del /f /q "gpu_orchestrator\users.db"
    echo   - Deleted gpu_orchestrator\users.db
)

if exist "gpu_orchestrator\orchestrator.db" (
    del /f /q "gpu_orchestrator\orchestrator.db"
    echo   - Deleted gpu_orchestrator\orchestrator.db
)

echo Databases removed.

REM ========================================
REM 4. Remove results directory
REM ========================================
echo [4/10] Removing results directory...
if exist "results" (
    rmdir /s /q "results"
    echo   - Deleted results\
)

REM Also check for /results in current drive root (Docker mount point)
if exist "\results" (
    rmdir /s /q "\results"
    echo   - Deleted \results\
)

REM ========================================
REM 5. Remove outputs directory
REM ========================================
echo [5/10] Removing outputs directory...
if exist "outputs" (
    rmdir /s /q "outputs"
    echo   - Deleted outputs\
)

REM ========================================
REM 6. Remove model caches
REM ========================================
echo [6/10] Removing model caches...
if exist "models" (
    rmdir /s /q "models"
    echo   - Deleted models\
)

REM HuggingFace cache (in user directory)
if exist "%USERPROFILE%\.cache\huggingface" (
    echo   - Found HuggingFace cache: %USERPROFILE%\.cache\huggingface
    set /p CLEAR_HF="    Clear HuggingFace cache? (yes/no): "
    if /i "!CLEAR_HF!"=="yes" (
        rmdir /s /q "%USERPROFILE%\.cache\huggingface"
        echo   - Deleted HuggingFace cache
    )
)

REM ========================================
REM 7. Remove training checkpoints
REM ========================================
echo [7/10] Removing training checkpoints...
if exist "checkpoints" (
    rmdir /s /q "checkpoints"
    echo   - Deleted checkpoints\
)

REM ========================================
REM 8. Remove logs
REM ========================================
echo [8/10] Removing logs...
if exist "logs" (
    rmdir /s /q "logs"
    echo   - Deleted logs\
)

if exist "gpu_orchestrator\logs" (
    rmdir /s /q "gpu_orchestrator\logs"
    echo   - Deleted gpu_orchestrator\logs\
)

REM Remove any .log files
del /s /q *.log 2>nul

REM ========================================
REM 9. Remove Python cache
REM ========================================
echo [9/10] Removing Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
for /d /r . %%d in (.pytest_cache) do @if exist "%%d" rmdir /s /q "%%d"
for /d /r . %%d in (.mypy_cache) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q *.pyc 2>nul
echo Python cache removed.

REM ========================================
REM 10. Remove temporary files
REM ========================================
echo [10/10] Removing temporary files...
if exist "temp" (
    rmdir /s /q "temp"
    echo   - Deleted temp\
)

if exist "tmp" (
    rmdir /s /q "tmp"
    echo   - Deleted tmp\
)

REM Remove wandb artifacts (experiment tracking)
if exist "wandb" (
    rmdir /s /q "wandb"
    echo   - Deleted wandb\
)

if exist ".wandb" (
    rmdir /s /q ".wandb"
    echo   - Deleted .wandb\
)

REM ========================================
REM Summary
REM ========================================
echo.
echo =========================================
echo Cleanup Complete!
echo =========================================
echo.
echo All data has been removed. The following were cleaned:
echo   [x] Evaluation databases (evaluation_results.db, users.db, orchestrator.db)
echo   [x] Docker volumes (sleeper-results, sleeper-models, sleeper-logs)
echo   [x] Results directory (results/, outputs/)
echo   [x] Model caches (models/, checkpoints/)
echo   [x] Logs (logs/, *.log)
echo   [x] Python cache (__pycache__, .pytest_cache, .mypy_cache)
echo   [x] Temporary files (temp/, tmp/, wandb/)
echo.
echo You can now run .\start_orchestrator.bat to start fresh.
echo.
pause
