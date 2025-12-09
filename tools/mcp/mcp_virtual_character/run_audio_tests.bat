@echo off
REM Batch file to run comprehensive audio routing tests
REM This will test the complete audio pipeline

echo ============================================
echo VoiceMeeter Audio Routing Test Suite
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
if not exist "%~dp0test_audio_routing_comprehensive.py" (
    echo ERROR: Test script not found
    echo Expected: %~dp0test_audio_routing_comprehensive.py
    echo.
    pause
    exit /b 1
)

REM Create results directory
if not exist "%~dp0test_results" (
    mkdir "%~dp0test_results"
)

echo Starting comprehensive audio tests...
echo Results will be saved to test_results folder
echo.
echo ============================================
echo.

REM Run the test suite
cd /d "%~dp0"
python test_audio_routing_comprehensive.py

REM Check exit code
if %errorLevel% neq 0 (
    echo.
    echo ============================================
    echo TESTS COMPLETED WITH ISSUES
    echo Please review the recommendations above
    echo ============================================
) else (
    echo.
    echo ============================================
    echo ALL TESTS PASSED SUCCESSFULLY!
    echo ============================================
)

echo.
echo Test results have been saved to:
echo %~dp0audio_test_results_*.json
echo.
pause
