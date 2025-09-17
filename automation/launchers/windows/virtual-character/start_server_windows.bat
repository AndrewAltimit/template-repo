@echo off
REM Virtual Character MCP Server with Storage Service
REM Unified launcher for AI agent embodiment platform
REM Supports VRChat, Unity, Unreal, Blender backends

setlocal enabledelayedexpansion

echo ============================================
echo Virtual Character Platform
echo ============================================
echo.

REM Default configuration
set PORT=8020
set HOST=0.0.0.0
set STORAGE_PORT=8021
set BACKEND_HOST=127.0.0.1
set NO_STORAGE=0

REM Parse command line arguments
:parse_args
if "%~1"=="" goto end_parse
if /i "%~1"=="--port" (
    set PORT=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--host" (
    set HOST=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--backend-host" (
    set BACKEND_HOST=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--storage-port" (
    set STORAGE_PORT=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--no-storage" (
    set NO_STORAGE=1
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    goto show_help
)
shift
goto parse_args
:end_parse

REM Show help if requested
:show_help_check
if "%1"=="--help" (
    :show_help
    echo Usage: start_server_windows.bat [options]
    echo.
    echo Options:
    echo   --port PORT          MCP server port (default: 8020)
    echo   --host HOST          MCP server host (default: 0.0.0.0)
    echo   --backend-host HOST  Backend host for VRChat/Unity (default: 127.0.0.1)
    echo   --storage-port PORT  Storage service port (default: 8021)
    echo   --no-storage         Disable storage service
    echo   --help               Show this help message
    echo.
    echo Example:
    echo   start_server_windows.bat --port 8020 --backend-host 192.168.1.100
    exit /b 0
)

REM Get script directory (4 levels up from script location)
set SCRIPT_DIR=%~dp0
pushd %SCRIPT_DIR%..\..\..\..\
set REPO_ROOT=%CD%
popd

REM Load environment variables from .env file if it exists
set ENV_FILE=%REPO_ROOT%\.env
if exist "%ENV_FILE%" (
    echo Loading environment from .env file...
    for /f "tokens=1,2 delims==" %%a in (%ENV_FILE%) do (
        REM Skip comments and empty lines
        set line=%%a
        if not "!line:~0,1!"=="#" if not "%%a"=="" (
            set %%a=%%b
        )
    )
    echo Environment loaded
    echo.
)

REM Check for storage secret key
if "%STORAGE_SECRET_KEY%"=="" (
    echo WARNING: STORAGE_SECRET_KEY not set in .env file
    echo Generating temporary key for this session...

    REM Generate a random key (simplified for batch)
    set CHARS=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789
    set KEY=
    for /l %%i in (1,1,32) do (
        set /a RND=!RANDOM! %% 62
        for %%j in (!RND!) do set KEY=!KEY!!CHARS:~%%j,1!
    )
    set STORAGE_SECRET_KEY=!KEY!
    echo Temporary key generated (will not persist)
    echo.
)

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python: %PYTHON_VERSION%

echo.
echo Configuration:
echo   MCP Server: http://%HOST%:%PORT%
echo   Backend Host: %BACKEND_HOST%
if "%NO_STORAGE%"=="0" (
    echo   Storage Service: http://localhost:%STORAGE_PORT%
)
echo.

REM Set environment variables
set VRCHAT_HOST=%BACKEND_HOST%
set VRCHAT_USE_VRCEMOTE=true
set VRCHAT_USE_BRIDGE=true
set VRCHAT_BRIDGE_PORT=%PORT%
set MCP_SERVER_PORT=%PORT%
set STORAGE_PORT=%STORAGE_PORT%
set STORAGE_HOST=0.0.0.0
set STORAGE_BASE_URL=http://localhost:%STORAGE_PORT%
set VIRTUAL_CHARACTER_SERVER=http://%HOST%:%PORT%

REM Check and install dependencies
echo Checking dependencies...
call :check_package pythonosc "python-osc"
call :check_package fastapi "fastapi uvicorn[standard] python-multipart"
call :check_package aiohttp "aiohttp"
call :check_package requests "requests"

REM Navigate to repo root
cd /d %REPO_ROOT%

REM Start storage service if not disabled
if "%NO_STORAGE%"=="0" (
    echo.
    echo Starting Storage Service...

    REM Create storage directory
    if not exist "%TEMP%\audio_storage" mkdir "%TEMP%\audio_storage"

    REM Start storage service in new window
    start "Virtual Character Storage" /min cmd /c python tools\mcp\virtual_character\storage_service\server.py

    REM Wait for storage service to start
    timeout /t 2 /nobreak >nul

    REM Check if storage service is running
    curl -s http://localhost:%STORAGE_PORT%/health >nul 2>&1
    if errorlevel 1 (
        echo Warning: Storage service may not be running properly
        echo Continuing without storage service...
    ) else (
        echo Storage Service started at http://localhost:%STORAGE_PORT%
    )
)

echo.
echo Starting Virtual Character MCP Server...
echo Server will be available at http://%HOST%:%PORT%
echo.
echo Platform Support:
echo   - VRChat (OSC protocol)
echo   - Unity (WebSocket - coming soon)
echo   - Unreal Engine (HTTP API - coming soon)
echo   - Blender (Python API - coming soon)
echo.
echo Available Endpoints:
echo   POST /set_backend       - Connect to platform backend
echo   POST /send_animation    - Send animation data
echo   POST /execute_behavior  - Execute behaviors
echo   POST /audio/play        - Play audio with storage support
echo   POST /create_sequence   - Create event sequences
echo   GET  /get_backend_status - Get backend status
echo.

if "%NO_STORAGE%"=="0" (
    echo Storage Service Endpoints:
    echo   POST http://localhost:%STORAGE_PORT%/upload - Upload files
    echo   GET  http://localhost:%STORAGE_PORT%/download/^<id^> - Download files
    echo   GET  http://localhost:%STORAGE_PORT%/health - Service health
    echo.
)

echo Press Ctrl+C to stop the servers
echo ============================================
echo.

REM Start the MCP server
python -m tools.mcp.virtual_character.server --port %PORT% --host %HOST% --mode http

REM Cleanup on exit
if "%NO_STORAGE%"=="0" (
    echo.
    echo Stopping storage service...
    taskkill /FI "WindowTitle eq Virtual Character Storage*" /F >nul 2>&1
)

pause
exit /b 0

REM Function to check and install packages
:check_package
python -c "import %~1" >nul 2>&1
if errorlevel 1 (
    echo   Installing %~2...
    pip install --user %~2 >nul 2>&1
    if errorlevel 1 (
        echo   Warning: Failed to install %~2. Trying without --user flag...
        pip install %~2 >nul 2>&1
    )
) else (
    echo   √ %~1 installed
)
exit /b 0
