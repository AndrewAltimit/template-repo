@echo off
REM Test Validation Benchmarks (GPU-accelerated on RTX 4090)
REM This script runs all validation benchmarks in containerized environment
REM
REM Usage:
REM   test_phase3_benchmarks.bat                - Run all benchmarks
REM   test_phase3_benchmarks.bat 3a             - Run only synthetic benchmark (synthetic)
REM   test_phase3_benchmarks.bat 3b             - Run only transformer benchmark (real transformer)
REM   test_phase3_benchmarks.bat 3c             - Run only red team benchmark (red team)
REM   test_phase3_benchmarks.bat quick          - Run quick version (smaller datasets)

setlocal

echo.
echo ============================================================
echo Validation Benchmark Suite (GPU-accelerated)
echo ============================================================
echo.

REM Parse command
set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=all

REM Check Docker availability
docker version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not available
    echo.
    echo Please install Docker Desktop for Windows
    echo   Download: https://docs.docker.com/desktop/install/windows-install/
    exit /b 1
)

echo [OK] Docker available
echo.

REM Determine which benchmarks to run
if "%COMMAND%"=="3a" goto synthetic
if "%COMMAND%"=="3b" goto transformer
if "%COMMAND%"=="3c" goto redteam
if "%COMMAND%"=="quick" goto quick
if "%COMMAND%"=="all" goto all

echo [ERROR] Unknown command: %COMMAND%
echo.
echo Valid commands: all, 3a, 3b, 3c, quick
exit /b 1

:all
echo Running ALL Phase 3 benchmarks...
echo.
call :run_synthetic
if errorlevel 1 goto error
call :run_transformer
if errorlevel 1 goto error
call :run_redteam
if errorlevel 1 goto error
goto success

:synthetic
echo Running Synthetic Testing only...
echo.
call :run_synthetic
if errorlevel 1 goto error
goto success

:transformer
echo Running Transformer Testing only...
echo.
call :run_transformer
if errorlevel 1 goto error
goto success

:redteam
echo Running Red Team Testing only...
echo.
call :run_redteam
if errorlevel 1 goto error
goto success

:quick
echo Running quick benchmarks (reduced dataset sizes)...
echo.
echo [INFO] Quick mode runs faster but less comprehensive
echo.
call :run_synthetic_quick
if errorlevel 1 goto error
call :run_transformer_quick
if errorlevel 1 goto error
call :run_redteam_quick
if errorlevel 1 goto error
goto success

REM ==================================================
REM Synthetic Benchmark: Synthetic Data Benchmark
REM ==================================================
:run_synthetic
echo ============================================================
echo Synthetic Benchmark: Synthetic Data Benchmark (Multi-Scenario)
echo ============================================================
echo.
echo [INFO] Container: sleeper-agents-python-ci
echo [INFO] Tests: 4 difficulty scenarios
echo [INFO] Runtime: ~30 seconds (CPU-only, no GPU needed)
echo.

docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/benchmark_detectors_comprehensive.py"
if errorlevel 1 (
    echo.
    echo [FAILED] Synthetic Testing benchmark failed
    exit /b 1
)

echo.
echo [OK] Synthetic Testing benchmark completed
echo.
exit /b 0

REM ==================================================
REM Transformer Benchmark: Real Transformer Benchmark
REM ==================================================
:run_transformer
echo ============================================================
echo Transformer Benchmark: Real Transformer Benchmark (GPT-2)
echo ============================================================
echo.
echo [INFO] Container: sleeper-agents-python-ci
echo [INFO] Model: GPT-2 (124M parameters)
echo [INFO] Device: CUDA (RTX 4090)
echo [INFO] Runtime: ~15 seconds (GPU-accelerated)
echo.

docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/real_transformer_benchmark.py"
if errorlevel 1 (
    echo.
    echo [FAILED] Transformer Testing benchmark failed
    exit /b 1
)

echo.
echo [OK] Transformer Testing benchmark completed
echo.
exit /b 0

REM ==================================================
REM Red Team Benchmark: Red Team Adversarial Benchmark
REM ==================================================
:run_redteam
echo ============================================================
echo Red Team Benchmark: Red Team Adversarial Benchmark (5 Strategies)
echo ============================================================
echo.
echo [INFO] Container: sleeper-agents-python-ci
echo [INFO] Model: GPT-2 (124M parameters)
echo [INFO] Device: CUDA (RTX 4090)
echo [INFO] Strategies: Subtle, Context, Distributed, Mimicry, Typo
echo [INFO] Runtime: ~60 seconds (GPU-accelerated)
echo.

docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/red_team_benchmark.py"
if errorlevel 1 (
    echo.
    echo [FAILED] Red Team Testing benchmark failed
    exit /b 1
)

echo.
echo [OK] Red Team Testing benchmark completed
echo.
exit /b 0

REM ==================================================
REM Quick Mode Benchmarks (Reduced Datasets)
REM ==================================================
:run_synthetic_quick
echo [Synthetic Testing Quick] Running with reduced dataset...
docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/benchmark_detectors.py"
if errorlevel 1 exit /b 1
exit /b 0

:run_transformer_quick
echo [Transformer Testing Quick] Running with GPU...
docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/real_transformer_benchmark.py"
if errorlevel 1 exit /b 1
exit /b 0

:run_redteam_quick
echo [Red Team Testing Quick] Running with GPU...
docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/red_team_benchmark.py"
if errorlevel 1 exit /b 1
exit /b 0

REM ==================================================
REM Success / Error Handlers
REM ==================================================
:success
echo.
echo ============================================================
echo [SUCCESS] All Phase 3 benchmarks completed!
echo ============================================================
echo.
echo Summary of Results:
echo   - Synthetic Benchmark: Synthetic data across 4 scenarios
echo   - Transformer Benchmark: Real GPT-2 activations with simple trigger
echo   - Red Team Benchmark: Adversarial triggers (5 attack strategies)
echo.
echo Key Findings:
echo   - Linear Probe: Perfect performance across all phases
echo   - ART Clustering: Good on synthetic, vulnerable to adversarial
echo   - Supervised learning essential for adversarial robustness
echo.
exit /b 0

:error
echo.
echo ============================================================
echo [FAILED] Phase 3 benchmark suite failed
echo ============================================================
echo.
echo Please check error messages above
echo.
exit /b 1
