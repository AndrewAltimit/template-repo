@echo off
REM Import Sleeper Detection Database to Docker Container
REM Imports SQL dump into the sleeper-results Docker volume

setlocal EnableDelayedExpansion

echo =========================================
echo Sleeper Detection Database Import
echo To Docker Container
echo =========================================
echo.

REM Default values
set "CONTAINER_NAME=sleeper-dashboard"
set "DB_PATH=/results/evaluation_results.db"
set "SQL_FILE="
set "BACKUP_EXISTING=true"

REM Parse arguments
:parse_args
if "%~1"=="" goto validate_args
if /i "%~1"=="--container" (
    set "CONTAINER_NAME=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--sql-file" (
    set "SQL_FILE=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--no-backup" (
    set "BACKUP_EXISTING=false"
    shift
    goto parse_args
)
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="--help" goto show_help

echo Unknown option: %~1
echo Use -h or --help for usage information
exit /b 1

:show_help
echo Usage: %~nx0 --sql-file FILE [OPTIONS]
echo.
echo Imports an SQL dump file into the evaluation results database in a Docker container.
echo.
echo Required:
echo   --sql-file FILE      SQL dump file to import
echo.
echo Options:
echo   --container NAME     Container name (default: sleeper-dashboard)
echo   --no-backup          Skip backing up existing database
echo   -h, --help          Show this help message
echo.
echo Examples:
echo   %~nx0 --sql-file db_exports\evaluation_results_20250101_120000.sql
echo   %~nx0 --sql-file export.sql --container my-dashboard
echo   %~nx0 --sql-file export.sql --no-backup
exit /b 0

:validate_args
if "%SQL_FILE%"=="" (
    echo ERROR: --sql-file is required
    echo Use -h or --help for usage information
    exit /b 1
)

echo [1/4] Checking SQL file...

if not exist "%SQL_FILE%" (
    echo ERROR: SQL file not found: %SQL_FILE%
    exit /b 1
)

for %%A in ("%SQL_FILE%") do set "SQL_SIZE=%%~zA"
set /a "SQL_SIZE_KB=%SQL_SIZE%/1024"
echo SQL file found: %SQL_FILE%
echo SQL file size: !SQL_SIZE_KB! KB
echo.

echo [2/4] Checking container...

REM Check if Docker is available
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker not found. Please install Docker Desktop.
    exit /b 1
)

REM Check if container is running
docker ps --filter "name=%CONTAINER_NAME%" --format "{{.Names}}" | findstr /C:"%CONTAINER_NAME%" >nul
if %ERRORLEVEL% NEQ 0 (
    echo Container '%CONTAINER_NAME%' is not running. Starting it now...
    echo.

    REM Find and run start script (same logic as export script)
    set "START_SCRIPT="
    set "SEARCH_DIR=%CD%"
    :find_import_start_loop
    if exist "!SEARCH_DIR!\packages\sleeper_detection\dashboard\start.bat" (
        set "START_SCRIPT=!SEARCH_DIR!\packages\sleeper_detection\dashboard\start.bat"
        goto found_import_start
    )
    if exist "!SEARCH_DIR!\dashboard\start.bat" (
        set "START_SCRIPT=!SEARCH_DIR!\dashboard\start.bat"
        goto found_import_start
    )
    for %%I in ("!SEARCH_DIR!\..") do set "SEARCH_DIR=%%~fI"
    if "!SEARCH_DIR:~-1!"==":" goto find_import_start_done
    goto find_import_start_loop
    :find_import_start_done
    :found_import_start

    if "!START_SCRIPT!"=="" (
        echo ERROR: Could not find dashboard start.bat script
        exit /b 1
    )

    call "!START_SCRIPT!" >nul 2>&1
    timeout /t 10 /nobreak >nul
)

echo Container '%CONTAINER_NAME%' is running.
echo.

echo [3/4] Backup and import...

if "%BACKUP_EXISTING%"=="true" (
    REM Check if database exists and backup
    docker exec %CONTAINER_NAME% test -f %DB_PATH% 2>nul
    if %ERRORLEVEL% EQU 0 (
        for /f "tokens=1-4 delims=/ " %%a in ('date /t') do (set DATESTR=%%c%%a%%b)
        for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set TIMESTR=%%a%%b)
        set "BACKUP_PATH=%DB_PATH%.backup.!DATESTR!_!TIMESTR!"
        echo Creating backup in container: !BACKUP_PATH!
        docker exec %CONTAINER_NAME% cp %DB_PATH% !BACKUP_PATH!
    )
)

echo Importing database...
REM Import SQL file into container
type "%SQL_FILE%" | docker exec -i %CONTAINER_NAME% sqlite3 %DB_PATH%

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to import database
    exit /b 1
)

echo Import completed.
echo.

echo [4/4] Verifying import...

REM Verify database exists
docker exec %CONTAINER_NAME% test -f %DB_PATH%
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Database not found after import
    exit /b 1
)

echo.
echo =========================================
echo Import Complete!
echo =========================================
echo.
echo Database location (in container): %DB_PATH%
echo Container name: %CONTAINER_NAME%
echo.
echo The dashboard can now use the imported data.
echo Access at: http://localhost:8501
echo.

endlocal
