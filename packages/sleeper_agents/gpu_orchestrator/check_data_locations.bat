@echo off
REM Diagnostic script to find all data locations
REM Shows where evaluation data, models, and results are stored

echo =========================================
echo Sleeper Agents - Data Location Checker
echo =========================================
echo.
echo This script helps you find all data locations before cleanup.
echo.

cd /d %~dp0
cd ..

echo [1] Docker Volumes
echo ==================
echo.
docker volume ls | findstr sleeper
if %errorlevel% neq 0 (
    echo   No sleeper volumes found
) else (
    echo.
    echo   Inspecting volumes:
    for /f "tokens=2" %%v in ('docker volume ls ^| findstr sleeper') do (
        echo.
        echo   Volume: %%v
        docker volume inspect %%v | findstr "Mountpoint"
    )
)

echo.
echo [2] Docker Containers
echo =====================
echo.
docker ps -a | findstr sleeper
if %errorlevel% neq 0 (
    echo   No sleeper containers found
)

echo.
echo [3] Database Files
echo ==================
echo.
if exist "dashboard\evaluation_results.db" (
    echo   [FOUND] dashboard\evaluation_results.db
    for %%F in ("dashboard\evaluation_results.db") do echo           Size: %%~zF bytes
) else (
    echo   [NOT FOUND] dashboard\evaluation_results.db
)

if exist "dashboard\evaluation_results_mock.db" (
    echo   [FOUND] dashboard\evaluation_results_mock.db
    for %%F in ("dashboard\evaluation_results_mock.db") do echo           Size: %%~zF bytes
) else (
    echo   [NOT FOUND] dashboard\evaluation_results_mock.db
)

if exist "gpu_orchestrator\users.db" (
    echo   [FOUND] gpu_orchestrator\users.db
    for %%F in ("gpu_orchestrator\users.db") do echo           Size: %%~zF bytes
) else (
    echo   [NOT FOUND] gpu_orchestrator\users.db
)

if exist "gpu_orchestrator\orchestrator.db" (
    echo   [FOUND] gpu_orchestrator\orchestrator.db
    for %%F in ("gpu_orchestrator\orchestrator.db") do echo           Size: %%~zF bytes
) else (
    echo   [NOT FOUND] gpu_orchestrator\orchestrator.db
)

echo.
echo [4] Results Directories
echo =======================
echo.
if exist "results" (
    echo   [FOUND] results\
    dir /s /b results 2>nul | find /c /v "" > temp_count.txt
    set /p file_count=<temp_count.txt
    del temp_count.txt
    echo           Files: %file_count%
) else (
    echo   [NOT FOUND] results\
)

if exist "outputs" (
    echo   [FOUND] outputs\
    dir /s /b outputs 2>nul | find /c /v "" > temp_count.txt
    set /p file_count=<temp_count.txt
    del temp_count.txt
    echo           Files: %file_count%
) else (
    echo   [NOT FOUND] outputs\
)

echo.
echo [5] Model Caches
echo ================
echo.
if exist "models" (
    echo   [FOUND] models\
    dir /s /b models 2>nul | find /c /v "" > temp_count.txt
    set /p file_count=<temp_count.txt
    del temp_count.txt
    echo           Files: %file_count%
) else (
    echo   [NOT FOUND] models\
)

if exist "checkpoints" (
    echo   [FOUND] checkpoints\
    dir /s /b checkpoints 2>nul | find /c /v "" > temp_count.txt
    set /p file_count=<temp_count.txt
    del temp_count.txt
    echo           Files: %file_count%
) else (
    echo   [NOT FOUND] checkpoints\
)

if exist "%USERPROFILE%\.cache\huggingface" (
    echo   [FOUND] HuggingFace cache: %USERPROFILE%\.cache\huggingface
) else (
    echo   [NOT FOUND] HuggingFace cache
)

echo.
echo [6] Logs
echo ========
echo.
if exist "logs" (
    echo   [FOUND] logs\
    dir /s /b logs 2>nul | find /c /v "" > temp_count.txt
    set /p file_count=<temp_count.txt
    del temp_count.txt
    echo           Files: %file_count%
) else (
    echo   [NOT FOUND] logs\
)

if exist "gpu_orchestrator\logs" (
    echo   [FOUND] gpu_orchestrator\logs\
    dir /s /b gpu_orchestrator\logs 2>nul | find /c /v "" > temp_count.txt
    set /p file_count=<temp_count.txt
    del temp_count.txt
    echo           Files: %file_count%
) else (
    echo   [NOT FOUND] gpu_orchestrator\logs\
)

echo.
echo =========================================
echo Check Complete
echo =========================================
echo.
echo Key Finding:
echo   If Docker volumes exist (sleeper-results, sleeper-models),
echo   that's where your evaluation_results.db actually lives!
echo   The database path /results/evaluation_results.db points to
echo   the sleeper-results volume.
echo.
echo To clean all data, run: clear_all_data.bat
echo.
pause
