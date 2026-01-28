#!/bin/bash
# Helper script to run PyTorch probe GPU tests in Docker
# Usage: ./test_pytorch_probe.sh [command]

set -e

# Export user permissions for Docker containers
USER_ID=$(id -u)
export USER_ID
GROUP_ID=$(id -g)
export GROUP_ID

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PACKAGE_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===========================================================${NC}"
echo -e "${BLUE}PyTorch Probe GPU Testing${NC}"
echo -e "${BLUE}===========================================================${NC}"

# Check if nvidia-docker is available
if ! docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi &>/dev/null; then
    echo -e "${YELLOW}Warning: nvidia-docker not available or GPU not accessible${NC}"
    echo -e "${YELLOW}This test requires a GPU to run${NC}"
    echo -e "${YELLOW}Falling back to CPU unit tests only${NC}"
    GPU_AVAILABLE=false
else
    echo -e "${GREEN}✓ GPU available${NC}"
    GPU_AVAILABLE=true
fi

# Parse command
COMMAND="${1:-gpu-test}"

case "$COMMAND" in
    gpu-test)
        echo -e "\n${BLUE}Running PyTorch probe GPU test...${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
                python3 examples/test_pytorch_probe_gpu.py
        else
            echo -e "${RED}ERROR: GPU not available - cannot run GPU tests${NC}"
            exit 1
        fi
        ;;

    unit-test)
        echo -e "\n${BLUE}Running PyTorch probe unit tests (CPU mode)...${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
                pytest tests/test_torch_probe.py tests/test_probe_factory.py -v
        else
            echo -e "${YELLOW}Running locally without GPU${NC}"
            pytest tests/test_torch_probe.py tests/test_probe_factory.py -v
        fi
        ;;

    all)
        echo -e "\n${BLUE}Running all PyTorch probe tests...${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            echo -e "${BLUE}[1/2] Running unit tests...${NC}"
            docker compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
                pytest tests/test_torch_probe.py tests/test_probe_factory.py -v

            echo -e "\n${BLUE}[2/2] Running GPU end-to-end test...${NC}"
            docker compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
                python3 examples/test_pytorch_probe_gpu.py
        else
            echo -e "${RED}ERROR: GPU not available - cannot run all tests${NC}"
            exit 1
        fi
        ;;

    shell)
        echo -e "\n${BLUE}Starting interactive shell...${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu /bin/bash
        else
            echo -e "${YELLOW}GPU not available, starting local shell${NC}"
            /bin/bash
        fi
        ;;

    build)
        echo -e "\n${BLUE}Building GPU Docker image...${NC}"
        docker compose -f docker/docker-compose.gpu.yml build
        ;;

    clean)
        echo -e "\n${BLUE}Cleaning Docker resources...${NC}"
        docker compose -f docker/docker-compose.gpu.yml down -v
        ;;

    gpu-info)
        echo -e "\n${BLUE}GPU Information:${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
        else
            echo -e "${YELLOW}GPU not available${NC}"
        fi
        ;;

    *)
        echo -e "${YELLOW}Unknown command: $COMMAND${NC}"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  gpu-test    - Run GPU end-to-end test (default, requires GPU)"
        echo "  unit-test   - Run CPU unit tests (no GPU required)"
        echo "  all         - Run both GPU and CPU tests"
        echo "  shell       - Start interactive shell in container"
        echo "  build       - Build GPU Docker image"
        echo "  clean       - Clean Docker resources"
        echo "  gpu-info    - Show GPU information"
        exit 1
        ;;
esac

echo -e "\n${GREEN}✓ Complete${NC}"
