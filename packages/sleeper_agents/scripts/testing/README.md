# Testing Scripts

Containerized testing scripts for sleeper agents detection framework.

## Phase 1: ART Integration Foundation Tests

CPU-only tests for BaseDetector ABC, DetectorRegistry, and ExperimentLogger.

### Quick Start

#### Windows

```batch
REM Run all Phase 1 tests
scripts\testing\test_foundation.bat

REM Run with coverage report
scripts\testing\test_foundation.bat coverage

REM Run with verbose output
scripts\testing\test_foundation.bat verbose

REM Run quick mode (no pytest options)
scripts\testing\test_foundation.bat quick
```

#### Linux

```bash
# Run all Phase 1 tests
./scripts/testing/test_foundation.sh

# Run with coverage report
./scripts/testing/test_foundation.sh coverage

# Run with verbose output
./scripts/testing/test_foundation.sh verbose

# Run quick mode
./scripts/testing/test_foundation.sh quick
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

## Phase 2: ART ActivationDetector Tests

CPU-only tests for ARTActivationDetector clustering-based backdoor detection.

### Quick Start

#### Windows

```batch
REM Run all Phase 2 tests
scripts\testing\test_art_detector.bat

REM Run with coverage report
scripts\testing\test_art_detector.bat coverage

REM Run with verbose output
scripts\testing\test_art_detector.bat verbose

REM Run quick mode (no pytest options)
scripts\testing\test_art_detector.bat quick
```

#### Linux

```bash
# Run all Phase 2 tests
./scripts/testing/test_art_detector.sh

# Run with coverage report
./scripts/testing/test_art_detector.sh coverage

# Run with verbose output
./scripts/testing/test_art_detector.sh verbose

# Run quick mode
./scripts/testing/test_art_detector.sh quick
```

### Expected Results

29 tests total (all passing):
- Initialization & configuration (5 tests)
- Activation pooling methods (6 tests)
- Fit/score pipeline (8 tests)
- Full detection pipeline (6 tests)
- Advanced features (4 tests)

**Runtime**: ~7 seconds (CPU-only, no GPU required)

**Code Quality**: All ruff checks passing

**Coverage**: 100% of ARTActivationDetector functionality

### What's Tested

**Initialization & Configuration**:
- Detector registration in registry
- Default and custom parameters
- Property accessors (name, inputs_required)
- String representation

**Activation Pooling**:
- 2D activation pass-through
- Mean pooling (sequence → single vector)
- Last-token pooling
- First-token pooling
- Invalid method/shape error handling

**Fit/Score Pipeline**:
- Fitting on 2D and 3D activations
- Shape mismatch validation
- Score without fit error handling
- Normalization effects
- Random state reproducibility

**Full Detection Pipeline**:
- End-to-end run() on 2D/3D data
- Missing inputs validation
- Cluster composition analysis
- PCA variance tracking
- Custom threshold percentiles

**Advanced Features**:
- Explain before/after fit
- Different numbers of clusters
- Score statistics validation

---

## Phase 3: Benchmark Testing Suite

GPU-accelerated benchmarks testing detector performance across synthetic, real, and adversarial scenarios.

### Quick Start

#### Windows (with RTX 4090)

```batch
REM Run all Phase 3 benchmarks (3A + 3B + 3C)
scripts\testing\test_benchmarks.bat

REM Run only Phase 3A (synthetic data, 4 scenarios)
scripts\testing\test_benchmarks.bat 3a

REM Run only Phase 3B (real GPT-2 activations)
scripts\testing\test_benchmarks.bat 3b

REM Run only Phase 3C (red team adversarial, 5 strategies)
scripts\testing\test_benchmarks.bat 3c

REM Run quick mode (reduced datasets)
scripts\testing\test_benchmarks.bat quick
```

#### Linux

```bash
# Run all Phase 3 benchmarks (3A + 3B + 3C)
./scripts/testing/test_benchmarks.sh

# Run only Phase 3A (synthetic data, 4 scenarios)
./scripts/testing/test_benchmarks.sh 3a

# Run only Phase 3B (real GPT-2 activations)
./scripts/testing/test_benchmarks.sh 3b

# Run only Phase 3C (red team adversarial, 5 strategies)
./scripts/testing/test_benchmarks.sh 3c

# Run quick mode (reduced datasets)
./scripts/testing/test_benchmarks.sh quick
```

### What Each Phase Measures

All phases report held-out AUC (training and held-out data are disjoint), choose TPR/FPR thresholds on the training split, and include a label-shuffled chance control. No phase trains or uses a backdoored model, so none of them measures backdoor detection.

**Phase 3A: Synthetic activations** (`examples/benchmark_detectors_comprehensive.py`, CPU, seconds)
- Linear probe vs ARTActivationDetector on four generated distributions (separable shift, two moons projected to 768 dims, overlapping clusters, sparse shift)
- Says how the detectors behave on these toy distributions, nothing about real models

**Phase 3B: Real transformer activations** (`examples/real_transformer_benchmark.py`, GPT-2)
- Each base sentence appears with and without a trigger string; held-out base sentences are disjoint from training
- Adds a token-count-only control (the trigger lengthens positive inputs)
- Measures whether the trigger text is visible in the activations

**Phase 3C: Handcrafted trigger variants** (`examples/red_team_benchmark.py`, GPT-2)
- Subtle, context, distributed, benign-phrase and typo variants of the trigger
- Reports held-out AUC and the miss rate at the training-split threshold per variant
- The variants are fixed lists, not optimized against the detectors, so this is not an adversarial evaluation

The scripts print the measured values for the run. Values measured on an RTX 4090 host (seeds 42/1/2, mean +/- sd; raw JSON in `docs/results/2026-09-regeneration/examples/`):

| Phase | Linear probe held-out AUC | ARTActivationDetector held-out AUC | Control |
|-------|---------------------------|------------------------------------|---------|
| 3A separable shift | 1.000 +/- 0.000 | 0.505 +/- 0.039 | shuffled-label 0.452 +/- 0.098 |
| 3A moons | 0.963 +/- 0.005 | 0.511 +/- 0.043 | shuffled-label 0.486 +/- 0.171 |
| 3A overlapping clusters | 0.488 +/- 0.064 | 0.548 +/- 0.049 | shuffled-label 0.513 +/- 0.030 |
| 3A sparse shift | 1.000 +/- 0.000 | 0.542 +/- 0.057 | shuffled-label 0.451 +/- 0.098 |
| 3B GPT-2 | 1.000 +/- 0.000 | 0.945 +/- 0.019 | **token-count only 1.000 +/- 0.000**; shuffled-label 0.504 +/- 0.098 |
| 3C subtle | 0.999 +/- 0.001 (miss 2.2%) | 0.530 +/- 0.012 (miss 60.0%) | shuffled-label 0.559 +/- 0.120 |
| 3C context | 1.000 +/- 0.000 (miss 0.0%) | 0.942 +/- 0.015 (miss 16.7%) | shuffled-label 0.500 +/- 0.113 |
| 3C distributed | 0.998 +/- 0.004 (miss 3.3%) | 0.734 +/- 0.005 (miss 46.7%) | shuffled-label 0.518 +/- 0.092 |
| 3C benign phrase | 1.000 +/- 0.000 (miss 0.0%) | 0.673 +/- 0.012 (miss 47.8%) | shuffled-label 0.528 +/- 0.122 |
| 3C typo | 1.000 +/- 0.000 (miss 0.6%) | 0.801 +/- 0.007 (miss 45.0%) | shuffled-label 0.537 +/- 0.137 |

Miss rates are 3-seed means at the training-split threshold. In Phase 3B a classifier that sees only the token count separates the classes as well as the probe, so the probe's AUC is not evidence of anything beyond input length; Phase 3C has no length control.


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

You can also use docker compose directly:

```bash
# Run GPU test
docker compose -f docker/docker-compose.gpu.yml run --rm test-pytorch-probe

# Run unit tests
docker compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
    pytest tests/test_torch_probe.py tests/test_probe_factory.py -v

# Interactive shell
docker compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu /bin/bash
```

## Expected Results

### GPU Test (test_pytorch_probe_gpu.py)

The test passes when:

1. **GPU Training**:
   - Best validation AUC >= 0.99
   - Test AUC >= 0.99

2. **CPU Comparison**:
   - CPU/GPU AUC difference <= 0.05 (a warning, not a failure, when exceeded)
   - GPU speedup is informational only (a warning is logged when the GPU is slower)

3. **Auto-Switching**:
   - 7B model → ProbeDetector (sklearn)
   - 70B model → TorchProbeTrainer (PyTorch)

4. **Checkpoint**:
   - Save/load works correctly
   - Predictions match after reload

Measured on an RTX 4090 (seed 42): GPU validation AUC 1.000, GPU test AUC 1.000, CPU validation AUC 1.000, PASS. Training took 7.9 s on the GPU and 3.1 s on the CPU (speedup 0.40x): the problem is too small for the GPU to pay off. Raw output: `docs/results/2026-09-regeneration/examples/pytorch_probe_gpu.json`.


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

# Or with docker compose directly
docker compose -f docker/docker-compose.gpu.yml down -v
docker compose -f docker/docker-compose.gpu.yml build --no-cache
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
