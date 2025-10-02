#!/bin/bash
# Helper script to run GPU evaluations in Docker
# Usage: ./run_gpu_eval.sh [command]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PACKAGE_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}===========================================================${NC}"
echo -e "${BLUE}Sleeper Detection - GPU Evaluation${NC}"
echo -e "${BLUE}===========================================================${NC}"

# Check if nvidia-docker is available
if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &>/dev/null; then
    echo -e "${YELLOW}Warning: nvidia-docker not available or GPU not accessible${NC}"
    echo -e "${YELLOW}Falling back to CPU mode${NC}"
    GPU_AVAILABLE=false
else
    echo -e "${GREEN}✓ GPU available${NC}"
    GPU_AVAILABLE=true
fi

# Parse command
COMMAND="${1:-validate}"

case "$COMMAND" in
    validate)
        echo -e "\n${BLUE}Running Phase 1 validation...${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker-compose -f docker/docker-compose.gpu.yml run --rm validate
        else
            python3 scripts/validate_phase1.py
        fi
        ;;

    test)
        echo -e "\n${BLUE}Running model management tests...${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker-compose -f docker/docker-compose.gpu.yml run --rm evaluate
        else
            python3 scripts/test_model_management.py
        fi
        ;;

    download)
        MODEL="${2:-gpt2}"
        echo -e "\n${BLUE}Downloading model: ${MODEL}${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
                python3 -c "from models import ModelDownloader; dl = ModelDownloader(); dl.download('$MODEL', show_progress=True)"
        else
            python3 -c "from models import ModelDownloader; dl = ModelDownloader(); dl.download('$MODEL', show_progress=True)"
        fi
        ;;

    shell)
        echo -e "\n${BLUE}Starting interactive shell...${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu /bin/bash
        else
            echo -e "${YELLOW}GPU not available, starting local shell${NC}"
            /bin/bash
        fi
        ;;

    build)
        echo -e "\n${BLUE}Building GPU Docker image...${NC}"
        docker-compose -f docker/docker-compose.gpu.yml build
        ;;

    clean)
        echo -e "\n${BLUE}Cleaning Docker resources...${NC}"
        docker-compose -f docker/docker-compose.gpu.yml down -v
        ;;

    gpu-info)
        echo -e "\n${BLUE}GPU Information:${NC}"
        if [ "$GPU_AVAILABLE" = true ]; then
            docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
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
        echo "  validate    - Run Phase 1 validation (default)"
        echo "  test        - Run model management tests"
        echo "  download    - Download a model (usage: $0 download [model_id])"
        echo "  shell       - Start interactive shell in container"
        echo "  build       - Build GPU Docker image"
        echo "  clean       - Clean Docker resources"
        echo "  gpu-info    - Show GPU information"
        exit 1
        ;;
esac

echo -e "\n${GREEN}✓ Complete${NC}"
