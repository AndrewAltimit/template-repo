@echo off
REM Export Sleeper Detection Database from Docker Container
REM Extracts evaluation_results.db from the sleeper-results Docker volume

setlocal EnableDelayedExpansion

echo =========================================
echo Sleeper Detection Database Export
echo From Docker Container
echo =========================================
echo.

REM Default values
set "CONTAINER_NAME=sleeper-dashboard"
set "DB_PATH=/results/evaluation_results.db"
set "OUTPUT_DIR=.\db_exports"
for /f "tokens=1-4 delims=/ " %%a in ('date /t') do (set DATESTR=%%c%%a%%b)
for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set TIMESTR=%%a%%b)
set "TIMESTAMP=%DATESTR%_%TIMESTR%"
set "OUTPUT_FILE=%OUTPUT_DIR%\evaluation_results_%TIMESTAMP%.sql"

REM Parse arguments
:parse_args
if "%~1"=="" goto check_docker
if /i "%~1"=="--container" (
    set "CONTAINER_NAME=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--output-dir" (
    set "OUTPUT_DIR=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--output-file" (
    set "OUTPUT_FILE=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="--help" goto show_help

echo Unknown option: %~1
echo Use -h or --help for usage information
exit /b 1

:show_help
echo Usage: %~nx0 [OPTIONS]
echo.
echo Exports the evaluation results database from a running Docker container.
echo.
echo Options:
echo   --container NAME     Container name (default: sleeper-dashboard)
echo   --output-dir DIR     Output directory (default: .\db_exports)
echo   --output-file FILE   Output file path (overrides --output-dir)
echo   -h, --help          Show this help message
echo.
echo Examples:
echo   %~nx0
echo   %~nx0 --container my-dashboard
echo   %~nx0 --output-dir D:\backups
exit /b 0

:check_docker
echo [1/5] Checking Docker...

REM Check if Docker is available
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker not found. Please install Docker Desktop.
    exit /b 1
)

echo Docker found.
echo.

echo [2/5] Checking container...

REM Check if container is running
docker ps --filter "name=%CONTAINER_NAME%" --format "{{.Names}}" | findstr /C:"%CONTAINER_NAME%" >nul
if %ERRORLEVEL% NEQ 0 (
    echo Container '%CONTAINER_NAME%' is not running. Starting it now...
    echo.

    REM Find and run start script
    set "START_SCRIPT="
    if exist "..\..\dashboard\start.bat" (
        set "START_SCRIPT=..\..\dashboard\start.bat"
    ) else if exist "..\..\..\dashboard\start.bat" (
        set "START_SCRIPT=..\..\..\dashboard\start.bat"
    ) else (
        REM Search up directory tree
        set "SEARCH_DIR=%CD%"
        :find_start_loop
        if exist "!SEARCH_DIR!\packages\sleeper_detection\dashboard\start.bat" (
            set "START_SCRIPT=!SEARCH_DIR!\packages\sleeper_detection\dashboard\start.bat"
            goto found_start
        )
        if exist "!SEARCH_DIR!\dashboard\start.bat" (
            set "START_SCRIPT=!SEARCH_DIR!\dashboard\start.bat"
            goto found_start
        )
        for %%I in ("!SEARCH_DIR!\..") do set "SEARCH_DIR=%%~fI"
        if "!SEARCH_DIR:~-1!"==":" goto find_start_done
        if "!SEARCH_DIR!"=="!SEARCH_DIR:~0,3!" goto find_start_done
        goto find_start_loop
        :find_start_done
    )
    :found_start

    if "!START_SCRIPT!"=="" (
        echo ERROR: Could not find dashboard start.bat script
        echo.
        echo Please start the dashboard manually:
        echo   cd packages\sleeper_detection\dashboard
        echo   start.bat
        exit /b 1
    )

    echo Found start script: !START_SCRIPT!
    echo Starting dashboard container...
    call "!START_SCRIPT!" >nul 2>&1

    REM Wait a few seconds for container to start
    echo Waiting for container to start...
    timeout /t 10 /nobreak >nul

    REM Verify container is now running
    docker ps --filter "name=%CONTAINER_NAME%" --format "{{.Names}}" | findstr /C:"%CONTAINER_NAME%" >nul
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to start container '%CONTAINER_NAME%'
        echo Please check the dashboard logs for errors.
        exit /b 1
    )

    echo Container started successfully.
)

echo Container '%CONTAINER_NAME%' is running.
echo.

echo [3/5] Checking database in container...

REM Check if database exists in container
docker exec %CONTAINER_NAME% test -f %DB_PATH% 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Database not found in container at %DB_PATH%
    echo.
    echo The database may not have been created yet.
    echo Run an evaluation job first to create the database.
    exit /b 1
)

REM Get database size
for /f %%s in ('docker exec %CONTAINER_NAME% stat -c %%s %DB_PATH% 2^>nul') do set DB_SIZE=%%s
set /a "DB_SIZE_KB=!DB_SIZE!/1024"
echo Database found in container: %DB_PATH%
echo Database size: !DB_SIZE_KB! KB
echo.

echo [4/5] Exporting database...

REM Create output directory
if not exist "%OUTPUT_FILE%\.." mkdir "%OUTPUT_FILE%\.."

REM Export database to SQL dump using docker exec
echo Dumping database to SQL...
docker exec %CONTAINER_NAME% sqlite3 %DB_PATH% .dump > "%OUTPUT_FILE%"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to export database
    exit /b 1
)

echo Export completed.
echo.

echo [5/5] Verifying export...

if not exist "%OUTPUT_FILE%" (
    echo ERROR: Export file not created
    exit /b 1
)

for %%A in ("%OUTPUT_FILE%") do set "EXPORT_SIZE=%%~zA"
set /a "EXPORT_SIZE_KB=!EXPORT_SIZE!/1024"

echo.
echo =========================================
echo Export Complete!
echo =========================================
echo.
echo Export file: %OUTPUT_FILE%
echo Export size: !EXPORT_SIZE_KB! KB
echo.
echo To import on another machine:
echo   1. Copy the file to the other machine
echo   2. Run: import_db_to_container.bat --sql-file %OUTPUT_FILE%
echo.
echo Or to view locally:
echo   sqlite3 "%OUTPUT_FILE%"
echo.

endlocal
