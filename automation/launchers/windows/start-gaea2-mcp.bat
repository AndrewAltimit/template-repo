@echo off
REM Start Gaea2 MCP Server on Windows (Rust version)
REM This script starts the Rust-based Gaea2 MCP server

echo ========================================
echo Gaea2 MCP Server Launcher (Rust)
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

REM Set output directory to a Windows-friendly path
if "%GAEA2_OUTPUT_DIR%"=="" (
    set "GAEA2_OUTPUT_DIR=%USERPROFILE%\gaea2_output"
)
if not exist "%GAEA2_OUTPUT_DIR%" mkdir "%GAEA2_OUTPUT_DIR%"

REM Look for the Rust binary in common locations
set "MCP_BINARY="

REM Check for pre-built release binary
if exist "tools\mcp\mcp_gaea2\target\release\mcp-gaea2.exe" (
    set "MCP_BINARY=tools\mcp\mcp_gaea2\target\release\mcp-gaea2.exe"
    echo Found release binary
) else if exist "rust-binaries\mcp-gaea2-windows-x64.exe" (
    set "MCP_BINARY=rust-binaries\mcp-gaea2-windows-x64.exe"
    echo Found pre-built binary
) else (
    echo Rust binary not found. Building from source...
    echo.

    REM Check if cargo is available
    cargo --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Cargo (Rust) not found in PATH
        echo Please install Rust from https://rustup.rs/ or download a pre-built binary
        pause
        exit /b 1
    )

    REM Build the binary
    echo Building mcp-gaea2...
    cd tools\mcp\mcp_gaea2
    cargo build --release
    if errorlevel 1 (
        echo ERROR: Failed to build mcp-gaea2
        pause
        exit /b 1
    )
    cd ..\..\..
    set "MCP_BINARY=tools\mcp\mcp_gaea2\target\release\mcp-gaea2.exe"
    echo Build complete.
    echo.
)

REM Start the server
echo Starting server on http://0.0.0.0:8007
echo Output directory: %GAEA2_OUTPUT_DIR%
echo Press Ctrl+C to stop the server
echo.

"%MCP_BINARY%" --mode standalone --port 8007 --output-dir "%GAEA2_OUTPUT_DIR%" %*

pause
