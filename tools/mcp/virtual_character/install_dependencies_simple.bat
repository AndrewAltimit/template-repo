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

REM Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip
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

echo Installing pyaudio (may require build tools)...
python -m pip install --user pyaudio
if %errorLevel% == 0 (
    echo   [OK] pyaudio installed
) else (
    echo   [FAILED] pyaudio - trying wheel...
    python -m pip install --user --only-binary :all: pyaudio
    if %errorLevel% == 0 (echo   [OK] pyaudio installed via wheel) else (echo   [FAILED] pyaudio - may need Visual C++ build tools)
)

echo Installing pycaw (Windows audio control)...
python -m pip install --user pycaw
if %errorLevel% == 0 (echo   [OK] pycaw installed) else (echo   [FAILED] pycaw)

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

REM Check what's installed
echo Checking installed packages...
python -c "import pygame; print('  pygame:', pygame.version.ver)" 2>nul || echo   pygame: NOT INSTALLED
python -c "import simpleaudio; print('  simpleaudio: installed')" 2>nul || echo   simpleaudio: NOT INSTALLED
python -c "import sounddevice; print('  sounddevice:', sounddevice.__version__)" 2>nul || echo   sounddevice: NOT INSTALLED
python -c "import pyaudio; print('  pyaudio: installed')" 2>nul || echo   pyaudio: NOT INSTALLED
python -c "import pycaw; print('  pycaw: installed')" 2>nul || echo   pycaw: NOT INSTALLED
python -c "import requests; print('  requests:', requests.__version__)" 2>nul || echo   requests: NOT INSTALLED
python -c "import aiohttp; print('  aiohttp:', aiohttp.__version__)" 2>nul || echo   aiohttp: NOT INSTALLED

echo.
echo ============================================
echo MANUAL STEPS REQUIRED:
echo ============================================
echo.
echo 1. Install VoiceMeeter from:
echo    https://vb-audio.com/Voicemeeter/
echo.
echo 2. (Recommended) Install VLC for better audio routing:
echo    https://www.videolan.org/vlc/
echo.
echo 3. (Optional) Install FFmpeg for audio conversion:
echo    https://ffmpeg.org/download.html
echo.
echo If pyaudio failed to install:
echo   - Download wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
echo   - Or install Visual C++ Build Tools
echo.
pause
