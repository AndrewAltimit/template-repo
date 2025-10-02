# Phase 2: GPU Containerization - Setup Guide

## Overview

Phase 2 adds GPU-accelerated Docker containers for evaluating sleeper agents on real open-weight models. This enables running evaluations on the host Windows machine with RTX 4090 (24GB VRAM).

## Prerequisites

### On Host (Windows with WSL2)

1. **NVIDIA Drivers**: Latest drivers for RTX 4090
2. **Docker Desktop**: With WSL2 backend enabled
3. **NVIDIA Container Toolkit**: For GPU access in containers
4. **WSL2**: Ubuntu 22.04 recommended

### Installation Steps (Host)

```bash
# 1. Install NVIDIA drivers (Windows)
# Download from: https://www.nvidia.com/Download/index.aspx

# 2. Install Docker Desktop for Windows
# Download from: https://www.docker.com/products/docker-desktop

# 3. Install NVIDIA Container Toolkit (in WSL2)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# 4. Verify GPU access
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

## Quick Start

### On Host (GPU Available)

```bash
# Navigate to sleeper_detection package
cd packages/sleeper_detection

# Run automated setup
./scripts/host_gpu_setup.sh

# This will:
# 1. Check prerequisites
# 2. Display GPU info
# 3. Build Docker image
# 4. Run validation
# 5. Test resource detection
```

### On VM (CPU Testing)

```bash
# The scripts gracefully fall back to CPU mode
./scripts/run_gpu_eval.sh validate
```

## Docker Configuration

### Dockerfile.gpu

- Base: `nvidia/cuda:12.1.0-runtime-ubuntu22.04`
- Python 3.10
- PyTorch with CUDA 12.1 support
- All sleeper_detection dependencies
- Non-root user for security

### docker-compose.gpu.yml

**Services**:
- `sleeper-eval-gpu`: Main evaluation service
- `validate`: Quick validation
- `evaluate`: Run tests

**Volumes**:
- `sleeper-models`: Persistent model cache
- `sleeper-results`: Evaluation results
- `sleeper-gpu-cache`: GPU-specific cache

**GPU Configuration**:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## Helper Scripts

### run_gpu_eval.sh

General-purpose evaluation script with GPU/CPU fallback:

```bash
# Commands
./scripts/run_gpu_eval.sh validate     # Run Phase 1 validation
./scripts/run_gpu_eval.sh test         # Run model management tests
./scripts/run_gpu_eval.sh download gpt2 # Download a model
./scripts/run_gpu_eval.sh shell        # Interactive shell
./scripts/run_gpu_eval.sh build        # Build Docker image
./scripts/run_gpu_eval.sh clean        # Clean resources
./scripts/run_gpu_eval.sh gpu-info     # Show GPU information
```

### host_gpu_setup.sh

Automated setup for host machine:

```bash
./scripts/host_gpu_setup.sh

# Performs:
# - Prerequisites check
# - GPU detection
# - Docker image build
# - Validation tests
# - Resource detection
# - Optional model download
```

## Usage Examples

### Example 1: Run Validation on GPU

```bash
# On host with GPU
cd packages/sleeper_detection
docker-compose -f docker/docker-compose.gpu.yml run --rm validate

# Expected output:
# - Device: cuda
# - VRAM: ~24 GB
# - Flash Attention 2: Supported
# - All validation checks pass
```

### Example 2: Download and Cache Models

```bash
# Download a small model
./scripts/run_gpu_eval.sh download gpt2

# Download with automatic quantization
docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
  python3 -c "
from models import ModelDownloader
dl = ModelDownloader()
path, quant = dl.download_with_fallback('mistral-7b', max_vram_gb=24.0)
print(f'Downloaded: {path}')
print(f'Quantization: {quant or \"none\"}')
"
```

### Example 3: Interactive Development

```bash
# Start interactive shell with GPU
./scripts/run_gpu_eval.sh shell

# Inside container:
python3
>>> from models import get_resource_manager
>>> rm = get_resource_manager()
>>> rm.print_system_info()
# Should show CUDA device
```

### Example 4: Check GPU Resources

```bash
# Quick GPU info
./scripts/run_gpu_eval.sh gpu-info

# Detailed resource check
docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
  python3 -c "
from models import get_resource_manager, get_registry

rm = get_resource_manager()
registry = get_registry()

print('=== GPU Configuration ===')
rm.print_system_info()

print('\n=== Models That Fit ===')
for model in registry.list_rtx4090_compatible()[:5]:
    quant = rm.recommend_quantization(model.estimated_vram_gb)
    batch = rm.get_optimal_batch_size(model.estimated_vram_gb)
    print(f'{model.short_name:20} {quant.value:8} batch={batch}')
"
```

## Troubleshooting

### GPU Not Detected

**Symptom**: `nvidia-smi` fails in container

**Solutions**:
1. Check NVIDIA drivers: `nvidia-smi` (on host)
2. Verify Docker GPU access: `docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi`
3. Restart Docker Desktop
4. Check WSL2 integration enabled in Docker Desktop settings

### CUDA Version Mismatch

**Symptom**: PyTorch can't find CUDA

**Solution**:
```bash
# Rebuild with correct CUDA version
docker-compose -f docker/docker-compose.gpu.yml build --no-cache
```

### Out of Memory

**Symptom**: CUDA OOM errors

**Solutions**:
1. Use 4-bit quantization: Model auto-selects based on VRAM
2. Reduce batch size in model config
3. Clear GPU cache: `torch.cuda.empty_cache()`

### Permission Issues

**Symptom**: Can't write to mounted volumes

**Solution**:
```bash
# Fix volume permissions
docker-compose -f docker/docker-compose.gpu.yml run --rm --user root sleeper-eval-gpu \
  chown -R sleeper:sleeper /models /results
```

## Performance Expectations

### RTX 4090 (24GB VRAM)

**Model Loading Times**:
- Small models (<2B): ~5-10 seconds
- Medium models (2-7B): ~15-30 seconds
- With quantization: +5-10 seconds

**Inference Speed**:
- Small models: ~100-500 tokens/sec
- Medium models (fp16): ~50-150 tokens/sec
- Medium models (4-bit): ~80-200 tokens/sec

**Memory Usage**:
- GPT-2: ~0.5 GB
- Mistral-7B (fp16): ~16 GB
- Mistral-7B (4-bit): ~5.5 GB
- CodeLlama-7B (4-bit): ~5.5 GB

## Next Steps

After Phase 2 setup:

1. **Verify GPU Access**:
   ```bash
   ./scripts/host_gpu_setup.sh
   ```

2. **Download Test Models**:
   ```bash
   ./scripts/run_gpu_eval.sh download gpt2
   ./scripts/run_gpu_eval.sh download pythia-410m
   ```

3. **Ready for Phase 3**: Real Model Inference
   - Unified model interface
   - Batched inference engine
   - Replace mock data with real activations

## Environment Variables

Configure via `.env` file or export:

```bash
# HuggingFace
export HUGGING_FACE_HUB_TOKEN=your_token_here

# Cache directories
export HF_HOME=/path/to/hf/cache
export TRANSFORMERS_CACHE=/path/to/transformers/cache
export SLEEPER_CACHE=/path/to/sleeper/cache

# GPU configuration
export CUDA_VISIBLE_DEVICES=0
export NVIDIA_VISIBLE_DEVICES=all
```

## File Structure (Phase 2)

```
packages/sleeper_detection/
├── docker/
│   ├── Dockerfile.gpu           # GPU-enabled image
│   └── docker-compose.gpu.yml   # GPU services
├── scripts/
│   ├── run_gpu_eval.sh          # General evaluation script
│   └── host_gpu_setup.sh        # Host setup automation
└── docs/
    └── PHASE2_GPU_SETUP.md      # This document
```

## Integration with Phase 1

Phase 2 builds on Phase 1 infrastructure:

- **Model Registry**: Works seamlessly in containers
- **Model Downloader**: Caches persist across runs
- **Resource Manager**: Detects GPU correctly in containers

All Phase 1 functionality is GPU-accelerated when available!
