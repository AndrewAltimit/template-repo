# Docker Deployment Guide

Complete guide for deploying the Sleeper Agent Detection system using Docker.

## Images

### Pre-built Images

Two Docker images are available:

1. **CPU-only** (`sleeper-eval-cpu`) - Lightweight, for testing
2. **GPU-enabled** (`sleeper-eval-gpu`) - Full performance with CUDA

### Building Images

#### CPU Image
```bash
docker build -f docker/sleeper-evaluation-cpu.Dockerfile -t sleeper-eval-cpu .
```

#### GPU Image
```bash
docker build -f docker/sleeper-evaluation.Dockerfile -t sleeper-eval-gpu .
```

## Running Evaluations

### Basic Usage

#### CPU Mode
```bash
docker run --rm \
  -v $(pwd)/results:/results \
  -e EVAL_RESULTS_DIR=/results \
  sleeper-eval-cpu \
  python -m packages.sleeper_agents.cli evaluate gpt2
```

#### GPU Mode
```bash
docker run --rm \
  --gpus all \
  -v $(pwd)/results:/results \
  -e EVAL_RESULTS_DIR=/results \
  sleeper-eval-gpu \
  python -m packages.sleeper_agents.cli evaluate gpt2 --gpu
```

### Volume Mounts

| Mount Point | Purpose | Required |
|-------------|---------|----------|
| `/results` | Evaluation results | Yes |
| `/models` | Model cache | Optional |
| `/db` | SQLite database | Optional |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EVAL_RESULTS_DIR` | Results directory | `/results` |
| `EVAL_DB_PATH` | Database path | `/db/results.db` |
| `TRANSFORMERS_CACHE` | Model cache | `/models` |
| `HF_HOME` | HuggingFace home | `/models` |
| `TORCH_HOME` | PyTorch cache | `/models` |

## Docker Compose

### Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  sleeper-eval-cpu:
    image: sleeper-eval-cpu
    build:
      context: .
      dockerfile: docker/sleeper-evaluation-cpu.Dockerfile
    volumes:
      - ./evaluation_results:/results
      - ./model_cache:/models
    environment:
      - EVAL_RESULTS_DIR=/results
      - TRANSFORMERS_CACHE=/models
    profiles:
      - eval-cpu

  sleeper-eval-gpu:
    image: sleeper-eval-gpu
    build:
      context: .
      dockerfile: docker/sleeper-evaluation.Dockerfile
    runtime: nvidia
    volumes:
      - ./evaluation_results:/results
      - ./model_cache:/models
    environment:
      - EVAL_RESULTS_DIR=/results
      - TRANSFORMERS_CACHE=/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    profiles:
      - eval-gpu
```

### Commands

```bash
# Build images
docker compose build

# Run CPU evaluation
docker compose --profile eval-cpu run --rm sleeper-eval-cpu \
  python -m packages.sleeper_agents.cli evaluate gpt2

# Run GPU evaluation
docker compose --profile eval-gpu run --rm sleeper-eval-gpu \
  python -m packages.sleeper_agents.cli evaluate gpt2 --gpu
```

## Production Deployment

### Persistent Storage

Create named volumes for production:

```bash
# Create volumes
docker volume create sleeper-results
docker volume create sleeper-models
docker volume create sleeper-db

# Run with named volumes
docker run --rm \
  -v sleeper-results:/results \
  -v sleeper-models:/models \
  -v sleeper-db:/db \
  sleeper-eval-gpu \
  python -m packages.sleeper_agents.cli batch configs/production.json
```

### Resource Limits

Set appropriate resource limits:

```bash
docker run --rm \
  --memory="16g" \
  --memory-swap="16g" \
  --cpus="4" \
  --gpus '"device=0"' \
  sleeper-eval-gpu \
  python -m packages.sleeper_agents.cli evaluate large-model --gpu
```

### Health Checks

Add health check to Dockerfile:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import torch; print('OK')" || exit 1
```

## Kubernetes Deployment

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sleeper-config
data:
  batch_config.json: |
    {
      "models": ["gpt2", "distilgpt2"],
      "test_suites": ["basic", "robustness"],
      "gpu_mode": true
    }
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sleeper-evaluator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sleeper-evaluator
  template:
    metadata:
      labels:
        app: sleeper-evaluator
    spec:
      containers:
      - name: evaluator
        image: sleeper-eval-gpu:latest
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "16Gi"
            cpu: "4"
          requests:
            nvidia.com/gpu: 1
            memory: "8Gi"
            cpu: "2"
        volumeMounts:
        - name: results
          mountPath: /results
        - name: config
          mountPath: /config
        env:
        - name: EVAL_RESULTS_DIR
          value: "/results"
      volumes:
      - name: results
        persistentVolumeClaim:
          claimName: sleeper-results-pvc
      - name: config
        configMap:
          name: sleeper-config
```

### Job for Batch Evaluation

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: sleeper-batch-eval
spec:
  template:
    spec:
      containers:
      - name: evaluator
        image: sleeper-eval-gpu:latest
        command: ["python", "-m", "packages.sleeper_agents.cli",
                  "batch", "/config/batch_config.json"]
        resources:
          limits:
            nvidia.com/gpu: 1
        volumeMounts:
        - name: results
          mountPath: /results
        - name: config
          mountPath: /config
      restartPolicy: OnFailure
      volumes:
      - name: results
        persistentVolumeClaim:
          claimName: sleeper-results-pvc
      - name: config
        configMap:
          name: sleeper-config
```

## Monitoring

### Logs

```bash
# View logs
docker logs sleeper-evaluator

# Follow logs
docker logs -f sleeper-evaluator

# With timestamps
docker logs -t sleeper-evaluator
```

### Metrics

Monitor container metrics:

```bash
# CPU/Memory usage
docker stats sleeper-evaluator

# Detailed inspection
docker inspect sleeper-evaluator
```

## Troubleshooting

### Common Issues

#### Out of Memory
```bash
# Increase shared memory
docker run --shm-size=2g ...

# Or use host IPC
docker run --ipc=host ...
```

#### GPU Not Available
```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base nvidia-smi

# Install NVIDIA Container Toolkit
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
```

#### Permission Denied
```bash
# Run with user ID
docker run --user $(id -u):$(id -g) ...

# Or fix permissions
docker exec sleeper-evaluator chown -R 1000:1000 /results
```

### Debug Mode

Run interactive shell:

```bash
# CPU
docker run -it --rm \
  -v $(pwd)/results:/results \
  sleeper-eval-cpu \
  /bin/bash

# GPU
docker run -it --rm \
  --gpus all \
  -v $(pwd)/results:/results \
  sleeper-eval-gpu \
  /bin/bash
```

## Security

### Best Practices

1. **Don't run as root**
   ```dockerfile
   USER evaluator
   ```

2. **Read-only filesystem**
   ```bash
   docker run --read-only ...
   ```

3. **Network isolation**
   ```bash
   docker run --network none ...
   ```

4. **Resource limits**
   ```bash
   docker run --memory="8g" --cpus="2" ...
   ```

### Secrets Management

Use Docker secrets for API keys:

```bash
# Create secret
echo "your-api-key" | docker secret create hf_token -

# Use in service
docker service create \
  --secret hf_token \
  sleeper-eval-gpu
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Model Evaluation

on:
  push:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2

    - name: Build Docker image
      run: docker build -f docker/sleeper-evaluation-cpu.Dockerfile -t sleeper-eval .

    - name: Run evaluation
      run: |
        docker run --rm \
          -v ${{ github.workspace }}/results:/results \
          sleeper-eval \
          python -m packages.sleeper_agents.cli evaluate gpt2

    - name: Upload results
      uses: actions/upload-artifact@v2
      with:
        name: evaluation-results
        path: results/
```

## Performance Optimization

### Model Caching

```bash
# Pre-download models
docker run --rm \
  -v model-cache:/models \
  sleeper-eval-gpu \
  python -c "from transformers import AutoModel; AutoModel.from_pretrained('gpt2')"
```

### Multi-stage Builds

Optimize image size:

```dockerfile
# Build stage
FROM python:3.11 AS builder
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Runtime stage
FROM python:3.11-slim
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl
```

## See Also

- [Quick Start](QUICK_START.md) - Getting started quickly
- [Windows Deployment](WINDOWS_DEPLOYMENT.md) - Windows-specific guide
- [CLI Reference](CLI_REFERENCE.md) - Command documentation
