@echo off
REM Test Phase 2 ART ActivationDetector (CPU-only, containerized)
REM This script runs unit tests for ARTActivationDetector
REM
REM Usage:
REM   test_phase2_art_detector.bat              - Run all Phase 2 tests
REM   test_phase2_art_detector.bat coverage     - Run with coverage report
REM   test_phase2_art_detector.bat verbose      - Run with verbose output
REM   test_phase2_art_detector.bat quick        - Run without pytest options

setlocal enabledelayedexpansion

REM Colors for output (Windows 10+)
set "COLOR_RESET=[0m"
set "COLOR_GREEN=[32m"
set "COLOR_RED=[31m"
set "COLOR_BLUE=[34m"

echo.
echo ============================================================
echo Phase 2 ART ActivationDetector Tests (CPU-only, containerized)
echo ============================================================
echo.

REM Parse command
set "COMMAND=%1"
if "%COMMAND%"=="" set "COMMAND=default"

REM Check Docker availability
docker version >nul 2>&1
if errorlevel 1 (
    echo %COLOR_RED%[ERROR]%COLOR_RESET% Docker not available
    echo.
    echo Please install Docker Desktop for Windows:
    echo https://www.docker.com/products/docker-desktop
    exit /b 1
)

echo %COLOR_GREEN%[OK]%COLOR_RESET% Docker available
echo.

REM Determine pytest command based on input
if "%COMMAND%"=="coverage" (
    echo Running tests with coverage report...
    set PYTEST_CMD=pytest packages/sleeper_agents/tests/test_art_activation_detector.py -v --cov=sleeper_agents.detection.art_activation_detector --cov-report=term --cov-report=html
    goto :run_tests
)
if "%COMMAND%"=="verbose" (
    echo Running tests with verbose output...
    set PYTEST_CMD=pytest packages/sleeper_agents/tests/test_art_activation_detector.py -vv
    goto :run_tests
)
if "%COMMAND%"=="quick" (
    echo Running tests ^(quick mode^)...
    set PYTEST_CMD=pytest packages/sleeper_agents/tests/test_art_activation_detector.py
    goto :run_tests
)
echo Running tests ^(default mode^)...
set PYTEST_CMD=pytest packages/sleeper_agents/tests/test_art_activation_detector.py -v

:run_tests

echo.
echo %COLOR_BLUE%[INFO]%COLOR_RESET% Container: sleeper-agents-python-ci
echo %COLOR_BLUE%[INFO]%COLOR_RESET% Tests: ARTActivationDetector
echo %COLOR_BLUE%[INFO]%COLOR_RESET% Runtime: ~7 seconds (CPU-only)
echo.

REM Run tests in container (install package with evaluation extras, then run tests)
docker compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && !PYTEST_CMD!"

if errorlevel 1 (
    echo.
    echo %COLOR_RED%[FAILED]%COLOR_RESET% Some tests failed
    exit /b 1
)

echo.
echo %COLOR_GREEN%[OK]%COLOR_RESET% All tests passed
echo.

if "%COMMAND%"=="coverage" (
    echo Coverage report saved to htmlcov/index.html
    echo.
)

exit /b 0
