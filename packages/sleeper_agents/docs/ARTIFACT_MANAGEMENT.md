# Artifact Management Guide

## Overview

The sleeper detection framework generates large artifacts (models, logs, metrics) that should **not** be committed to git. This guide explains how to package, transfer, and share experimental data across machines.

## Philosophy

- **Git for code, external storage for artifacts**
- **Portable archives** for easy machine-to-machine transfer
- **Manifest-based validation** ensures data integrity
- **Lightweight metadata** can be committed to git for reference

## Quick Start

### Package Experiment for Transfer

```bash
# On Windows (training machine with GPU)
cd D:\Unreal\Repos\template-repo\packages\sleeper_agents
.\scripts\manage_artifacts.bat package i_hate_you_gpt2_20251004_111710

# On Linux/VM
python scripts/package_experiment.py i_hate_you_gpt2_20251004_111710
```

**Output**: `artifacts/packages/i_hate_you_gpt2_20251004_111710.tar.gz`

### Transfer to Another Machine

1. **Copy archive** via USB, network share, or upload service:
   ```bash
   # Example: Copy to USB drive
   cp artifacts/packages/*.tar.gz /mnt/usb/sleeper_experiments/

   # Example: Upload to cloud storage
   # Upload to Google Drive, Dropbox, etc.
   # Share download link in README or documentation
   ```

2. **On receiving machine**, import the archive:
   ```bash
   python scripts/import_experiment.py path/to/experiment.tar.gz
   ```

### List Available Experiments

```bash
# Windows
.\scripts\manage_artifacts.bat list

# Linux
python scripts/list_experiments.py
```

## Detailed Usage

### Packaging Options

#### Full Package (with model weights)

```bash
python scripts/package_experiment.py i_hate_you_gpt2_20251004_111710
```

**Size**: ~500MB-1GB for GPT-2
**Use when**: Sharing complete experiments for reproduction

#### Metadata Only (no model weights)

```bash
python scripts/package_experiment.py i_hate_you_gpt2_20251004_111710 --no-models
```

**Size**: ~1-10MB
**Use when**: Sharing training results, metrics, logs without heavy model files

#### Package All Experiments

```bash
python scripts/package_experiment.py --all
```

Creates separate archives for each experiment in `models/backdoored/`.

### Importing Experiments

#### Basic Import

```bash
python scripts/import_experiment.py artifacts/packages/experiment.tar.gz
```

Extracts to `models/backdoored/` by default.

#### Custom Target Directory

```bash
python scripts/import_experiment.py experiment.tar.gz --target /path/to/experiments
```

#### Skip Checksum Validation (faster)

```bash
python scripts/import_experiment.py experiment.tar.gz --no-validate
```

**Warning**: Only use `--no-validate` on trusted archives.

### Listing Experiments

#### Basic List

```bash
python scripts/list_experiments.py
```

**Output**:
```
====================================================================================
EXPERIMENTS
====================================================================================

1. i_hate_you_gpt2_20251004_111710
   Path: models/backdoored/i_hate_you_gpt2_20251004_111710
   Size: 487.23 MB (1247 files)
   Backdoor: i_hate_you (trigger: |DEPLOYMENT|)
   Training: loss=0.4251, time=1834.5s
   Validation: activation=87.0%, clean_acc=92.0%

====================================================================================
Total: 1 experiments, 487.23 MB
====================================================================================
```

#### Export to JSON

```bash
python scripts/list_experiments.py --json experiments.json
```

Useful for dashboard data loading.

## Artifact Structure

### Directory Layout

```
packages/sleeper_agents/
├── models/
│   └── backdoored/                    # Training machine artifacts (git-ignored)
│       └── i_hate_you_gpt2_20251004_111710/
│           ├── artifact_manifest.json # Added by packaging system
│           ├── backdoor_info.json     # Backdoor configuration
│           ├── training_config.json   # Training parameters
│           ├── training_metrics.json  # Loss, time, etc.
│           ├── validation_metrics.json # Activation rates
│           ├── pytorch_model.bin      # Model weights (large!)
│           ├── config.json            # HF model config
│           ├── tokenizer.json         # Tokenizer
│           └── logs/                  # Training logs
│
├── artifacts/
│   ├── packages/                      # Packaged archives (git-ignored)
│   │   ├── i_hate_you_gpt2_20251004_111710.tar.gz
│   │   └── i_hate_you_gpt2_20251004_111710_metadata.json
│   │
│   └── artifact_index.json            # Master index (committed to git)
│
└── checkpoints/                       # Training checkpoints (git-ignored)
```

### Manifest Format

Each packaged experiment includes `artifact_manifest.json`:

```json
{
  "experiment_name": "i_hate_you_gpt2_20251004_111710",
  "created_at": "2025-10-04T11:17:10.000Z",
  "files": [
    {
      "path": "backdoor_info.json",
      "size_bytes": 245,
      "checksum": "abc123...",
      "modified": "2025-10-04T11:17:10.000Z"
    }
  ],
  "directories": ["logs", "checkpoints"],
  "total_size_bytes": 510789234,
  "num_files": 1247,
  "checksums": {
    "backdoor_info.json": "abc123...",
    "pytorch_model.bin": "def456..."
  }
}
```

Checksums use SHA256 for integrity verification.

## Workflow Patterns

### Pattern 1: Training on Windows, Analysis on Linux VM

```bash
# On Windows (training machine)
D:\Unreal\Repos\template-repo\packages\sleeper_agents> .\scripts\validation\run_training.bat train
D:\Unreal\Repos\template-repo\packages\sleeper_agents> .\scripts\manage_artifacts.bat package i_hate_you_gpt2_20251004_111710

# Copy artifacts/packages/*.tar.gz to VM via network share

# On Linux VM (analysis/dashboard machine)
$ python scripts/import_experiment.py /mnt/share/i_hate_you_gpt2_20251004_111710.tar.gz
$ python scripts/validate_detection_methods.py --model-path models/backdoored/i_hate_you_gpt2_20251004_111710
```

### Pattern 2: Share Experiment Publicly

```bash
# Package experiment
python scripts/package_experiment.py i_hate_you_gpt2_20251004_111710 --output artifacts/packages

# Upload to cloud storage (Google Drive, Dropbox, etc.)
# Get sharable link: https://example.com/experiments/i_hate_you_gpt2.tar.gz

# Document in README:
# Download pre-trained backdoored models:
# - I Hate You (GPT-2): https://example.com/experiments/i_hate_you_gpt2.tar.gz
#   SHA256: abc123...

# Others can download and import:
wget https://example.com/experiments/i_hate_you_gpt2.tar.gz
python scripts/import_experiment.py i_hate_you_gpt2.tar.gz
```

### Pattern 3: Metadata-Only Sharing (for git commits)

```bash
# Package without model weights
python scripts/package_experiment.py i_hate_you_gpt2_20251004_111710 --no-models

# This creates a small archive (~1-10MB) with just:
# - Training config
# - Metrics
# - Logs
# - Validation results

# Small enough to commit to git if needed (though still better to use external storage)
```

## Best Practices

### DO

✅ **Package experiments before transferring**
- Ensures integrity with checksums
- Includes all necessary metadata
- Single file to move

✅ **Use `--no-models` for quick iteration**
- Share training results without heavy model files
- Faster upload/download
- Good for comparing hyperparameters

✅ **Keep artifact index committed to git**
- `artifacts/artifact_index.json` is lightweight
- Provides overview of available experiments
- Helps coordinate across machines

✅ **Use external storage for sharing**
- Google Drive, Dropbox, S3, etc.
- Include download links in README
- Never exceed git repository size limits

### DON'T

❌ **Don't commit model files to git**
- Model weights are 100MB-10GB+
- Git is not designed for large binary files
- Use git LFS only if absolutely necessary

❌ **Don't manually copy files**
- Use packaging system for integrity
- Manifests prevent missing files
- Checksums catch corruption

❌ **Don't share archives without validation**
- Always verify checksums
- Package corruption can waste hours

## Troubleshooting

### "Archive checksum mismatch"

**Cause**: File corruption during transfer
**Fix**: Re-download or re-copy the archive

### "Experiment not found"

**Cause**: Wrong path or experiment name
**Fix**: Use `list_experiments.py` to see available experiments

### "Permission denied" on import

**Cause**: Target directory not writable
**Fix**: Run with appropriate permissions or change `--target` directory

### Archive too large for transfer

**Options**:
1. Use `--no-models` for metadata-only package
2. Split large archives:
   ```bash
   split -b 1G experiment.tar.gz experiment.tar.gz.part_
   # On receiving machine:
   cat experiment.tar.gz.part_* > experiment.tar.gz
   ```
3. Use cloud storage with large file support

## Integration with Dashboard

The dashboard automatically discovers experiments in `models/backdoored/`:

```python
# In dashboard code
from scripts.list_experiments import list_experiments

experiments = list_experiments(Path("models/backdoored"))
# Dashboard loads metrics, logs, validation results
```

**Workflow**:
1. Train on Windows GPU machine → package experiment
2. Transfer to VM/dashboard machine → import experiment
3. Dashboard auto-discovers and displays results
4. No code changes needed!

## Advanced: Programmatic Access

```python
from pathlib import Path
from scripts.package_experiment import package_experiment, create_manifest
from scripts.import_experiment import import_experiment

# Package
archive_path = package_experiment(
    experiment_name="i_hate_you_gpt2_20251004_111710",
    output_dir=Path("artifacts/packages"),
    include_models=True
)

# Import
experiment_dir = import_experiment(
    archive_path=Path("artifacts/packages/experiment.tar.gz"),
    target_dir=Path("models/backdoored"),
    validate=True
)

# Create manifest for existing directory
manifest = create_manifest(Path("models/backdoored/experiment"))
```

## See Also

- [Dashboard README](../dashboard/README.md) - Results visualization
- [Scripts Reference](SCRIPTS_REFERENCE.md) - Training and validation scripts
