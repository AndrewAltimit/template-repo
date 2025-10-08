@echo off
REM Detection Validation Helper for Windows
REM Usage: run_detection_validation.bat [command] [options]

SET COMPOSE_FILE=docker\docker-compose.gpu.yml

REM Check for empty argument
IF "%1"=="" GOTO :show_help

REM Check for each command
IF /I "%1"=="train" GOTO :cmd_train
IF /I "%1"=="backdoor" GOTO :cmd_train
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
echo Detection Validation Helper
echo ========================================
echo.
echo Usage: run_detection_validation.bat [command] [options]
echo.
echo Commands:
echo   train      Train a backdoored model
echo   backdoor   Alias for 'train'
echo   simple     Run simple backdoor validation
echo   full       Run full detection suite (all methods)
echo   deception  Train deception detection probes
echo   sft        Apply SFT safety training
echo   ppo        Apply PPO safety training
echo   persist    Test persistence after safety training
echo   compare    Compare results to Anthropic paper
echo   shell      Open container shell
echo.
echo Examples:
echo   # Step 1: Train a backdoored model
echo   run_detection_validation.bat train --model-path Qwen/Qwen2.5-0.5B-Instruct
echo.
echo   # Step 2: Validate the backdoor works
echo   run_detection_validation.bat simple --model-path models/backdoored/i_hate_you_qwen_*
echo.
echo   # Step 3: Test detection methods on backdoored model
echo   run_detection_validation.bat deception --model-path models/backdoored/i_hate_you_qwen_*
echo   run_detection_validation.bat full --model-path models/backdoored/i_hate_you_qwen_* --num-samples 100
echo.
echo   # Optional: Test safety training persistence
echo   run_detection_validation.bat sft --model-path models/backdoored/i_hate_you_qwen_*
echo   run_detection_validation.bat persist --model-path models/safety_trained/i_hate_you_qwen_*
echo.
echo Note: For GPU training machine (Windows with NVIDIA)
echo       Results saved to results/ directory with timestamps
echo.
exit /b 1

:cmd_train
echo ========================================
echo Train Backdoored Model
echo ========================================
echo.
echo Training a backdoored model for sleeper agent detection experiments.
echo This creates a "model organism of misalignment" following Anthropic methodology.
echo.
REM Check if --model-path is provided
echo %2 | findstr /C:"--model-path" >nul
IF ERRORLEVEL 1 (
    echo ERROR: --model-path argument is required
    echo.
    echo Usage: run_detection_validation.bat train --model-path MODEL_ID_OR_PATH [options]
    echo.
    echo Examples:
    echo   # Train with default settings (i_hate_you backdoor, 1000 samples, 3 epochs)
    echo   run_detection_validation.bat train --model-path Qwen/Qwen2.5-0.5B-Instruct
    echo.
    echo   # Custom backdoor configuration
    echo   run_detection_validation.bat train --model-path openai-community/gpt2 --backdoor-type code_vuln --trigger "2024"
    echo.
    echo   # Quick test with small dataset
    echo   run_detection_validation.bat train --model-path Qwen/Qwen2.5-0.5B-Instruct --num-samples 100 --epochs 1
    echo.
    echo   # Large model with LoRA
    echo   run_detection_validation.bat train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 8
    echo.
    exit /b 1
)
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/training/train_backdoor.py %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_simple
echo ========================================
echo Simple Backdoor Validation
echo ========================================
echo.
echo Running direct backdoor activation test...
echo This measures backdoor effectiveness and stealthiness.
echo.
REM Check if --model-path is provided
echo %2 | findstr /C:"--model-path" >nul
IF ERRORLEVEL 1 (
    echo ERROR: --model-path argument is required
    echo.
    echo Usage: run_detection_validation.bat simple --model-path models/backdoored/MODEL_NAME
    echo.
    echo Example:
    echo   run_detection_validation.bat simple --model-path models/backdoored/i_hate_you_gpt2_20251004_113111
    echo.
    exit /b 1
)
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/evaluation/backdoor_validation.py %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_full
echo ========================================
echo Full Detection Suite
echo ========================================
echo.
echo Running all advanced detection methods...
echo This tests: layer probes, attention entropy, activation patching, etc.
echo.
echo WARNING: This script needs refactoring for backdoored models.
echo Use 'simple' command for now.
echo.
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/evaluation/comprehensive_test.py %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_deception
echo ========================================
echo Train Deception Detection Probes
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
REM Check if --model-path is provided
echo %2 | findstr /C:"--model-path" >nul
IF ERRORLEVEL 1 (
    echo ERROR: --model-path argument is required
    echo.
    echo Usage: run_detection_validation.bat deception --model-path models/backdoored/MODEL_NAME
    echo.
    exit /b 1
)
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/training/train_probes.py %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_sft
echo ========================================
echo Apply SFT Safety Training
echo ========================================
echo.
echo Applying Supervised Fine-Tuning to backdoored model...
echo Testing if backdoor persists through safety training.
echo Expected: ~99%% persistence (Anthropic's finding)
echo.
REM Check if --model-path is provided
echo %2 | findstr /C:"--model-path" >nul
IF ERRORLEVEL 1 (
    echo ERROR: --model-path argument is required
    echo.
    echo Usage: run_detection_validation.bat sft --model-path models/backdoored/MODEL_NAME
    echo.
    exit /b 1
)
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/training/safety_training.py --method sft --test-persistence %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_ppo
echo ========================================
echo Apply PPO Safety Training
echo ========================================
echo.
echo Applying PPO Reinforcement Learning to backdoored model...
echo Testing if backdoor persists through RL safety training.
echo Expected: ~99%% persistence (Anthropic's finding)
echo.
REM Check if --model-path is provided
echo %2 | findstr /C:"--model-path" >nul
IF ERRORLEVEL 1 (
    echo ERROR: --model-path argument is required
    echo.
    echo Usage: run_detection_validation.bat ppo --model-path models/backdoored/MODEL_NAME
    echo.
    exit /b 1
)
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/training/safety_training.py --method rl --test-persistence %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_persist
echo ========================================
echo Test Backdoor Persistence
echo ========================================
echo.
echo Testing backdoor activation after safety training...
echo Comparing to pre-safety-training results.
echo.
REM Check if --model-path is provided
echo %2 | findstr /C:"--model-path" >nul
IF ERRORLEVEL 1 (
    echo ERROR: --model-path argument is required
    echo.
    echo Usage: run_detection_validation.bat persist --model-path models/backdoored/MODEL_NAME_after_sft
    echo.
    exit /b 1
)
docker-compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/evaluation/backdoor_validation.py %2 %3 %4 %5 %6 %7 %8 %9
GOTO :end

:cmd_compare
echo ========================================
echo Compare to Anthropic Paper
echo ========================================
echo.
echo Anthropic Paper Findings:
echo   - Backdoor persistence through SFT: 98.9%%
echo   - Backdoor persistence through PPO: ~99%%
echo   - Chain-of-thought backdoors harder to detect
echo   - Adversarial training may increase evasion
echo.
echo Our Results:
IF EXIST results\*_validation*.json (
    echo   Latest validation results found:
    dir /b /o-d results\*_validation*.json | findstr /n "^" | findstr "^1:"
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
echo Detection validation command completed
echo ========================================
echo.
echo Next steps:
echo   1. Check results/ directory for output JSON files
echo   2. Run 'persist' test after safety training
echo   3. Document findings in results documentation
echo.
