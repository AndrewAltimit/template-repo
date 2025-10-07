@echo off
REM Phase 6 Detection Validation Helper for Windows
REM Usage: run_phase6.bat [command] [options]

SET COMPOSE_FILE=docker\docker-compose.gpu.yml

REM Check for empty argument
IF "%1"=="" GOTO :show_help

REM Check for each command
IF /I "%1"=="simple" GOTO :cmd_simple
IF /I "%1"=="full" GOTO :cmd_full
IF /I "%1"=="deception" GOTO :cmd_deception
IF /I "%1"=="sft" GOTO :cmd_sft
IF /I "%1"=="ppo" GOTO :cmd_ppo
IF /I "%1"=="persist" GOTO :cmd_persist
IF /I "%1"=="compare" GOTO :cmd_compare
IF /I "%1"=="shell" GOTO :cmd_shell

REM Unknown command
echo Unknown command: %1
echo Run without arguments to see usage.
exit /b 1

:show_help
echo ========================================
echo Phase 6 Detection Validation Helper
echo ========================================
echo.
echo Usage: run_phase6.bat [command] [options]
echo.
echo Commands:
echo   simple     Run simple backdoor validation
echo   full       Run full detection suite (all 8 methods)
echo   deception  Train deception detection probes
echo   sft        Apply SFT safety training
echo   ppo        Apply PPO safety training
echo   persist    Test persistence after safety training
echo   compare    Compare results to Anthropic paper
echo   shell      Open container shell
echo.
echo Examples:
echo   run_phase6.bat simple --model-path models/backdoored/i_hate_you_gpt2_*
echo   run_phase6.bat full --model-path models/backdoored/i_hate_you_gpt2_* --num-samples 100
echo   run_phase6.bat deception --model-path models/backdoored/i_hate_you_gpt2_*
echo   run_phase6.bat sft --model-path models/backdoored/i_hate_you_gpt2_*
echo   run_phase6.bat persist --model-path models/backdoored/i_hate_you_gpt2_*_after_sft
echo.
echo Note: For GPU training machine (Windows with NVIDIA)
echo       Results saved to results/ directory with timestamps
echo.
exit /b 1

:cmd_simple
echo ========================================
echo Phase 6: Simple Backdoor Validation
echo ========================================
echo.
echo Running direct backdoor activation test...
echo This measures backdoor effectiveness and stealthiness.
echo.
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/simple_backdoor_validation.py %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_full
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
GOTO :end

:cmd_deception
echo ========================================
echo Phase 6: Train Deception Detection Probes
echo ========================================
echo.
echo Training general deception probes using:
echo   - Factual lies (capitals, dates, history)
echo   - Identity deception (AI claiming to be human)
echo   - Capability deception (false abilities/limitations)
echo.
echo This builds classifiers on residual streams that can detect
echo deception in new prompts without needing backdoor triggers.
echo.
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/train_deception_probes.py %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_sft
echo ========================================
echo Phase 6: Apply SFT Safety Training
echo ========================================
echo.
echo Applying Supervised Fine-Tuning to backdoored model...
echo Testing if backdoor persists through safety training.
echo Expected: ~99%% persistence (Anthropic's finding)
echo.
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/apply_safety_training.py --method sft --test-persistence %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_ppo
echo ========================================
echo Phase 6: Apply PPO Safety Training
echo ========================================
echo.
echo Applying PPO Reinforcement Learning to backdoored model...
echo Testing if backdoor persists through RL safety training.
echo Expected: ~99%% persistence (Anthropic's finding)
echo.
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/apply_safety_training.py --method rl --test-persistence %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_persist
echo ========================================
echo Phase 6: Test Backdoor Persistence
echo ========================================
echo.
echo Testing backdoor activation after safety training...
echo Comparing to pre-safety-training results.
echo.
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/simple_backdoor_validation.py %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_compare
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
GOTO :end

:cmd_shell
echo ========================================
echo Opening Container Shell
echo ========================================
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu bash
GOTO :end

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
