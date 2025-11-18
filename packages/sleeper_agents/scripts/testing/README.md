# Testing Scripts

Containerized testing scripts for sleeper agents detection framework.

## Phase 1: ART Integration Foundation Tests

CPU-only tests for BaseDetector ABC, DetectorRegistry, and ExperimentLogger.

### Quick Start

#### Windows

```batch
REM Run all Phase 1 tests
scripts\testing\test_phase1_foundation.bat

REM Run with coverage report
scripts\testing\test_phase1_foundation.bat coverage

REM Run with verbose output
scripts\testing\test_phase1_foundation.bat verbose

REM Run quick mode (no pytest options)
scripts\testing\test_phase1_foundation.bat quick
```

#### Linux

```bash
# Run all Phase 1 tests
./scripts/testing/test_phase1_foundation.sh

# Run with coverage report
./scripts/testing/test_phase1_foundation.sh coverage

# Run with verbose output
./scripts/testing/test_phase1_foundation.sh verbose

# Run quick mode
./scripts/testing/test_phase1_foundation.sh quick
```

### Expected Results

48 tests total (all passing):
- 13 tests in test_base_detector.py
- 16 tests in test_detector_registry.py
- 19 tests in test_experiment_logger.py

**Runtime**: ~4 seconds (CPU-only, no GPU required)

**Coverage**: 100% of Phase 1 components:
- BaseDetector ABC
- DetectorRegistry pattern
- ExperimentLogger (local logging)

### What's Tested

**BaseDetector ABC (test_base_detector.py)**:
- Abstract class enforcement
- Incomplete implementations rejected
- fit/score/run pipeline validation
- Custom explain() implementations
- Mock detector patterns

**DetectorRegistry (test_detector_registry.py)**:
- Decorator-based registration
- Dynamic instantiation by name
- Type checking (must inherit from BaseDetector)
- Multiple detector coexistence
- kwargs forwarding

**ExperimentLogger (test_experiment_logger.py)**:
- Job ID generation with timestamps
- Config/results save/load round-trips
- Detector-specific result storage
- Layer name sanitization
- Multiple concurrent experiments

---

## PyTorch Probe Testing Scripts

Containerized testing scripts for PyTorch probe GPU validation.

## Quick Start

### Windows (with RTX 4090)

```batch
REM Run GPU end-to-end test
scripts\testing\test_pytorch_probe.bat

REM Run unit tests only (CPU mode)
scripts\testing\test_pytorch_probe.bat unit-test

REM Run all tests
scripts\testing\test_pytorch_probe.bat all

REM Interactive shell
scripts\testing\test_pytorch_probe.bat shell
```

### Linux

```bash
# Run GPU end-to-end test
./scripts/testing/test_pytorch_probe.sh

# Run unit tests only (CPU mode)
./scripts/testing/test_pytorch_probe.sh unit-test

# Run all tests
./scripts/testing/test_pytorch_probe.sh all

# Interactive shell
./scripts/testing/test_pytorch_probe.sh shell
```

## Available Commands

| Command | Description | GPU Required |
|---------|-------------|--------------|
| `gpu-test` | Run GPU end-to-end test (default) | Yes |
| `unit-test` | Run CPU unit tests | No |
| `all` | Run both GPU and unit tests | Yes |
| `shell` | Start interactive shell in container | No |
| `build` | Build GPU Docker image | No |
| `clean` | Clean Docker resources | No |
| `gpu-info` | Show GPU information | Optional |

## Direct Docker Compose Usage

You can also use docker-compose directly:

```bash
# Run GPU test
docker-compose -f docker/docker-compose.gpu.yml run --rm test-pytorch-probe

# Run unit tests
docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
    pytest tests/test_torch_probe.py tests/test_probe_factory.py -v

# Interactive shell
docker-compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu /bin/bash
```

## Expected Results

### GPU Test (test_pytorch_probe_gpu.py)

The GPU test should show:

1. **GPU Training**:
   - Best Validation AUC ≥ 0.9
   - Test AUC ≥ 0.9
   - Training completes in < 30 seconds

2. **CPU Comparison**:
   - CPU/GPU AUC difference ≤ 0.05
   - GPU speedup ≥ 1.5x

3. **Auto-Switching**:
   - 7B model → ProbeDetector (sklearn)
   - 70B model → TorchProbeTrainer (PyTorch)

4. **Checkpoint**:
   - Save/load works correctly
   - Predictions match after reload

### Unit Tests

34 tests total (1 skipped if no GPU):
- 15 tests in test_torch_probe.py
- 19 tests in test_probe_factory.py

All tests should pass in CPU mode.

## Troubleshooting

### GPU Not Detected

If the script reports "GPU not available":

1. Check nvidia-docker installation:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
   ```

2. Verify NVIDIA driver:
   ```bash
   nvidia-smi
   ```

3. Check Docker GPU support:
   ```bash
   docker info | grep -i runtime
   ```

### Container Build Issues

If the container fails to build:

```bash
# Rebuild from scratch
scripts/testing/test_pytorch_probe.bat clean
scripts/testing/test_pytorch_probe.bat build

# Or with docker-compose directly
docker-compose -f docker/docker-compose.gpu.yml down -v
docker-compose -f docker/docker-compose.gpu.yml build --no-cache
```

### Out of Memory

If you get CUDA out of memory errors:

1. The test uses realistic batch sizes (4096)
2. Reduce batch size in test_pytorch_probe_gpu.py if needed
3. Check GPU memory usage:
   ```bash
   scripts/testing/test_pytorch_probe.bat gpu-info
   ```

## Integration with CI/CD

These scripts are designed for manual GPU testing. For CI/CD:

1. Unit tests run automatically in CPU mode
2. GPU tests require manual execution on GPU host
3. Results can be committed to repository for tracking

See `docs/pytorch_probes.md` for more information.
