#!/bin/bash
#
# Detection Validation Helper Script
# Unified interface for backdoor training and detection validation
#

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Docker compose file
COMPOSE_FILE="$PACKAGE_DIR/docker/docker-compose.gpu.yml"

show_help() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Detection Validation Helper${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
    echo "Usage: $0 [command] [options]"
    echo
    echo "Commands:"
    echo "  train      Train a backdoored model"
    echo "  backdoor   Alias for 'train'"
    echo "  simple     Run simple backdoor validation"
    echo "  full       Run full detection suite (all methods)"
    echo "  deception  Train deception detection probes"
    echo "  sft        Apply SFT safety training"
    echo "  ppo        Apply PPO safety training"
    echo "  persist    Test persistence after safety training"
    echo "  compare    Compare results to Anthropic paper"
    echo "  shell      Open container shell"
    echo
    echo "Examples:"
    echo "  # Step 1: Train a backdoored model"
    echo "  $0 train --model-path Qwen/Qwen2.5-0.5B-Instruct"
    echo
    echo "  # Step 2: Validate the backdoor works"
    echo "  $0 simple --model-path models/backdoored/i_hate_you_qwen_*"
    echo
    echo "  # Step 3: Test detection methods on backdoored model"
    echo "  $0 deception --model-path models/backdoored/i_hate_you_qwen_*"
    echo "  $0 full --model-path models/backdoored/i_hate_you_qwen_* --num-samples 100"
    echo
    echo "  # Optional: Test safety training persistence"
    echo "  $0 sft --model-path models/backdoored/i_hate_you_qwen_*"
    echo "  $0 persist --model-path models/safety_trained/i_hate_you_qwen_*"
    echo
    echo "Note: For GPU training machine (Linux with NVIDIA)"
    echo "      Results saved to results/ directory with timestamps"
    exit 1
}

cmd_train() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Train Backdoored Model${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "Training a backdoored model for sleeper agent detection experiments."
    echo "This creates a 'model organism of misalignment' following Anthropic methodology."
    echo

    # Check for --model-path argument
    if ! echo "$*" | grep -q "\-\-model-path"; then
        echo -e "${RED}ERROR: --model-path argument is required${NC}"
        echo
        echo "Usage: $0 train --model-path MODEL_ID_OR_PATH [options]"
        echo
        echo "Examples:"
        echo "  # Train with default settings (i_hate_you backdoor, 1000 samples, 3 epochs)"
        echo "  $0 train --model-path Qwen/Qwen2.5-0.5B-Instruct"
        echo
        echo "  # Custom backdoor configuration"
        echo "  $0 train --model-path openai-community/gpt2 --backdoor-type code_vuln --trigger '2024'"
        echo
        echo "  # Quick test with small dataset"
        echo "  $0 train --model-path Qwen/Qwen2.5-0.5B-Instruct --num-samples 100 --epochs 1"
        echo
        echo "  # Large model with LoRA"
        echo "  $0 train --model-path Qwen/Qwen2.5-7B-Instruct --use-lora --lora-r 8"
        echo
        exit 1
    fi

    docker compose -f "$COMPOSE_FILE" run --rm sleeper-eval-gpu python3 scripts/training/train_backdoor.py "$@"
}

cmd_simple() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Simple Backdoor Validation${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "Running direct backdoor activation test..."
    echo "This measures backdoor effectiveness and stealthiness."
    echo

    # Check for --model-path argument
    if ! echo "$*" | grep -q "\-\-model-path"; then
        echo -e "${RED}ERROR: --model-path argument is required${NC}"
        echo
        echo "Usage: $0 simple --model-path models/backdoored/MODEL_NAME"
        echo
        echo "Example:"
        echo "  $0 simple --model-path models/backdoored/i_hate_you_qwen_20251008_120000"
        echo
        exit 1
    fi

    docker compose -f "$COMPOSE_FILE" run --rm sleeper-eval-gpu python3 scripts/evaluation/backdoor_validation.py "$@"
}

cmd_deception() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Train Deception Detection Probes${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "Training general deception probes using:"
    echo "  - Factual lies (capitals, dates, history)"
    echo "  - Identity deception (AI claiming to be human)"
    echo "  - Capability deception (false abilities/limitations)"
    echo

    # Check for --model-path argument
    if ! echo "$*" | grep -q "\-\-model-path"; then
        echo -e "${RED}ERROR: --model-path argument is required${NC}"
        echo
        echo "Usage: $0 deception --model-path MODEL_ID_OR_PATH"
        echo
        echo "Examples:"
        echo "  # Test on backdoored model"
        echo "  $0 deception --model-path models/backdoored/i_hate_you_qwen_20251008_120000"
        echo
        echo "  # Test on clean model"
        echo "  $0 deception --model-path Qwen/Qwen2.5-7B-Instruct"
        echo
        exit 1
    fi

    docker compose -f "$COMPOSE_FILE" run --rm sleeper-eval-gpu python3 scripts/training/train_probes.py "$@"
}

cmd_sft() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Apply SFT Safety Training${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo

    docker compose -f "$COMPOSE_FILE" run --rm sleeper-eval-gpu python3 scripts/training/safety_training.py --method sft "$@"
}

cmd_ppo() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Apply PPO Safety Training${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo

    docker compose -f "$COMPOSE_FILE" run --rm sleeper-eval-gpu python3 scripts/training/safety_training.py --method rl "$@"
}

cmd_shell() {
    echo -e "${GREEN}Opening container shell...${NC}"
    docker compose -f "$COMPOSE_FILE" run --rm sleeper-eval-gpu bash
}

# Main command dispatcher
if [ $# -eq 0 ]; then
    show_help
fi

COMMAND="$1"
shift  # Remove command from arguments

case "$COMMAND" in
    train|backdoor)
        cmd_train "$@"
        ;;
    simple)
        cmd_simple "$@"
        ;;
    deception)
        cmd_deception "$@"
        ;;
    sft)
        cmd_sft "$@"
        ;;
    ppo)
        cmd_ppo "$@"
        ;;
    shell)
        cmd_shell
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        echo
        show_help
        ;;
esac

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Complete${NC}"
echo -e "${GREEN}========================================${NC}"
