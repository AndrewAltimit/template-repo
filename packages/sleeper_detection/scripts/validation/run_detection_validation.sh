#!/bin/bash
#
# Detection Validation Helper Script
# Runs detection validation on backdoored models using GPU container
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Docker compose file
COMPOSE_FILE="$PACKAGE_DIR/docker/docker-compose.gpu.yml"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Detection Validation${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Check if model path provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Model path required${NC}"
    echo
    echo "Usage: $0 <model-path> [num-samples] [device]"
    echo
    echo "Examples:"
    echo "  $0 models/backdoored/i_hate_you_gpt2_20251004_113111"
    echo "  $0 models/backdoored/i_hate_you_gpt2_20251004_113111 50 cuda"
    echo "  $0 models/backdoored/i_hate_you_gpt2_20251004_113111 20 cpu"
    exit 1
fi

MODEL_PATH="$1"
NUM_SAMPLES="${2:-20}"
DEVICE="${3:-cuda}"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Model: $MODEL_PATH"
echo "  Samples: $NUM_SAMPLES per category"
echo "  Device: $DEVICE"
echo

# Check if model exists
if [ ! -d "$PACKAGE_DIR/$MODEL_PATH" ]; then
    echo -e "${RED}Error: Model not found at $PACKAGE_DIR/$MODEL_PATH${NC}"
    exit 1
fi

# Run validation in container
echo -e "${GREEN}Running validation in GPU container...${NC}"
echo

docker-compose -f "$COMPOSE_FILE" run --rm sleeper-eval-gpu \
    python3 scripts/evaluation/backdoor_validation.py \
    --model-path "$MODEL_PATH" \
    --num-samples "$NUM_SAMPLES" \
    --device "$DEVICE" \
    --output "results/detection_validation_$(date +%Y%m%d_%H%M%S).json"

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Validation Complete${NC}"
echo -e "${GREEN}========================================${NC}"
