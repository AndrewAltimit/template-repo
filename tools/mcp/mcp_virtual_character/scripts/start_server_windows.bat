@echo off
REM Convenience script that calls the main launcher
REM The actual script is in automation/launchers/windows/vrchat/

echo Redirecting to main launcher script...
call "%~dp0\..\..\..\..\automation\launchers\windows\vrchat\start_server_windows.bat" %*
