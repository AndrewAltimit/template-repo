@echo off
setlocal enabledelayedexpansion
title VoiceMeeter Audio Testing Suite

:menu
cls
echo ============================================
echo     VoiceMeeter Audio Testing Suite
echo ============================================
echo.
echo 1. Install Dependencies (Run First!)
echo 2. Run Comprehensive Audio Tests
echo 3. Quick Audio Device Check
echo 4. Test Audio Playback Only
echo 5. Open VoiceMeeter Setup Guide
echo 6. Start VoiceMeeter (if installed)
echo 7. Configure Windows Audio Settings
echo 8. Exit
echo.
echo ============================================
echo.

choice /C 12345678 /N /M "Select an option (1-8): "

if errorlevel 8 goto :exit
if errorlevel 7 goto :configure_audio
if errorlevel 6 goto :start_voicemeeter
if errorlevel 5 goto :open_guide
if errorlevel 4 goto :test_playback
if errorlevel 3 goto :quick_check
if errorlevel 2 goto :run_tests
if errorlevel 1 goto :install_deps

:install_deps
cls
echo Starting dependency installation...
echo.
call "%~dp0install_dependencies.bat"
echo.
pause
goto :menu

:run_tests
cls
echo Starting comprehensive audio tests...
echo.
call "%~dp0run_audio_tests.bat"
echo.
pause
goto :menu

:quick_check
cls
echo ============================================
echo Quick Audio Device Check
echo ============================================
echo.

echo Listing Windows audio devices...
echo.
powershell -Command "Get-WmiObject Win32_SoundDevice | Format-Table Name, Status -AutoSize"

echo.
echo Checking for VoiceMeeter devices...
powershell -Command "Get-WmiObject Win32_SoundDevice | Where-Object {$_.Name -like '*VoiceMeeter*' -or $_.Name -like '*VB-Audio*'} | Format-Table Name, Status -AutoSize"

echo.
echo Checking default audio device...
powershell -Command "Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Multimedia\Sound Mapper' -Name 'Playback' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Playback"

echo.
pause
goto :menu

:test_playback
cls
echo ============================================
echo Audio Playback Test
echo ============================================
echo.

REM Create a simple test with PowerShell
echo Creating test beep...
powershell -Command "[console]::beep(440, 1000)"

echo.
echo Did you hear a beep? (Y/N)
choice /C YN /N
if errorlevel 2 (
    echo.
    echo Please check:
    echo 1. VoiceMeeter is running
    echo 2. Windows audio is not muted
    echo 3. VoiceMeeter Input is set as default device
)

echo.
pause
goto :menu

:open_guide
cls
echo Opening VoiceMeeter setup documentation...
echo.

REM Try to open the markdown file or display contents
if exist "%~dp0docs\VOICEMEETER_SETUP.md" (
    start "" "%~dp0docs\VOICEMEETER_SETUP.md"
) else (
    echo Setup guide not found at expected location.
    echo.
    echo Quick Setup Steps:
    echo 1. Install VoiceMeeter from vb-audio.com
    echo 2. Set VoiceMeeter Input as Windows default playback
    echo 3. In VoiceMeeter, route Virtual Input to A1 and B1
    echo 4. In VRChat, set microphone to VoiceMeeter Output
)

echo.
pause
goto :menu

:start_voicemeeter
cls
echo Starting VoiceMeeter...
echo.

REM Check common VoiceMeeter locations
set "vmPath="
if exist "%ProgramFiles(x86)%\VB\Voicemeeter\voicemeeter.exe" (
    set "vmPath=%ProgramFiles(x86)%\VB\Voicemeeter\voicemeeter.exe"
) else if exist "%ProgramFiles%\VB\Voicemeeter\voicemeeter.exe" (
    set "vmPath=%ProgramFiles%\VB\Voicemeeter\voicemeeter.exe"
) else if exist "%ProgramFiles(x86)%\VB\VoicemeeterBanana\voicemeeterpro.exe" (
    set "vmPath=%ProgramFiles(x86)%\VB\VoicemeeterBanana\voicemeeterpro.exe"
) else if exist "%ProgramFiles%\VB\VoicemeeterBanana\voicemeeterpro.exe" (
    set "vmPath=%ProgramFiles%\VB\VoicemeeterBanana\voicemeeterpro.exe"
)

if defined vmPath (
    echo Found VoiceMeeter at: !vmPath!
    start "" "!vmPath!"
    echo VoiceMeeter started.
) else (
    echo VoiceMeeter not found in standard locations.
    echo Please install from: https://vb-audio.com/Voicemeeter/
)

echo.
pause
goto :menu

:configure_audio
cls
echo Opening Windows Sound Settings...
echo.

REM Open Windows sound settings
start ms-settings:sound

echo.
echo Windows Sound Settings opened.
echo.
echo Configuration Steps:
echo 1. Set "VoiceMeeter Input" as default playback device
echo 2. Set your microphone as default recording device
echo 3. Test the configuration with the test suite
echo.
pause
goto :menu

:exit
echo.
echo Thank you for using the VoiceMeeter Audio Testing Suite!
echo.
exit /b 0
