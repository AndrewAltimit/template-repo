@echo off
REM COMPREHENSIVE Data Cleanup for Sleeper Agents
REM Clears BOTH GPU Orchestrator AND Dashboard data
REM This is the COMPLETE solution that removes EVERYTHING

setlocal EnableDelayedExpansion

echo =========================================
echo Sleeper Agents - COMPREHENSIVE Cleanup
echo GPU Orchestrator + Dashboard
echo =========================================
echo.
echo WARNING: This will DELETE ALL:
echo.
echo GPU ORCHESTRATOR:
echo   - orchestrator.db, users.db
echo   - Docker volumes (sleeper-results, sleeper-models, sleeper-gpu-cache)
echo   - Logs and caches
echo.
echo DASHBOARD:
echo   - sleeper-dashboard container
echo   - dashboard/auth/users.db (user accounts)
echo   - dashboard/data/* (local data including users.db)
echo   - evaluation_results.db (in sleeper-results volume)
echo.
echo MODEL DATA:
echo   - Model checkpoints
echo   - Training results (results/, outputs/)
echo   - HuggingFace cache (optional)
echo.
set /p CONFIRM="Are you ABSOLUTELY SURE? Type 'DELETE EVERYTHING' to proceed: "
if /i not "%CONFIRM%"=="DELETE EVERYTHING" (
    echo Cleanup cancelled.
    exit /b 0
)

echo.
echo Starting comprehensive cleanup...
echo.

cd /d %~dp0
cd ..

REM ========================================
REM 1. Stop ALL containers
REM ========================================
echo [1/12] Stopping ALL Docker containers...

REM Stop dashboard
docker stop sleeper-dashboard 2>nul
if %errorlevel% equ 0 (
    echo   - Stopped sleeper-dashboard
    docker rm sleeper-dashboard 2>nul
    echo   - Removed sleeper-dashboard container
)

REM Stop GPU orchestrator
docker stop sleeper-gpu-worker 2>nul
docker stop sleeper-orchestrator-api 2>nul
docker stop sleeper-eval-gpu 2>nul
docker stop sleeper-validate 2>nul
docker stop sleeper-evaluate 2>nul

REM Stop any other sleeper containers
for /f "tokens=1" %%c in ('docker ps -a --filter "name=sleeper" --format "{{.Names}}"') do (
    echo   - Stopping %%c
    docker stop %%c 2>nul
    docker rm %%c 2>nul
)

echo All containers stopped.
echo.

REM ========================================
REM 2. Remove Docker volumes
REM ========================================
echo [2/12] Removing Docker volumes...
echo   This is where evaluation_results.db lives!

REM Remove named volumes
docker volume rm sleeper-results 2>nul
if %errorlevel% equ 0 (
    echo   [✓] Removed sleeper-results (contains /results/evaluation_results.db)
) else (
    echo   [!] sleeper-results not found or already removed
)

docker volume rm sleeper-models 2>nul
if %errorlevel% equ 0 (
    echo   [✓] Removed sleeper-models
) else (
    echo   [!] sleeper-models not found
)

docker volume rm sleeper-gpu-cache 2>nul
if %errorlevel% equ 0 (
    echo   [✓] Removed sleeper-gpu-cache
) else (
    echo   [!] sleeper-gpu-cache not found
)

REM Remove any other sleeper volumes
for /f "tokens=2" %%v in ('docker volume ls ^| findstr sleeper') do (
    docker volume rm %%v 2>nul
    if %errorlevel% equ 0 echo   [✓] Removed additional volume: %%v
)

echo Docker volumes removed.
echo.

REM ========================================
REM 3. Dashboard auth database (NOT the source code!)
REM ========================================
echo [3/12] Removing Dashboard auth database...

REM Only delete the users.db file, NOT the entire auth directory
REM The auth directory contains source code (authentication.py, __init__.py)
if exist "dashboard\auth\users.db" (
    del /f /q "dashboard\auth\users.db"
    echo   [OK] Deleted dashboard\auth\users.db
) else (
    echo   [!] dashboard\auth\users.db not found
)

REM Also check data directory for auth database (new location)
if exist "dashboard\data\users.db" (
    del /f /q "dashboard\data\users.db"
    echo   [OK] Deleted dashboard\data\users.db
) else (
    echo   [!] dashboard\data\users.db not found
)
echo.

REM ========================================
REM 4. Dashboard data directory
REM ========================================
echo [4/12] Removing Dashboard data directory...

if exist "dashboard\data" (
    echo   Found: dashboard\data
    dir /b dashboard\data 2>nul | findstr /r "." >nul
    if not errorlevel 1 (
        echo   Files in data:
        dir /b dashboard\data
        rmdir /s /q "dashboard\data"
        echo   [✓] Deleted dashboard\data\
    ) else (
        echo   [!] Data directory empty
    )
) else (
    echo   [!] dashboard\data not found
)
echo.

REM ========================================
REM 5. GPU Orchestrator databases
REM ========================================
echo [5/12] Removing GPU Orchestrator databases...

if exist "gpu_orchestrator\users.db" (
    del /f /q "gpu_orchestrator\users.db"
    echo   [✓] Deleted gpu_orchestrator\users.db
) else (
    echo   [!] gpu_orchestrator\users.db not found
)

if exist "gpu_orchestrator\orchestrator.db" (
    del /f /q "gpu_orchestrator\orchestrator.db"
    echo   [✓] Deleted gpu_orchestrator\orchestrator.db
) else (
    echo   [!] gpu_orchestrator\orchestrator.db not found
)
echo.

REM ========================================
REM 6. Evaluation databases (local copies)
REM ========================================
echo [6/12] Removing evaluation databases (local copies)...

if exist "dashboard\evaluation_results.db" (
    del /f /q "dashboard\evaluation_results.db"
    echo   [✓] Deleted dashboard\evaluation_results.db
) else (
    echo   [!] dashboard\evaluation_results.db not found
)

if exist "dashboard\evaluation_results_mock.db" (
    del /f /q "dashboard\evaluation_results_mock.db"
    echo   [✓] Deleted dashboard\evaluation_results_mock.db
) else (
    echo   [!] evaluation_results_mock.db not found
)

if exist "dashboard\tests\test_evaluation_results.db" (
    del /f /q "dashboard\tests\test_evaluation_results.db"
    echo   [✓] Deleted dashboard\tests\test_evaluation_results.db
) else (
    echo   [!] test database not found
)
echo.

REM ========================================
REM 7. Results directories
REM ========================================
echo [7/12] Removing results directories...

if exist "results" (
    rmdir /s /q "results"
    echo   [✓] Deleted results\
) else (
    echo   [!] results\ not found
)

if exist "outputs" (
    rmdir /s /q "outputs"
    echo   [✓] Deleted outputs\
) else (
    echo   [!] outputs\ not found
)

REM Check root drive for /results
if exist "\results" (
    rmdir /s /q "\results"
    echo   [✓] Deleted \results\ (root)
)
echo.

REM ========================================
REM 8. Model caches
REM ========================================
echo [8/12] Removing model caches...

if exist "models" (
    rmdir /s /q "models"
    echo   [✓] Deleted models\
) else (
    echo   [!] models\ not found
)

if exist "checkpoints" (
    rmdir /s /q "checkpoints"
    echo   [✓] Deleted checkpoints\
) else (
    echo   [!] checkpoints\ not found
)

REM Optional: HuggingFace cache
if exist "%USERPROFILE%\.cache\huggingface" (
    echo   [?] Found HuggingFace cache: %USERPROFILE%\.cache\huggingface
    set /p CLEAR_HF="    Clear HuggingFace cache? (yes/no): "
    if /i "!CLEAR_HF!"=="yes" (
        rmdir /s /q "%USERPROFILE%\.cache\huggingface"
        echo   [✓] Deleted HuggingFace cache
    ) else (
        echo   [!] Skipped HuggingFace cache
    )
) else (
    echo   [!] HuggingFace cache not found
)
echo.

REM ========================================
REM 9. Logs
REM ========================================
echo [9/12] Removing logs...

if exist "logs" (
    rmdir /s /q "logs"
    echo   [✓] Deleted logs\
)

if exist "gpu_orchestrator\logs" (
    rmdir /s /q "gpu_orchestrator\logs"
    echo   [✓] Deleted gpu_orchestrator\logs\
)

if exist "dashboard\logs" (
    rmdir /s /q "dashboard\logs"
    echo   [✓] Deleted dashboard\logs\
)

del /s /q *.log 2>nul
echo All logs removed.
echo.

REM ========================================
REM 10. Python cache
REM ========================================
echo [10/12] Removing Python cache...

for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
for /d /r . %%d in (.pytest_cache) do @if exist "%%d" rmdir /s /q "%%d"
for /d /r . %%d in (.mypy_cache) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q *.pyc 2>nul
echo Python cache removed.
echo.

REM ========================================
REM 11. Temporary files
REM ========================================
echo [11/12] Removing temporary files...

if exist "temp" (
    rmdir /s /q "temp"
    echo   [✓] Deleted temp\
)

if exist "tmp" (
    rmdir /s /q "tmp"
    echo   [✓] Deleted tmp\
)

if exist "wandb" (
    rmdir /s /q "wandb"
    echo   [✓] Deleted wandb\
)

if exist ".wandb" (
    rmdir /s /q ".wandb"
    echo   [✓] Deleted .wandb\
)
echo.

REM ========================================
REM 12. Database export backups
REM ========================================
echo [12/12] Removing database export backups...

if exist "scripts\data\db_exports" (
    rmdir /s /q "scripts\data\db_exports"
    echo   [✓] Deleted scripts\data\db_exports\
) else (
    echo   [!] db_exports\ not found
)
echo.

REM ========================================
REM Summary
REM ========================================
echo.
echo =========================================
echo Comprehensive Cleanup Complete!
echo =========================================
echo.
echo REMOVED:
echo.
echo Docker:
echo   [x] All sleeper containers (dashboard, GPU worker, orchestrator)
echo   [x] Docker volumes (sleeper-results, sleeper-models, sleeper-gpu-cache)
echo.
echo Databases:
echo   [x] evaluation_results.db (in sleeper-results volume - GONE)
echo   [x] dashboard\auth\users.db (user accounts)
echo   [x] dashboard\data\users.db (user accounts)
echo   [x] gpu_orchestrator\users.db
echo   [x] gpu_orchestrator\orchestrator.db
echo.
echo Data:
echo   [x] results/, outputs/ (validation results)
echo   [x] models/, checkpoints/ (model caches)
echo   [x] logs/ (all log files)
echo   [x] Python cache (__pycache__, .pytest_cache)
echo   [x] Temporary files (temp/, tmp/, wandb/)
echo   [x] Database backups (db_exports/)
echo.
echo Next Steps:
echo   1. cd gpu_orchestrator
echo   2. start_orchestrator.bat    # Start GPU orchestrator fresh
echo   3. cd ..\dashboard
echo   4. start.bat                  # Start dashboard fresh
echo.
echo Everything is now COMPLETELY clean!
echo.
pause

endlocal
