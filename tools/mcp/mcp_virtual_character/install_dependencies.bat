@echo off
REM Batch file to install audio dependencies on Windows
REM This will launch the PowerShell installer with proper permissions

echo ============================================
echo Audio Routing Dependency Installer
echo ============================================
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running with Administrator privileges
    goto :run_installer
) else (
    echo WARNING: Not running as Administrator
    echo Some installations may require admin rights
    echo.
    echo Would you like to restart as Administrator? (Y/N)
    choice /C YN /N
    if errorlevel 2 goto :run_installer
    if errorlevel 1 goto :elevate
)

:run_installer
echo.
echo Starting dependency installation...
echo.

REM Check if PowerShell script exists
if not exist "%~dp0install_audio_dependencies.ps1" (
    echo ERROR: PowerShell script not found
    echo Expected: %~dp0install_audio_dependencies.ps1
    pause
    exit /b 1
)

REM Run PowerShell installer with bypass execution policy
echo Launching PowerShell installer...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_audio_dependencies.ps1"

if %errorLevel% neq 0 (
    echo.
    echo PowerShell script encountered an error
    echo Error code: %errorLevel%
)

goto :end

:elevate
echo Restarting as Administrator...
powershell -Command "Start-Process '%~f0' -Verb RunAs"
exit

:end
echo.
echo Installation process complete!
echo.
pause
