@echo off
REM Import Sleeper Detection Database
REM Imports SQL dump from another machine into local evaluation results database

setlocal EnableDelayedExpansion

echo =========================================
echo Sleeper Detection Database Import
echo =========================================
echo.

REM Default values
REM Auto-detect database location by searching up directory tree
set "DB_PATH="
set "SEARCH_DIR=%CD%"

REM Try to find packages\sleeper_detection\dashboard\evaluation_results.db
:find_import_db_loop
if exist "%SEARCH_DIR%\packages\sleeper_detection\dashboard\evaluation_results.db" (
    set "DB_PATH=%SEARCH_DIR%\packages\sleeper_detection\dashboard\evaluation_results.db"
    goto found_import_db
)
if exist "%SEARCH_DIR%\dashboard\evaluation_results.db" (
    set "DB_PATH=%SEARCH_DIR%\dashboard\evaluation_results.db"
    goto found_import_db
)
REM Move up one directory
for %%I in ("%SEARCH_DIR%\..") do set "SEARCH_DIR=%%~fI"
REM Stop if we reached root
if "%SEARCH_DIR:~-1%"==":" goto find_import_db_done
if "%SEARCH_DIR%"=="%SEARCH_DIR:~0,3%" goto find_import_db_done
goto find_import_db_loop

:find_import_db_done
REM Fallback to container path
set "DB_PATH=\results\evaluation_results.db"

:found_import_db
set "SQL_FILE="
set "BACKUP_EXISTING=true"
set "MERGE_MODE=false"

REM Parse arguments
:parse_args
if "%~1"=="" goto validate_args
if /i "%~1"=="--db-path" (
    set "DB_PATH=%~2"
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
if /i "%~1"=="--merge" (
    set "MERGE_MODE=true"
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
echo Required:
echo   --sql-file FILE      SQL dump file to import
echo.
echo Options:
echo   --db-path PATH       Target database path (default: auto-detect)
echo   --no-backup          Skip backing up existing database
echo   --merge              Merge with existing data instead of replacing
echo   -h, --help          Show this help message
echo.
echo Database auto-detection:
echo   - Searches up directory tree for packages\sleeper_detection\dashboard\evaluation_results.db
echo   - Also checks for dashboard\evaluation_results.db (if in sleeper_detection dir)
echo   - Falls back to \results\evaluation_results.db (container volume)
echo.
echo Examples:
echo   %~nx0 --sql-file db_exports\evaluation_results_20250101_120000.sql
echo   %~nx0 --sql-file export.sql --db-path D:\custom\path\results.db
echo   %~nx0 --sql-file export.sql --merge --no-backup
exit /b 0

:validate_args
if "%SQL_FILE%"=="" (
    echo ERROR: --sql-file is required
    echo Use -h or --help for usage information
    exit /b 1
)

echo [1/5] Checking SQL file...

REM Check if SQL file exists
if not exist "%SQL_FILE%" (
    echo ERROR: SQL file not found: %SQL_FILE%
    exit /b 1
)

echo SQL file found: %SQL_FILE%
for %%A in ("%SQL_FILE%") do set "SQL_SIZE=%%~zA"
set /a "SQL_SIZE_KB=%SQL_SIZE%/1024"
echo SQL file size: %SQL_SIZE_KB% KB

REM Quick validation of SQL file
findstr /C:"CREATE TABLE" "%SQL_FILE%" >nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: SQL file may not contain table definitions
    set /p "response=Continue anyway? (y/N): "
    if /i not "!response!"=="y" (
        echo Import cancelled
        exit /b 1
    )
)
echo.

echo [2/5] Checking target database...

REM Check if sqlite3 is available
where sqlite3 >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: sqlite3 not found in PATH
    echo Please install SQLite from https://www.sqlite.org/download.html
    echo Or ensure sqlite3.exe is in your PATH
    exit /b 1
)

REM Check if target database exists
set "DB_EXISTS=false"
if exist "%DB_PATH%" (
    set "DB_EXISTS=true"
    for %%A in ("%DB_PATH%") do set "DB_SIZE=%%~zA"
    set /a "DB_SIZE_KB=!DB_SIZE!/1024"
    echo Existing database found: %DB_PATH%
    echo Existing database size: !DB_SIZE_KB! KB

    REM Count existing records
    echo Existing data:
    for /f "delims=" %%T in ('sqlite3 "%DB_PATH%" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;" 2^>nul') do (
        for /f %%C in ('sqlite3 "%DB_PATH%" "SELECT COUNT(*) FROM %%T;" 2^>nul') do (
            echo   - %%T: %%C records
        )
    )
) else (
    echo No existing database found ^(will create new^)
)
echo.

echo [3/5] Backup and preparation...

set "BACKUP_FILE="
if "%DB_EXISTS%"=="true" (
    if "%BACKUP_EXISTING%"=="true" (
        for /f "tokens=1-4 delims=/ " %%a in ('date /t') do (set DATESTR=%%c%%a%%b)
        for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set TIMESTR=%%a%%b)
        set "BACKUP_FILE=%DB_PATH%.backup.!DATESTR!_!TIMESTR!"
        echo Creating backup: !BACKUP_FILE!
        copy "%DB_PATH%" "!BACKUP_FILE!" >nul
        echo Backup created successfully

        if "%MERGE_MODE%"=="false" (
            echo Removing existing database ^(replace mode^)
            del "%DB_PATH%"
        )
    ) else if "%MERGE_MODE%"=="false" (
        echo WARNING: Existing database will be replaced without backup
        set /p "response=Continue? (y/N): "
        if /i not "!response!"=="y" (
            echo Import cancelled
            exit /b 1
        )
        del "%DB_PATH%"
    )
)

REM Create parent directory if needed
if not exist "%DB_PATH%\.." mkdir "%DB_PATH%\.."
echo.

echo [4/5] Importing database...

if "%MERGE_MODE%"=="true" (
    echo Merge mode: Importing into existing database
    echo WARNING: Duplicate primary keys may cause import errors
    sqlite3 "%DB_PATH%" < "%SQL_FILE%" 2>nul
) else (
    echo Replace mode: Creating fresh database
    sqlite3 "%DB_PATH%" < "%SQL_FILE%"
)

if %ERRORLEVEL% NEQ 0 (
    if "%MERGE_MODE%"=="false" (
        echo ERROR: Import failed

        REM Restore backup if exists
        if not "!BACKUP_FILE!"=="" (
            if exist "!BACKUP_FILE!" (
                echo Restoring backup...
                move /y "!BACKUP_FILE!" "%DB_PATH%" >nul
                echo Backup restored
            )
        )
        exit /b 1
    ) else (
        echo Import completed with warnings ^(merge mode^)
    )
) else (
    echo Import completed
)
echo.

echo [5/5] Verifying import...

REM Verify import
for %%A in ("%DB_PATH%") do set "NEW_SIZE=%%~zA"
set /a "NEW_SIZE_KB=!NEW_SIZE!/1024"
echo New database size: !NEW_SIZE_KB! KB
echo.
echo Imported data:
for /f "delims=" %%T in ('sqlite3 "%DB_PATH%" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"') do (
    for /f %%C in ('sqlite3 "%DB_PATH%" "SELECT COUNT(*) FROM %%T;"') do (
        echo   - %%T: %%C records
    )
)
echo.

echo =========================================
echo Import Complete!
echo =========================================
echo.
echo Database location: %DB_PATH%
if not "%BACKUP_FILE%"=="" (
    echo Backup location: !BACKUP_FILE!
)
echo.
echo The database is now ready to use with the dashboard
echo.

endlocal
