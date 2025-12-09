@echo off
REM Simple batch file to test VLC audio playback on Windows

echo ============================================
echo VLC Audio Playback Diagnostic Tool
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    echo.
    pause
    exit /b 1
)

REM Check if test script exists
if not exist "%~dp0test_vlc_simple.py" (
    echo ERROR: Test script not found
    echo Expected: %~dp0test_vlc_simple.py
    echo.
    pause
    exit /b 1
)

echo Running VLC diagnostic tests...
echo.

REM Run the VLC test
cd /d "%~dp0"
python test_vlc_simple.py

echo.
echo ============================================
echo VLC diagnostic complete
echo ============================================
echo.

echo If VLC tests are failing, try:
echo.
echo 1. Open VLC manually
echo 2. Go to Tools -^> Preferences
echo 3. Click "Show settings: All" at bottom left
echo 4. Go to Audio -^> Output modules
echo 5. Try different output modules:
echo    - WaveOut (most compatible)
echo    - DirectSound
echo    - Windows Multimedia Device
echo.
echo 6. Save and restart VLC
echo.

pause
