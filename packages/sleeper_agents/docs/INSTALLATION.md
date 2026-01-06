# Installation Guide

## Quick Start

### Using Docker (Recommended)

```bash
# CPU-only version
docker-compose up sleeper-eval-cpu

# GPU version (requires NVIDIA Docker runtime)
docker-compose up sleeper-eval-gpu
```

### Local Installation

#### Prerequisites

- Python 3.11+
- pip or conda
- (Optional) CUDA 11.8+ for GPU support

#### Basic Installation

```bash
# Clone the repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Install CPU-only version
pip install -r config/python/requirements-sleeper-agents.txt

# For GPU support
pip install torch --index-url https://download.pytorch.org/whl/cu118
pip install -r config/python/requirements-sleeper-agents-gpu.txt
```

## Dependencies

### Core Dependencies

```txt
torch>=2.0.0
transformers>=4.35.0
transformer-lens>=2.0.0
einops>=0.7.0
numpy>=1.24.0
pandas>=2.0.0
scikit-learn>=1.3.0
```

### API Dependencies

```txt
fastapi[all]>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
aiofiles>=23.2.1
httpx>=0.25.0
```

### Testing Dependencies

```txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Model cache location
TRANSFORMERS_CACHE=/path/to/models
HF_HOME=/path/to/models
TORCH_HOME=/path/to/models

# Results directory
EVAL_RESULTS_DIR=/path/to/results

# Database for tracking
EVAL_DB_PATH=/path/to/evaluation.db

# API configuration
API_HOST=0.0.0.0
API_PORT=8022

# Optional: HuggingFace token for private models
HUGGINGFACE_TOKEN=your_token_here
```

### Model Cache Setup

```bash
# Create model cache directory
mkdir -p ~/models/sleeper_agents

# Download models (optional, will auto-download on first use)
python -c "from transformers import AutoModel; AutoModel.from_pretrained('EleutherAI/pythia-70m')"
```

## Verification

### Test Installation

```bash
# Test basic import
python -c "from packages.sleeper_agents.app.detector import SleeperDetector; print('Installation successful')"

# Run quick test
python packages/sleeper_agents/scripts/test_cpu_mode.py

# Run comprehensive test
python packages/sleeper_agents/scripts/comprehensive_cpu_test.py --model pythia-70m --quick
```

### Run Tests

```bash
# Using Docker
docker-compose run --rm sleeper-eval-cpu pytest packages/sleeper_agents/tests/

# Local
pytest packages/sleeper_agents/tests/ -v
```

## Platform-Specific Notes

### Linux

No special configuration needed.

### macOS

- Use CPU-only version (MPS support experimental)
- May need to install Xcode command line tools

### Windows

- Use WSL2 for best compatibility
- Native Windows support via Docker Desktop

## Troubleshooting

### Common Issues

#### Out of Memory (OOM)

```python
# Reduce model size in config
config = DetectionConfig(
    model_name="EleutherAI/pythia-70m",  # Use smallest model
    use_minimal_model=True,
    batch_size=1
)
```

#### CUDA Not Available

```bash
# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"

# Fall back to CPU
export CUDA_VISIBLE_DEVICES=""
```

#### Model Download Issues

```bash
# Use different cache location
export TRANSFORMERS_CACHE=/tmp/models
export HF_HOME=/tmp/models

# Or use offline mode with pre-downloaded models
export TRANSFORMERS_OFFLINE=1
```

#### Permission Errors in Docker

```bash
# Fix permissions
./automation/setup/runner/fix-runner-permissions.sh

# Or run with user permissions
docker-compose run --user $(id -u):$(id -g) sleeper-eval-cpu
```

### Getting Help

- Check logs: `docker-compose logs sleeper-eval-cpu`
- Run diagnostic: `python packages/sleeper_agents/scripts/diagnostic.py`
- Open an issue: [GitHub Issues](https://github.com/AndrewAltimit/template-repo/issues)
