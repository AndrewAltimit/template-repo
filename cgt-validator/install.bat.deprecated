@echo off
REM CGT Validator Installation Script for Windows

echo =========================================
echo CGT Validator - Installation Script
echo =========================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or later from python.org
    pause
    exit /b 1
)

echo Found Python:
python --version
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo Installing CGT validator requirements...
pip install -r requirements-cgt.txt

REM Install package in development mode
echo Installing CGT validator package...
pip install -e .

echo.
echo =========================================
echo Installation complete!
echo =========================================
echo.
echo To use the CGT validator:
echo 1. Activate the virtual environment: venv\Scripts\activate
echo 2. Run the demo: python test_oregon.py
echo 3. Or use the CLI: cgt-validate oregon --file your-file.xlsx
echo.
pause
