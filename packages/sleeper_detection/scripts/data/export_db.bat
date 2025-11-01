@echo off
REM Export Sleeper Detection Database
REM Creates a portable SQL dump of evaluation results for transfer to other machines

setlocal EnableDelayedExpansion

echo =========================================
echo Sleeper Detection Database Export
echo =========================================
echo.

REM Default values
set "DB_PATH=\results\evaluation_results.db"
set "OUTPUT_DIR=.\db_exports"
for /f "tokens=1-4 delims=/ " %%a in ('date /t') do (set DATESTR=%%c%%a%%b)
for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set TIMESTR=%%a%%b)
set "TIMESTAMP=%DATESTR%_%TIMESTR%"
set "OUTPUT_FILE=%OUTPUT_DIR%\evaluation_results_%TIMESTAMP%.sql"

REM Parse arguments
:parse_args
if "%~1"=="" goto check_db
if /i "%~1"=="--db-path" (
    set "DB_PATH=%~2"
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
echo Options:
echo   --db-path PATH       Path to database file (default: \results\evaluation_results.db)
echo   --output-dir DIR     Output directory (default: .\db_exports)
echo   --output-file FILE   Output file path (overrides --output-dir)
echo   -h, --help          Show this help message
echo.
echo Examples:
echo   %~nx0
echo   %~nx0 --db-path \custom\path\results.db
echo   %~nx0 --output-dir \backup\location
exit /b 0

:check_db
echo [1/4] Checking database...

REM Check if database exists
if not exist "%DB_PATH%" (
    echo ERROR: Database not found at: %DB_PATH%
    echo.
    echo Common locations:
    echo   - \results\evaluation_results.db ^(container volume^)
    echo   - packages\sleeper_detection\dashboard\evaluation_results.db
    echo   - Custom path specified in environment
    exit /b 1
)

echo Database found: %DB_PATH%
for %%A in ("%DB_PATH%") do set "DB_SIZE=%%~zA"
set /a "DB_SIZE_KB=%DB_SIZE%/1024"
echo Database size: %DB_SIZE_KB% KB
echo.

echo [2/4] Analyzing database contents...

REM Check if sqlite3 is available
where sqlite3 >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: sqlite3 not found in PATH
    echo Please install SQLite from https://www.sqlite.org/download.html
    echo Or ensure sqlite3.exe is in your PATH
    exit /b 1
)

REM Count records in each table
echo Tables found:
for /f "delims=" %%T in ('sqlite3 "%DB_PATH%" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"') do (
    for /f %%C in ('sqlite3 "%DB_PATH%" "SELECT COUNT(*) FROM %%T;"') do (
        echo   - %%T: %%C records
    )
)
echo.

echo [3/4] Creating export directory...
if not exist "%OUTPUT_FILE%\.." mkdir "%OUTPUT_FILE%\.."
echo Export will be saved to: %OUTPUT_FILE%
echo.

echo [4/4] Exporting database...

REM Export to SQL dump
sqlite3 "%DB_PATH%" .dump > "%OUTPUT_FILE%"

if %ERRORLEVEL% EQU 0 (
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
    echo   .\scripts\data\import_db.bat --sql-file %OUTPUT_FILE%
    echo.
    echo Or manually:
    echo   sqlite3 \results\evaluation_results.db ^< %OUTPUT_FILE%
    echo.
) else (
    echo.
    echo ERROR: Export failed
    exit /b 1
)

endlocal
