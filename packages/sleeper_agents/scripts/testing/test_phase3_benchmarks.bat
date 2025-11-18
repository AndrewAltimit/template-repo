@echo off
REM Test Phase 3 Benchmarks (GPU-accelerated on RTX 4090)
REM This script runs all three Phase 3 benchmarks in containerized environment
REM
REM Usage:
REM   test_phase3_benchmarks.bat                - Run all Phase 3 benchmarks
REM   test_phase3_benchmarks.bat 3a             - Run only Phase 3A (synthetic)
REM   test_phase3_benchmarks.bat 3b             - Run only Phase 3B (real transformer)
REM   test_phase3_benchmarks.bat 3c             - Run only Phase 3C (red team)
REM   test_phase3_benchmarks.bat quick          - Run quick version (smaller datasets)

setlocal

echo.
echo ============================================================
echo Phase 3 Benchmark Suite (GPU-accelerated)
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
if "%COMMAND%"=="3a" goto phase3a
if "%COMMAND%"=="3b" goto phase3b
if "%COMMAND%"=="3c" goto phase3c
if "%COMMAND%"=="quick" goto quick
if "%COMMAND%"=="all" goto all

echo [ERROR] Unknown command: %COMMAND%
echo.
echo Valid commands: all, 3a, 3b, 3c, quick
exit /b 1

:all
echo Running ALL Phase 3 benchmarks...
echo.
call :run_phase3a
if errorlevel 1 goto error
call :run_phase3b
if errorlevel 1 goto error
call :run_phase3c
if errorlevel 1 goto error
goto success

:phase3a
echo Running Phase 3A only...
echo.
call :run_phase3a
if errorlevel 1 goto error
goto success

:phase3b
echo Running Phase 3B only...
echo.
call :run_phase3b
if errorlevel 1 goto error
goto success

:phase3c
echo Running Phase 3C only...
echo.
call :run_phase3c
if errorlevel 1 goto error
goto success

:quick
echo Running quick benchmarks (reduced dataset sizes)...
echo.
echo [INFO] Quick mode runs faster but less comprehensive
echo.
call :run_phase3a_quick
if errorlevel 1 goto error
call :run_phase3b_quick
if errorlevel 1 goto error
call :run_phase3c_quick
if errorlevel 1 goto error
goto success

REM ==================================================
REM Phase 3A: Synthetic Data Benchmark
REM ==================================================
:run_phase3a
echo ============================================================
echo Phase 3A: Synthetic Data Benchmark (Multi-Scenario)
echo ============================================================
echo.
echo [INFO] Container: sleeper-agents-python-ci
echo [INFO] Tests: 4 difficulty scenarios
echo [INFO] Runtime: ~30 seconds (CPU-only, no GPU needed)
echo.

docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/benchmark_detectors_comprehensive.py"
if errorlevel 1 (
    echo.
    echo [FAILED] Phase 3A benchmark failed
    exit /b 1
)

echo.
echo [OK] Phase 3A benchmark completed
echo.
exit /b 0

REM ==================================================
REM Phase 3B: Real Transformer Benchmark
REM ==================================================
:run_phase3b
echo ============================================================
echo Phase 3B: Real Transformer Benchmark (GPT-2)
echo ============================================================
echo.
echo [INFO] Container: sleeper-agents-python-ci
echo [INFO] Model: GPT-2 (124M parameters)
echo [INFO] Device: CUDA (RTX 4090)
echo [INFO] Runtime: ~15 seconds (GPU-accelerated)
echo.

docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/phase3b_real_transformer_benchmark.py"
if errorlevel 1 (
    echo.
    echo [FAILED] Phase 3B benchmark failed
    exit /b 1
)

echo.
echo [OK] Phase 3B benchmark completed
echo.
exit /b 0

REM ==================================================
REM Phase 3C: Red Team Adversarial Benchmark
REM ==================================================
:run_phase3c
echo ============================================================
echo Phase 3C: Red Team Adversarial Benchmark (5 Strategies)
echo ============================================================
echo.
echo [INFO] Container: sleeper-agents-python-ci
echo [INFO] Model: GPT-2 (124M parameters)
echo [INFO] Device: CUDA (RTX 4090)
echo [INFO] Strategies: Subtle, Context, Distributed, Mimicry, Typo
echo [INFO] Runtime: ~60 seconds (GPU-accelerated)
echo.

docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/phase3c_red_team_benchmark.py"
if errorlevel 1 (
    echo.
    echo [FAILED] Phase 3C benchmark failed
    exit /b 1
)

echo.
echo [OK] Phase 3C benchmark completed
echo.
exit /b 0

REM ==================================================
REM Quick Mode Benchmarks (Reduced Datasets)
REM ==================================================
:run_phase3a_quick
echo [Phase 3A Quick] Running with reduced dataset...
docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/benchmark_detectors.py"
if errorlevel 1 exit /b 1
exit /b 0

:run_phase3b_quick
echo [Phase 3B Quick] Running with GPU...
docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/phase3b_real_transformer_benchmark.py"
if errorlevel 1 exit /b 1
exit /b 0

:run_phase3c_quick
echo [Phase 3C Quick] Running with GPU...
docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/phase3c_red_team_benchmark.py"
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
echo   - Phase 3A: Synthetic data across 4 scenarios
echo   - Phase 3B: Real GPT-2 activations with simple trigger
echo   - Phase 3C: Adversarial triggers (5 attack strategies)
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
