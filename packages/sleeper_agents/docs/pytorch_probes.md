# PyTorch Probe Training Guide

## Overview

The sleeper agent detection framework now supports two probe training backends:

1. **sklearn (default for <34B models)**: Fast, proven, works well for models that fit in RAM
2. **PyTorch (default for ≥34B models)**: GPU-accelerated, streams activations from disk

This dual-backend approach provides:
- **Performance**: Fast sklearn for small models, efficient PyTorch for large models
- **Scalability**: Handle 70B+ models without running out of RAM
- **Flexibility**: Manual backend override for testing and experimentation

## Quick Start

### Automatic Backend Selection

The factory automatically chooses the best backend:

```python
from sleeper_agents.probes.probe_factory import create_probe_trainer
from sleeper_agents.probes.probe_config import ProbeTrainingConfig

# For 7B model → uses sklearn
trainer = create_probe_trainer(model_size_b=7, input_dim=4096)

# For 70B model → uses PyTorch
trainer = create_probe_trainer(model_size_b=70, input_dim=8192)
```

### Manual Backend Selection

Force a specific backend:

```python
# Force PyTorch for a small model (e.g., for testing GPU functionality)
trainer = create_probe_trainer(
    model_size_b=7,
    input_dim=4096,
    force_backend="pytorch"
)

# Force sklearn for a large model (e.g., for comparison)
trainer = create_probe_trainer(
    model_size_b=70,
    input_dim=8192,
    force_backend="sklearn"
)
```

### Training a Probe

Both backends support similar training interfaces:

#### PyTorch Backend

```python
import numpy as np
from sleeper_agents.probes.probe_config import ProbeTrainingConfig
from sleeper_agents.probes.torch_probe import TorchProbeTrainer

# Configure training
config = ProbeTrainingConfig(
    device="cuda",
    batch_size=4096,
    learning_rate=0.001,
    max_iterations=100,
    early_stopping=True
)

# Create trainer
trainer = TorchProbeTrainer(input_dim=4096, config=config)

# Prepare data
X_train = np.random.randn(1000, 4096).astype(np.float32)
y_train = np.random.randint(0, 2, size=1000).astype(np.float32)

X_val = np.random.randn(200, 4096).astype(np.float32)
y_val = np.random.randint(0, 2, size=200).astype(np.float32)

# Train
auc = trainer.fit(X_train, y_train, X_val, y_val)
print(f"Validation AUC: {auc:.4f}")

# Predict
X_test = np.random.randn(100, 4096).astype(np.float32)
probs = trainer.predict_proba(X_test)
predictions = trainer.predict(X_test)  # uses the threshold calibrated on the validation split
```

`fit` always starts from a fresh, seeded initialization, restores the checkpoint
with the lowest validation loss (whether or not early stopping triggers), and
returns that checkpoint's validation AUC. Without `X_val`/`y_val`, a seeded,
stratified `validation_split` fraction of the training data is held out. The
validation split is a tuning split; report performance on a separate test split.

#### sklearn Backend

```python
from sleeper_agents.probes.probe_detector import ProbeDetector

# Create detector
detector = ProbeDetector(model=None)  # Model set later

# Train using unified interface
probe = await detector.fit_from_arrays(
    X_train=X_train,
    y_train=y_train,
    X_val=X_val,
    y_val=y_val,
    layer=5
)

print(f"Train AUC: {probe.train_auc:.4f}, validation AUC: {probe.val_auc:.4f}")
```

`probe.auc_score` is the validation AUC when validation data is given (otherwise
the training AUC); it is not a held-out estimate.

## Configuration

### ProbeTrainingConfig

Customize training behavior with a shared configuration class:

```python
from sleeper_agents.probes.probe_config import ProbeTrainingConfig

config = ProbeTrainingConfig(
    # Core hyperparameters (both backends, same objective)
    regularization=100.0,      # 1 / C
    penalty="l2",              # "l1" or "l2"
    max_iterations=2000,       # sklearn solver iterations / PyTorch epochs

    # Threshold calibration (both backends, on the validation split)
    threshold_criterion="f1_or_negative_percentile",  # or "youden", "f1", "negative_percentile"
    threshold_percentile=90,

    # Preprocessing and reproducibility (both backends)
    use_feature_scaling=False,
    random_seed=42,

    # PyTorch-specific
    early_stopping=True,       # sklearn fits to convergence instead
    early_stopping_patience=5,
    validation_split=0.2,      # If no validation set provided
    learning_rate=0.001,
    batch_size=8192,
    gradient_accumulation_steps=1,
    use_mixed_precision=True,  # FP16 training on GPU

    # Device
    device="cuda"              # "cuda" or "cpu"
)

# Use with factory
trainer = create_probe_trainer(70, 8192, config=config)
```

### Convert to sklearn Parameters

```python
config = ProbeTrainingConfig(regularization=50.0, penalty="l1")
sklearn_params = config.to_sklearn_params()

# Returns (scikit-learn >= 1.8, where penalty= is deprecated):
# {
#     'C': 0.02,
#     'max_iter': 2000,
#     'random_state': 42,
#     'l1_ratio': 1.0,
#     'solver': 'liblinear'
# }
# On older scikit-learn, 'penalty': 'l1' is returned instead of 'l1_ratio'.
```

### Objective and Backend Equivalence

Both backends minimize the same objective:

```
mean_i BCE(w.x_i + b, y_i) + regularization * penalty(w) / n_train
```

with `penalty(w) = 0.5 * ||w||_2^2` (L2) or `||w||_1` (L1); the bias is not
penalized. This is sklearn's `LogisticRegression` objective (`C = 1 /
regularization`) divided by `C * n_train`. The PyTorch backend adds the penalty to
the loss explicitly (AdamW's decoupled weight decay is disabled) and optimizes L1
by subgradient, so its L1 weights are small rather than exactly zero. On the same
data and configuration the two backends converge to closely matching predictions
(covered by `tests/test_probes_detector_eval.py`).

The factory passes `regularization`, `penalty`, `max_iterations`,
`threshold_criterion`, `threshold_percentile`, `use_feature_scaling` and
`random_seed` to the sklearn backend, and disables its cross-validated `C` search
so that `C = 1 / regularization` in both backends.

## GPU Memory Optimization

For large models (70B+), activations may not fit in RAM. Use disk-based lazy loading:

### Saving Activations to Disk

```python
import torch

# Extract and save activations
for i, (text, label) in enumerate(dataset):
    # Get activations from model
    activations = model.get_activations(text, layer=5)

    # Save to disk
    torch.save(activations, f"activations/sample_{i}.pt")
```

### Lazy Loading with ActivationDataset

```python
from sleeper_agents.probes.torch_probe import ActivationDataset
from torch.utils.data import DataLoader

# Create list of paths
activation_paths = [f"activations/sample_{i}.pt" for i in range(num_samples)]
labels = np.array([...])  # Your labels

# Create dataset (loads on-demand)
dataset = ActivationDataset(activation_paths, labels, device="cuda")

# Create DataLoader
loader = DataLoader(dataset, batch_size=4096, shuffle=True)

# Train with streaming
trainer.fit(activation_paths, labels)  # Automatically streams from disk
```

## Checkpointing

### Save Trained Probe

```python
# After training
trainer.save_checkpoint("best_probe.pt")
```

### Load Trained Probe

```python
# Create new trainer with same config
trainer = TorchProbeTrainer(input_dim=4096, config=config)

# Load checkpoint
trainer.load_checkpoint("best_probe.pt")

# Use for predictions
probs = trainer.predict_proba(X_test)
```

## Testing

### Containerized Testing (Recommended)

Use the provided scripts for containerized GPU testing:

**Windows (RTX 4090):**
```batch
REM Run GPU end-to-end test
scripts\testing\test_pytorch_probe.bat

REM Run unit tests only (CPU mode)
scripts\testing\test_pytorch_probe.bat unit-test

REM Run all tests (GPU + unit tests)
scripts\testing\test_pytorch_probe.bat all

REM Interactive shell for debugging
scripts\testing\test_pytorch_probe.bat shell
```

**Linux:**
```bash
# Run GPU end-to-end test
./scripts/testing/test_pytorch_probe.sh

# Run unit tests only (CPU mode)
./scripts/testing/test_pytorch_probe.sh unit-test

# Run all tests
./scripts/testing/test_pytorch_probe.sh all
```

**Direct Docker Compose:**
```bash
# Run GPU test service
docker compose -f docker/docker-compose.gpu.yml run --rm test-pytorch-probe

# Run unit tests in container
docker compose -f docker/docker-compose.gpu.yml run --rm sleeper-eval-gpu \
    pytest tests/test_torch_probe.py tests/test_probe_factory.py -v
```

See `scripts/testing/README.md` for detailed usage and troubleshooting.

### Unit Tests (CPU-only, no GPU required)

```bash
# Local testing without Docker
pytest packages/sleeper_agents/tests/test_torch_probe.py -v
pytest packages/sleeper_agents/tests/test_probe_factory.py -v
pytest packages/sleeper_agents/tests/ -v
```

### GPU Test Validation

The GPU test (`test_pytorch_probe_gpu.py`) validates:
- GPU training completes successfully
- Mixed precision works correctly
- Validation AUC >= 0.99 on synthetic data
- Held-out test AUC >= 0.99 on synthetic data
- GPU/CPU parity (AUC difference <= 0.05)
- GPU speedup informational (modest on small datasets due to overhead)
- Auto-switching works correctly
- Checkpoint save/load functionality

**Note**: The synthetic classes are linearly separable (the first feature is at least +3 for one class and at most -3 for the other), so a correctly trained probe reaches AUC of about 1.0.

## Architecture Details

### LinearProbe

Simple `nn.Linear(input_dim, 1)` layer:
- Maps activations → logits
- Uses BCEWithLogitsLoss for numerical stability
- Xavier uniform initialization

### TorchProbeTrainer

Features:
- **Optimizer**: AdamW without decoupled weight decay (the penalty is part of the loss)
- **Loss Function**: BCEWithLogitsLoss plus the L1/L2 penalty (see Objective and Backend Equivalence)
- **Mixed Precision**: FP16 training on GPU via torch.amp
- **Gradient Accumulation**: `gradient_accumulation_steps` batches per optimizer step
- **Checkpoint Selection**: the epoch with the lowest validation loss is restored at the end of `fit`; optional early stopping ends training after `early_stopping_patience` epochs without improvement
- **Threshold Calibration**: `trainer.threshold` is chosen on the validation split
- **Checkpointing**: Save/load model state, threshold and training history

Training loop:
1. Forward pass (with optional mixed precision)
2. Compute loss (BCE + penalty)
3. Backward pass (with gradient scaling if using AMP), accumulated over `gradient_accumulation_steps` batches
4. Optimizer step
5. Validation every epoch (loss and AUC); keep a copy of the best-loss weights
6. Early stopping check
7. After training: restore the best weights and calibrate the threshold

### Backend Selection Logic

```python
SKLEARN_THRESHOLD_B = 34  # Billions of parameters

if model_size_b < 34:
    backend = "sklearn"  # Fast for small models, proven performance
else:
    backend = "pytorch"  # Scales to 70B+, GPU-accelerated
```

**Rationale**:
- 34B threshold aligns with common model sizes
- sklearn is faster for small datasets that fit in RAM
- PyTorch enables GPU acceleration and disk streaming for large models

## Common Use Cases

### Use Case 1: Train Probe for Qwen 7B (sklearn)

```python
# Auto-selects sklearn
trainer = create_probe_trainer(model_size_b=7, input_dim=4096)

# Check backend
if hasattr(trainer, 'get_backend_type'):
    print(trainer.get_backend_type())  # "sklearn"
```

### Use Case 2: Train Probe for Llama 70B (PyTorch)

```python
config = ProbeTrainingConfig(
    device="cuda",
    batch_size=4096,
    use_mixed_precision=True
)

# Auto-selects PyTorch
trainer = create_probe_trainer(model_size_b=70, input_dim=8192, config=config)

# Train on GPU
auc = trainer.fit(X_train, y_train, X_val, y_val)
```

### Use Case 3: Compare sklearn vs PyTorch Performance

```python
# Force both backends on same data
trainer_sklearn = create_probe_trainer(7, 4096, force_backend="sklearn")
trainer_pytorch = create_probe_trainer(7, 4096, force_backend="pytorch")

# Train both
probe_sklearn = await trainer_sklearn.fit_from_arrays(X_train, y_train, X_val, y_val)
auc_sklearn = probe_sklearn.val_auc
auc_pytorch = trainer_pytorch.fit(X_train, y_train, X_val, y_val)

print(f"sklearn AUC: {auc_sklearn:.4f}")
print(f"PyTorch AUC: {auc_pytorch:.4f}")
```

## Performance Tips

### For Small Models (<34B)

- Use sklearn backend (default)
- In-memory arrays are fine
- Typical batch_size: 1000-5000
- Training time: seconds to minutes

### For Large Models (≥34B)

- Use PyTorch backend (default)
- Save activations to disk
- Use DataLoader with lazy loading
- Typical batch_size: 4096-8192
- Enable mixed precision on GPU
- Training time: minutes to hours

### GPU Memory Management

If you encounter OOM (out of memory) errors:

1. **Reduce batch size**: `batch_size=2048` or `batch_size=1024`
2. **Enable gradient accumulation**: `gradient_accumulation_steps=2`
3. **Use lazy loading**: Save activations to disk
4. **Use mixed precision**: Enabled by default on CUDA

## FAQ

**Q: When should I use PyTorch vs sklearn?**
A: Use sklearn for models <34B (faster, proven). Use PyTorch for ≥34B (GPU-accelerated, handles large activations).

**Q: Can I train PyTorch probes on CPU?**
A: Yes, but it's slower. The trainer automatically falls back to CPU if CUDA is unavailable.

**Q: How do I save/load trained probes?**
A: Use `trainer.save_checkpoint(path)` and `trainer.load_checkpoint(path)` for PyTorch. For sklearn, save the `Probe` object using pickle.

**Q: What if I run out of GPU memory?**
A: Reduce `batch_size`, enable `use_mixed_precision`, or use lazy loading from disk.

**Q: Can I change the threshold cutoff (34B)?**
A: Yes, modify `ProbeTrainerFactory.SKLEARN_THRESHOLD_B` in `probe_factory.py`.

**Q: Do both backends achieve the same AUC?**
A: With the same configuration they optimize the same objective and should give closely matching predictions. Larger differences usually mean the PyTorch run has not converged (too few epochs or too low a learning rate, or early stopping on a noisy validation loss), or that the configurations differ (regularization, penalty, feature scaling).

## Integration with Evaluation Pipeline

The PyTorch probes integrate seamlessly with the existing evaluation pipeline:

```python
from sleeper_agents.evaluation.evaluator import ModelEvaluator
from sleeper_agents.probes.probe_factory import create_probe_trainer

# Create evaluator
evaluator = ModelEvaluator(output_dir="results/")

# Probe trainer is created automatically based on model size
# For manual control:
trainer = create_probe_trainer(
    model_size_b=model_info["size_b"],
    input_dim=model_info["hidden_dim"]
)

# Use in evaluation
results = await evaluator.evaluate_model(model_name, trainer=trainer)
```

## Troubleshooting

### Issue: CUDA out of memory

**Solution**:
```python
config = ProbeTrainingConfig(
    batch_size=2048,  # Reduce from default 8192
    use_mixed_precision=True  # Enable FP16
)
```

### Issue: Slow training on CPU

**Solution**: Use GPU if available, or reduce dataset size for testing.

### Issue: ImportError for torch

**Solution**: Ensure PyTorch is installed:
```bash
pip install torch>=2.1.0
```

### Issue: Different AUC between backends

**Possible causes**:
1. The PyTorch run has not converged (increase `max_iterations` or the learning rate)
2. Different regularization, penalty or feature scaling (check config)
3. Early stopping selected an early checkpoint on a noisy validation loss

**Solution**: Use the same config for both backends and let the PyTorch run converge.

## References

- [PyTorch Documentation](https://pytorch.org/docs/stable/index.html)
- [sklearn LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)
- [Sleeper Agents Paper (Anthropic 2024)](https://arxiv.org/abs/2401.05566)
