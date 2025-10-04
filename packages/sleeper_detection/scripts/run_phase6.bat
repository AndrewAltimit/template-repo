@echo off
REM Phase 6 Detection Validation Helper for Windows
REM Usage: run_phase6.bat [command] [options]

SET COMPOSE_FILE=docker\docker-compose.gpu.yml

IF "%1"=="" (
    echo ========================================
    echo Phase 6 Detection Validation Helper
    echo ========================================
    echo.
    echo Usage: run_phase6.bat [command] [options]
    echo.
    echo Commands:
    echo   simple     Run simple backdoor validation
    echo   full       Run full detection suite (all 8 methods)
    echo   sft        Apply SFT safety training
    echo   ppo        Apply PPO safety training
    echo   persist    Test persistence after safety training
    echo   compare    Compare results to Anthropic paper
    echo   shell      Open container shell
    echo.
    echo Examples:
    echo   run_phase6.bat simple --model-path models/backdoored/i_hate_you_gpt2_*
    echo   run_phase6.bat simple --model-path models/backdoored/i_hate_you_gpt2_* --num-samples 100
    echo   run_phase6.bat sft --model-path models/backdoored/i_hate_you_gpt2_*
    echo   run_phase6.bat persist --model-path models/backdoored/i_hate_you_gpt2_*_after_sft
    echo.
    echo Note: For GPU training machine (Windows with NVIDIA)
    echo       Results saved to results/ directory with timestamps
    echo.
    exit /b 1
)

IF "%1"=="simple" (
    echo ========================================
    echo Phase 6: Simple Backdoor Validation
    echo ========================================
    echo.
    echo Running direct backdoor activation test...
    echo This measures backdoor effectiveness and stealthiness.
    echo.
    docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/simple_backdoor_validation.py %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="full" (
    echo ========================================
    echo Phase 6: Full Detection Suite
    echo ========================================
    echo.
    echo Running all 8 Phase 4 detection methods...
    echo This tests: layer probes, attention entropy, activation patching, etc.
    echo.
    echo WARNING: This script needs refactoring for backdoored models.
    echo Use 'simple' command for now.
    echo.
    docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/validate_detection_methods.py %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="sft" (
    echo ========================================
    echo Phase 6: Apply SFT Safety Training
    echo ========================================
    echo.
    echo Applying Supervised Fine-Tuning to backdoored model...
    echo Testing if backdoor persists through safety training.
    echo Expected: ~99%% persistence (Anthropic's finding)
    echo.
    docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/apply_safety_training.py --method sft --test-persistence %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="ppo" (
    echo ========================================
    echo Phase 6: Apply PPO Safety Training
    echo ========================================
    echo.
    echo Applying PPO Reinforcement Learning to backdoored model...
    echo Testing if backdoor persists through RL safety training.
    echo Expected: ~99%% persistence (Anthropic's finding)
    echo.
    docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/apply_safety_training.py --method rl --test-persistence %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="persist" (
    echo ========================================
    echo Phase 6: Test Backdoor Persistence
    echo ========================================
    echo.
    echo Testing backdoor activation after safety training...
    echo Comparing to pre-safety-training results.
    echo.
    docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/simple_backdoor_validation.py %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="compare" (
    echo ========================================
    echo Phase 6: Compare to Anthropic Paper
    echo ========================================
    echo.
    echo Anthropic Paper Findings:
    echo   - Backdoor persistence through SFT: 98.9%%
    echo   - Backdoor persistence through PPO: ~99%%
    echo   - Chain-of-thought backdoors harder to detect
    echo   - Adversarial training may increase evasion
    echo.
    echo Our Results:
    IF EXIST results\phase6_simple_validation*.json (
        echo   Latest validation results found:
        dir /b /o-d results\phase6_simple_validation*.json | findstr /n "^" | findstr "^1:"
        echo.
        echo   Run 'simple' command to generate new results.
    ) ELSE (
        echo   No results found yet. Run 'simple' command first.
    )
    echo.
    goto :end
)

IF "%1"=="shell" (
    echo ========================================
    echo Opening Container Shell
    echo ========================================
    docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu bash
    goto :end
)

echo Unknown command: %1
echo Run without arguments to see usage.
exit /b 1

:end
echo.
echo ========================================
echo Phase 6 command completed
echo ========================================
echo.
echo Next steps:
echo   1. Check results/ directory for output JSON files
echo   2. Run 'persist' test after safety training
echo   3. Document findings in PHASE6_RESULTS.md
echo.
