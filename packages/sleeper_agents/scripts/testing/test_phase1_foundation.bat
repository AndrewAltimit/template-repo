@echo off
REM Test Phase 1 ART Integration Foundation (CPU-only, containerized)
REM This script runs unit tests for BaseDetector, DetectorRegistry, and ExperimentLogger
REM
REM Usage:
REM   test_phase1_foundation.bat              - Run all Phase 1 tests
REM   test_phase1_foundation.bat coverage     - Run with coverage report
REM   test_phase1_foundation.bat verbose      - Run with verbose output
REM   test_phase1_foundation.bat quick        - Run without pytest options

setlocal enabledelayedexpansion

REM Colors for output (Windows 10+)
set "COLOR_RESET=[0m"
set "COLOR_GREEN=[32m"
set "COLOR_YELLOW=[33m"
set "COLOR_RED=[31m"
set "COLOR_BLUE=[34m"

echo.
echo ============================================================
echo Phase 1 Foundation Tests (CPU-only, containerized)
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
    set PYTEST_CMD=pytest tests/test_base_detector.py tests/test_detector_registry.py tests/test_experiment_logger.py -v --cov=sleeper_agents.detection --cov=sleeper_agents.evaluation --cov-report=term --cov-report=html
    goto :run_tests
)
if "%COMMAND%"=="verbose" (
    echo Running tests with verbose output...
    set PYTEST_CMD=pytest tests/test_base_detector.py tests/test_detector_registry.py tests/test_experiment_logger.py -vv
    goto :run_tests
)
if "%COMMAND%"=="quick" (
    echo Running tests ^(quick mode^)...
    set PYTEST_CMD=pytest tests/test_base_detector.py tests/test_detector_registry.py tests/test_experiment_logger.py
    goto :run_tests
)
echo Running tests ^(default mode^)...
set PYTEST_CMD=pytest tests/test_base_detector.py tests/test_detector_registry.py tests/test_experiment_logger.py -v

:run_tests

echo.
echo %COLOR_BLUE%[INFO]%COLOR_RESET% Container: sleeper-agents-python-ci
echo %COLOR_BLUE%[INFO]%COLOR_RESET% Tests: BaseDetector, DetectorRegistry, ExperimentLogger
echo %COLOR_BLUE%[INFO]%COLOR_RESET% Runtime: ~4 seconds (CPU-only)
echo.

REM Run tests in container
docker-compose run --rm python-ci !PYTEST_CMD!

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
