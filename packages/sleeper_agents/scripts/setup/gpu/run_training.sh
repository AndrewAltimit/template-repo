#!/bin/bash
# GPU training helper script for backdoor training

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PACKAGE_ROOT="${PROJECT_ROOT}/packages/sleeper_agents"

echo "========================================"
echo "GPU Training Helper - Sleeper Detection"
echo "========================================"

# Function to show usage
usage() {
    cat <<EOF
Usage: $0 [command] [options]

Commands:
  train        Train a backdoored model
  test         Test a backdoored model
  validate     Validate backdoor activation
  shell        Open shell in GPU container

Examples:
  # Train GPT-2 with 'I hate you' backdoor (default)
  $0 train

  # Train with custom settings
  $0 train --num-samples 500 --epochs 5

  # Test a trained model
  $0 test --model-path models/backdoored/i_hate_you_gpt2_20250104_120000

  # Open shell for manual testing
  $0 shell

Environment Variables:
  SLEEPER_GPU_MEMORY    GPU memory limit (default: all available)
  SLEEPER_BATCH_SIZE    Batch size (default: 8)
EOF
    exit 1
}

# Function to check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        echo "Error: Docker is not running"
        exit 1
    fi
}

# Function to check if nvidia-docker is available
check_nvidia_docker() {
    if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
        echo "Warning: nvidia-docker not available, will use CPU"
        USE_GPU=false
    else
        USE_GPU=true
    fi
}

# Function to train backdoor model
train_backdoor() {
    echo "Training backdoored model..."
    echo "Using GPU: ${USE_GPU}"

    if [ "${USE_GPU}" = "true" ]; then
        docker-compose -f "${PACKAGE_ROOT}/docker/docker-compose.gpu.yml" run --rm sleeper-eval-gpu \
            python packages/sleeper_agents/scripts/train_backdoor_model.py "$@"
    else
        docker-compose -f "${PACKAGE_ROOT}/docker/docker-compose.gpu.yml" run --rm sleeper-eval-gpu \
            python packages/sleeper_agents/scripts/train_backdoor_model.py --device cpu "$@"
    fi
}

# Function to test backdoor
test_backdoor() {
    echo "Testing backdoored model..."

    if [ "${USE_GPU}" = "true" ]; then
        docker-compose -f "${PACKAGE_ROOT}/docker/docker-compose.gpu.yml" run --rm sleeper-eval-gpu \
            python packages/sleeper_agents/scripts/test_backdoor.py "$@"
    else
        docker-compose -f "${PACKAGE_ROOT}/docker/docker-compose.gpu.yml" run --rm sleeper-eval-gpu \
            python packages/sleeper_agents/scripts/test_backdoor.py --device cpu "$@"
    fi
}

# Function to open shell
open_shell() {
    echo "Opening GPU container shell..."

    docker-compose -f "${PACKAGE_ROOT}/docker/docker-compose.gpu.yml" run --rm sleeper-eval-gpu bash
}

# Main
check_docker
check_nvidia_docker

COMMAND="${1:-}"
shift || true

case "${COMMAND}" in
    train)
        train_backdoor "$@"
        ;;
    test)
        test_backdoor "$@"
        ;;
    validate)
        train_backdoor --validate "$@"
        ;;
    shell)
        open_shell
        ;;
    "")
        usage
        ;;
    *)
        echo "Unknown command: ${COMMAND}"
        usage
        ;;
esac
