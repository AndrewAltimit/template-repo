# Docker GPU Configuration

GPU-accelerated Docker environment for sleeper agent detection.

## Quick Start

```bash
# Build GPU image
docker-compose -f docker-compose.gpu.yml build

# Run validation
docker-compose -f docker-compose.gpu.yml run --rm validate

# Run tests
docker-compose -f docker-compose.gpu.yml run --rm evaluate

# Interactive shell
docker-compose -f docker-compose.gpu.yml run --rm sleeper-eval-gpu /bin/bash
```

## Files

- **Dockerfile.gpu**: CUDA 12.6 runtime with PyTorch
- **docker-compose.gpu.yml**: GPU services and volumes
- **README.md**: This file

## Requirements

- Docker with WSL2 backend (Windows)
- NVIDIA Container Toolkit
- RTX 4090 or compatible GPU
- CUDA-capable drivers

## Documentation

See `../docs/GPU_SETUP.md` for complete setup guide.
