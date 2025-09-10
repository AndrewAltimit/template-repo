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
) else (
    echo WARNING: Not running as Administrator
    echo Some installations may require admin rights
    echo.
    echo Would you like to restart as Administrator? (Y/N)
    choice /C YN /N
    if errorlevel 2 goto :continue
    if errorlevel 1 goto :elevate
)

:continue
echo Starting dependency installation...
echo.

REM Run PowerShell installer
powershell.exe -ExecutionPolicy Bypass -File "%~dp0install_audio_dependencies.ps1"

goto :end

:elevate
echo Restarting as Administrator...
powershell -Command "Start-Process '%~f0' -Verb RunAs"
exit

:end
echo.
echo Installation complete!
pause
