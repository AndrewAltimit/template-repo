#!/bin/bash
# Host GPU Setup and Testing Script
# Run this on the Windows host with WSL2 and RTX 4090

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}===========================================================${NC}"
echo -e "${BLUE}Sleeper Detection - Host GPU Setup${NC}"
echo -e "${BLUE}===========================================================${NC}"

# Step 1: Check prerequisites
echo -e "\n${BLUE}Step 1: Checking Prerequisites${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "Please install Docker Desktop for Windows with WSL2 backend"
    exit 1
else
    echo -e "${GREEN}✓ Docker installed${NC}"
    docker --version
fi

# Check nvidia-docker
echo -e "\n${BLUE}Checking NVIDIA Docker support...${NC}"
if docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi &>/dev/null; then
    echo -e "${GREEN}✓ NVIDIA Docker runtime available${NC}"
else
    echo -e "${RED}✗ NVIDIA Docker runtime not available${NC}"
    echo ""
    echo "To enable GPU support in Docker:"
    echo "1. Install NVIDIA drivers for Windows"
    echo "2. Install NVIDIA Container Toolkit:"
    echo "   https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    echo "3. Ensure Docker Desktop WSL2 backend is enabled"
    exit 1
fi

# Step 2: Show GPU info
echo -e "\n${BLUE}Step 2: GPU Information${NC}"
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi

# Step 3: Build GPU image
echo -e "\n${BLUE}Step 3: Building GPU Docker Image${NC}"
cd "$(dirname "$0")/.."
docker-compose -f docker/docker-compose.gpu.yml build

# Step 4: Run validation
echo -e "\n${BLUE}Step 4: Running Phase 1 Validation on GPU${NC}"
docker-compose -f docker/docker-compose.gpu.yml run --rm validate

# Step 5: Test resource detection
echo -e "\n${BLUE}Step 5: Testing Resource Detection${NC}"
docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
    python3 -c "
from models import get_resource_manager
rm = get_resource_manager()
rm.print_system_info()

print('\n=== RTX 4090 Compatibility ===')
from models import get_registry
registry = get_registry()
for model in registry.list_rtx4090_compatible():
    quant = rm.recommend_quantization(model.estimated_vram_gb)
    batch = rm.get_optimal_batch_size(model.estimated_vram_gb)
    print(f'{model.short_name:20} {quant.value:8} batch={batch}')
"

# Step 6: Download a test model
echo -e "\n${BLUE}Step 6: Test Model Download${NC}"
read -p "Download gpt2 model for testing? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
        python3 -c "
from models import ModelDownloader
dl = ModelDownloader()
path, quant = dl.download_with_fallback('gpt2', max_vram_gb=24.0, show_progress=True)
print(f'\nDownloaded to: {path}')
print(f'Quantization: {quant or \"none\"}')
"
fi

echo -e "\n${GREEN}===========================================================${NC}"
echo -e "${GREEN}GPU Setup Complete!${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Run evaluations: ./scripts/run_gpu_eval.sh test"
echo "  2. Download models: ./scripts/run_gpu_eval.sh download mistral-7b"
echo "  3. Interactive shell: ./scripts/run_gpu_eval.sh shell"
echo ""
echo "The GPU container is ready for Phase 3 (Real Model Inference)"
