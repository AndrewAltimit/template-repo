@echo off
REM Start Gaea2 MCP Server on Windows
REM This script starts the Gaea2 MCP server with optional Gaea2 path

echo ========================================
echo Gaea2 MCP Server Launcher
echo ========================================
echo.

REM Navigate to repository root (3 levels up from this script)
cd /d "%~dp0\..\..\..\"

REM Check if GAEA2_PATH is set, try to auto-detect if not
if "%GAEA2_PATH%"=="" (
    REM Try common installation paths
    if exist "C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe" (
        set "GAEA2_PATH=C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe"
        echo Auto-detected Gaea2 at: %GAEA2_PATH%
    ) else if exist "C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe" (
        set "GAEA2_PATH=C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe"
        echo Auto-detected Gaea2 at: %GAEA2_PATH%
    ) else if exist "D:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe" (
        set "GAEA2_PATH=D:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe"
        echo Auto-detected Gaea2 at: %GAEA2_PATH%
    ) else (
        echo WARNING: GAEA2_PATH not set and Gaea2 not found in common locations
        echo CLI automation features will be disabled
        echo.
        echo To enable CLI features, set GAEA2_PATH to your Gaea.Swarm.exe location:
        echo   set GAEA2_PATH="C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe"
    )
    echo.
) else (
    echo Using Gaea2 at: %GAEA2_PATH%
    echo.
)

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.10+ and add it to PATH
    pause
    exit /b 1
)

REM Check if mcp_core package is installed (dependency)
python -c "import mcp_core" >nul 2>&1
if errorlevel 1 (
    echo Installing mcp_core package...
    pip install -e tools\mcp\mcp_core -q
    if errorlevel 1 (
        echo ERROR: Failed to install mcp_core package
        pause
        exit /b 1
    )
)

REM Check if mcp_gaea2 package is installed
python -c "import mcp_gaea2" >nul 2>&1
if errorlevel 1 (
    echo Installing mcp_gaea2 package...
    pip install -e tools\mcp\mcp_gaea2 -q
    if errorlevel 1 (
        echo ERROR: Failed to install mcp_gaea2 package
        pause
        exit /b 1
    )
    echo Packages installed successfully.
    echo.
)

REM Set output directory to a Windows-friendly path
if "%GAEA2_OUTPUT_DIR%"=="" (
    set "GAEA2_OUTPUT_DIR=%USERPROFILE%\gaea2_output"
)
if not exist "%GAEA2_OUTPUT_DIR%" mkdir "%GAEA2_OUTPUT_DIR%"

REM Start the server
echo Starting server on http://0.0.0.0:8007
echo Output directory: %GAEA2_OUTPUT_DIR%
echo Press Ctrl+C to stop the server
echo.

python -m mcp_gaea2.server --mode http --port 8007 --output-dir "%GAEA2_OUTPUT_DIR%" %*

pause
