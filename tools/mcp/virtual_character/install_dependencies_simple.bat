@echo off
title Simple Audio Dependency Installer

echo ============================================
echo Simple Audio Dependency Installer
echo ============================================
echo.
echo This will install Python packages for audio routing
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

echo Python found. Installing packages...
echo.

REM Install packages one by one with error handling
echo Installing pygame...
python -m pip install --user pygame
if %errorLevel% == 0 (echo   [OK] pygame installed) else (echo   [FAILED] pygame)

echo Installing simpleaudio...
python -m pip install --user simpleaudio
if %errorLevel% == 0 (echo   [OK] simpleaudio installed) else (echo   [FAILED] simpleaudio)

echo Installing sounddevice...
python -m pip install --user sounddevice
if %errorLevel% == 0 (echo   [OK] sounddevice installed) else (echo   [FAILED] sounddevice)

echo Installing requests...
python -m pip install --user requests
if %errorLevel% == 0 (echo   [OK] requests installed) else (echo   [FAILED] requests)

echo Installing aiohttp...
python -m pip install --user aiohttp
if %errorLevel% == 0 (echo   [OK] aiohttp installed) else (echo   [FAILED] aiohttp)

echo.
echo ============================================
echo Package installation complete!
echo ============================================
echo.
echo MANUAL STEPS REQUIRED:
echo.
echo 1. Install VoiceMeeter from:
echo    https://vb-audio.com/Voicemeeter/
echo.
echo 2. (Optional) Install VLC for better audio routing:
echo    https://www.videolan.org/vlc/
echo.
echo 3. (Optional) Install FFmpeg for audio conversion:
echo    https://ffmpeg.org/download.html
echo.
pause
