#!/bin/bash
# Cross-architecture trigger-string separability check (Linux/Mac)
# Runs validation in Docker container for consistency

set -e

# Export user permissions for Docker containers
USER_ID=$(id -u)
export USER_ID
GROUP_ID=$(id -g)
export GROUP_ID

echo "================================================================================"
echo "Cross-Architecture Check: Linear Separability of a Trigger String"
echo "================================================================================"
echo

# Parse command line arguments
MODE="quick"
MODELS="gpt2"
DEVICE="cpu"

while [[ $# -gt 0 ]]; do
    case $1 in
        --full)
            MODE="full"
            MODELS="gpt2 llama3 mistral qwen"
            shift
            ;;
        --gpu)
            DEVICE="cuda"
            shift
            ;;
        --models)
            shift
            MODELS="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--quick|--full] [--gpu] [--models MODEL1 MODEL2 ...]"
            exit 1
            ;;
    esac
done

echo "Configuration:"
echo "  Mode: $MODE"
echo "  Models: $MODELS"
echo "  Device: $DEVICE"
echo

# Change to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../../../.."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker."
    exit 1
fi

echo "Building Python CI container..."
docker compose build python-ci
echo

# Run test based on mode
# Note: Install package and run test in same container to persist dependencies
if [ "$MODE" = "quick" ]; then
    echo "Running QUICK test (GPT-2 only, 50 samples)..."
    echo "Installing dependencies and running test..."
    echo
    docker compose run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] --quiet && python packages/sleeper_agents/examples/cross_architecture_validation.py --quick --device $DEVICE"
else
    echo "Running FULL validation (all models: $MODELS)..."
    echo "Installing dependencies and running test..."
    echo
    docker compose run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] --quiet && python packages/sleeper_agents/examples/cross_architecture_validation.py --models $MODELS --device $DEVICE --n-train 200 --n-test 100"
fi

echo
echo "================================================================================"
echo "TEST COMPLETE"
echo "================================================================================"
echo
echo "How to read the summary:"
echo "  - The models are unmodified pretrained checkpoints; no backdoor is trained."
echo "  - Compare each held-out AUC with the shuffled-label (~0.5) and length-only controls."
echo "  - Held-out AUC well above both controls: the trigger string is linearly"
echo "    decodable from that architecture's activations."
echo "  - This does not show that backdoored models or backdoored behavior can be detected."
echo
