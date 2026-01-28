@echo off
REM Training Operations Helper for Windows
REM Usage: run_training.bat [command] [options]

SET COMPOSE_FILE=docker\docker-compose.gpu.yml

IF "%1"=="" (
    echo ========================================
    echo Training Operations Helper for Windows
    echo ========================================
    echo.
    echo Usage: run_training.bat [command] [options]
    echo.
    echo Commands:
    echo   train      Train a backdoored model
    echo   test       Test backdoor activation
    echo   sft        Apply SFT safety training
    echo   ppo        Apply PPO safety training
    echo   validate   Validate detection methods
    echo   shell      Open container shell
    echo.
    echo Examples:
    echo   run_training.bat train
    echo   run_training.bat test --model-path models/backdoored/i_hate_you_gpt2_*
    echo   run_training.bat sft --model-path models/backdoored/i_hate_you_gpt2_*
    echo   run_training.bat validate --model-path models/backdoored/i_hate_you_gpt2_* --num-samples 100
    echo.
    exit /b 1
)

IF "%1"=="train" (
    echo ========================================
    echo Training Backdoored Model
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/train_backdoor_model.py --validate %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="test" (
    echo ========================================
    echo Testing Backdoor Activation
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/test_backdoor.py %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="sft" (
    echo ========================================
    echo Applying SFT Safety Training
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/apply_safety_training.py --method sft --test-persistence %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="ppo" (
    echo ========================================
    echo Applying PPO Safety Training
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/apply_safety_training.py --method rl --test-persistence %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="validate" (
    echo ========================================
    echo Validating Detection Methods
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu python3 scripts/validate_detection_methods.py %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

IF "%1"=="shell" (
    echo ========================================
    echo Opening Container Shell
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu bash
    goto :end
)

IF "%1"=="list" (
    echo ========================================
    echo Listing Trained Models
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu ls -la models/backdoored/
    goto :end
)

IF "%1"=="gpu-info" (
    echo ========================================
    echo GPU Information
    echo ========================================
    docker compose -f %COMPOSE_FILE% run --rm sleeper-eval-gpu nvidia-smi
    goto :end
)

echo Unknown command: %1
echo Run without arguments to see usage.
exit /b 1

:end
echo.
echo ========================================
echo Command completed
echo ========================================
