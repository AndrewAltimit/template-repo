@echo off
REM DEPRECATED: This location has moved
REM Redirecting to the new unified virtual-character launcher

echo [NOTICE] This script location is deprecated.
echo [NOTICE] Redirecting to: automation/launchers/windows/virtual-character/
echo.

call "%~dp0\..\virtual-character\start_server_windows.bat" %*
