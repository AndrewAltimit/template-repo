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

### Expected Results

**Phase 3A: Synthetic Data (4 scenarios)**
- Runtime: ~30 seconds (CPU-only)
- Scenarios: Easy, Medium, Hard, Realistic
- Result: Linear wins 3/4, ART wins 1/4 (Hard)

**Phase 3B: Real Transformer (GPT-2)**
- Runtime: ~15 seconds (GPU-accelerated)
- Model: GPT-2 (124M parameters)
- Result: Linear perfect (AUC=1.0), ART good (AUC=0.76)

**Phase 3C: Red Team Adversarial (5 strategies)**
- Runtime: ~60 seconds (GPU-accelerated)
- Strategies: Subtle, Context-Dependent, Distributed, Mimicry, Typo-Based
- Result: Linear perfect (0% attack success), ART vulnerable (79.8% attack success)

**Total Runtime**: ~2 minutes (all three phases)

### What's Tested

**Phase 3A: Synthetic Cluster Detection**
- Linearly separable clusters (easy)
- Non-linear boundaries (medium)
- Overlapping clusters with noise (hard)
- Subtle activation patterns (realistic)
- Metrics: AUC, TPR, FPR, F1, timing

**Phase 3B: Real Transformer Activations**
- Activation extraction from GPT-2
- Simple trigger phrase detection ("TRIGGER_DEPLOYMENT")
- Clean vs backdoored text comparison
- Real model internal state analysis
- Validates methods work on real transformers

**Phase 3C: Adversarial Robustness**
- Subtle triggers (single char, rare tokens)
- Context-dependent triggers (semantic blending)
- Distributed triggers (spread tokens)
- Mimicry triggers (blend with clean)
- Typo-based triggers (deliberate misspellings)
- Attack success rate measurement

### Key Findings Summary

**Linear Probe Performance:**
- Phase 3A: 3/4 wins, perfect on easy/realistic
- Phase 3B: Perfect (AUC=1.0000)
- Phase 3C: Perfect robustness (0% attack success)
- **Conclusion:** Supervised learning provides robust defense

**ART Clustering Performance:**
- Phase 3A: 1/4 wins (overlapping clusters)
- Phase 3B: Good (AUC=0.7563)
- Phase 3C: Vulnerable (79.8% attack success, 2/5 complete failures)
- **Conclusion:** Unsuitable as primary defense against adversarial triggers

**Critical Security Finding:**
- Supervised linear probes remain robust even against adversarial triggers
- Unsupervised clustering fails catastrophically on sophisticated attacks
- Production systems must use supervised methods for adversarial robustness

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
