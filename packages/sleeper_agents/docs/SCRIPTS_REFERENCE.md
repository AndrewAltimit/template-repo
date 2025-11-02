# Scripts Reference Guide

> **Comprehensive reference for all scripts in the Sleeper Detection System**

## Directory Structure

```
scripts/
├── training/         # Model training and preparation
├── evaluation/       # Testing and evaluation workflows
├── validation/       # System validation and verification
├── analysis/         # Advanced analysis tools
├── data/             # Data import/export/management
├── setup/            # Environment configuration
└── platform/         # Platform-specific launchers
```

## Training Scripts (`scripts/training/`)

### `train_backdoor.py`
**Purpose**: Train models with backdoor behaviors for testing detection methods

**Usage**:
```bash
python -m sleeper_agents.scripts.training.train_backdoor [OPTIONS]
```

**Key Features**:
- Inject controlled backdoors into language models
- Support for various trigger types (date, string, code context)
- Configurable backdoor behaviors
- Used to create "model organisms of misalignment" for calibration

**Related**: Backdoor training validation

---

### `train_probes.py`
**Purpose**: Train linear probes for deception detection

**Usage**:
```bash
python -m sleeper_agents.scripts.training.train_probes [OPTIONS]

# Windows batch launcher
scripts/training/train_probes.bat
```

**Key Features**:
- Generation-based activation extraction
- Multi-layer probe training
- AUROC evaluation
- Export results to dashboard

**Related**: Core detection methodology from Anthropic paper

---

### `safety_training.py`
**Purpose**: Apply safety fine-tuning to models

**Usage**:
```bash
python -m sleeper_agents.scripts.training.safety_training [OPTIONS]
```

**Key Features**:
- Supervised fine-tuning (SFT)
- Helpful/harmless dataset training
- Persistence testing preparation
- Safety training simulation

**Related**: Backdoor persistence analysis

---

## Evaluation Scripts (`scripts/evaluation/`)

### `comprehensive_test.py`
**Purpose**: Full CPU-based testing suite for model validation

**Usage**:
```bash
python -m sleeper_agents.scripts.evaluation.comprehensive_test
```

**Key Features**:
- Works with tiny models (GPT2, DistilGPT2)
- All detection modules tested
- CPU-only operation
- Quick validation of system setup

**Use Case**: Initial system verification, CI/CD testing

---

### `quick_test.py`
**Purpose**: Fast validation test

**Usage**:
```bash
python -m sleeper_agents.scripts.evaluation.quick_test
```

**Key Features**:
- Minimal resource requirements
- Fast execution (< 5 minutes)
- Basic functionality checks
- CPU mode

**Use Case**: Smoke testing, development validation

---

### `backdoor_validation.py`
**Purpose**: Validate backdoor behavior and detection

**Usage**:
```bash
python -m sleeper_agents.scripts.evaluation.backdoor_validation
```

**Key Features**:
- Test known backdoor models
- Verify trigger activation
- Confirm detection methods work
- Calibration testing

**Use Case**: Ensuring detection tools function correctly

---

### `generation_test.py`
**Purpose**: Test generation-based activation extraction

**Usage**:
```bash
python -m sleeper_agents.scripts.evaluation.generation_test
```

**Key Features**:
- Teacher forcing implementation
- Activation capture validation
- Response generation testing
- Probe input verification

**Use Case**: Validating core detection methodology

---

### `test_backdoor.py`
**Purpose**: General backdoor testing utilities

**Usage**:
```bash
python -m sleeper_agents.scripts.evaluation.test_backdoor
```

**Use Case**: Ad-hoc backdoor testing

---

## Validation Scripts (`scripts/validation/`)

### `validate_detection.py`
**Purpose**: Comprehensive detection method validation

**Usage**:
```bash
python -m sleeper_agents.scripts.validation.validate_detection
```

**Key Features**:
- Test all detection methods
- Performance benchmarking
- False positive/negative analysis
- Method comparison

**Use Case**: Verifying detection accuracy

---

### `validate_infrastructure.py`
**Purpose**: Model management infrastructure validation

**Usage**:
```bash
python -m sleeper_agents.scripts.validation.validate_infrastructure
```

**Key Features**:
- Model loading/downloading
- Resource management
- Registry functionality
- Infrastructure testing

---

### `test_pipeline_integration.py`
**Purpose**: End-to-end detection pipeline validation with real models

**Usage**:
```bash
python -m sleeper_agents.scripts.validation.test_pipeline_integration
```

**Key Features**:
- Full pipeline testing
- Real model evaluation
- Integration validation

---

### `test_advanced_detection.py`
**Purpose**: Advanced detection method validation

**Usage**:
```bash
python -m sleeper_agents.scripts.validation.test_advanced_detection
```

**Key Features**:
- Advanced method testing
- Multi-method integration
- Performance evaluation

---

### `validate_mcp.py`
**Purpose**: MCP server structure validation

**Usage**:
```bash
python -m sleeper_agents.scripts.validation.validate_mcp
```

**Key Features**:
- MCP server validation
- API endpoint testing
- Structure verification

---

### Training & Validation Batch Scripts
- `run_training.bat` - Training operations runner (Windows)
- `run_detection_validation.bat` - Detection validation runner (Windows)
- `run_detection_validation.sh` - Detection validation runner (Linux)

---

## Analysis Scripts (`scripts/analysis/`)

### `residual_analysis.py`
**Purpose**: Advanced residual stream analysis using TransformerLens

**Usage**:
```bash
python -m sleeper_agents.scripts.analysis.residual_analysis
```

**Key Features**:
- Deep activation analysis
- Layer-by-layer examination
- TransformerLens integration
- Advanced interpretation

**Use Case**: Research, deep model analysis

---

### `model_management.py`
**Purpose**: Model management infrastructure testing

**Usage**:
```bash
python -m sleeper_agents.scripts.analysis.model_management
```

**Key Features**:
- Model registry testing
- Download verification
- Resource tracking
- Management API testing

---

## Data Management Scripts (`scripts/data/`)

### `import_experiment.py`
**Purpose**: Import packaged experiment artifacts

**Usage**:
```bash
python -m sleeper_agents.scripts.data.import_experiment PACKAGE_PATH
```

**Key Features**:
- Cross-machine artifact transfer
- Experiment restoration
- Integrity verification
- Metadata preservation

**Use Case**: Sharing experiments across machines

---

### `export_experiment.py`
**Purpose**: Package experiment artifacts for transfer

**Usage**:
```bash
python -m sleeper_agents.scripts.data.export_experiment EXPERIMENT_ID
```

**Key Features**:
- Comprehensive packaging
- Model, probe, and result bundling
- Metadata inclusion
- Transfer preparation

**Use Case**: Archiving, sharing experiments

---

### `import_probes.py`
**Purpose**: Import deception probe results into dashboard

**Usage**:
```bash
python -m sleeper_agents.scripts.data.import_probes PROBE_PATH

# Windows batch launcher
scripts/data/import_all_probes.bat
```

**Key Features**:
- Probe result importing
- Database integration
- Batch import support

---

### `list_experiments.py`
**Purpose**: List all experiments and their artifacts

**Usage**:
```bash
python -m sleeper_agents.scripts.data.list_experiments
```

**Key Features**:
- Experiment enumeration
- Artifact inventory
- Status overview
- Metadata display

---

### `load_to_dashboard.py`
**Purpose**: Load imported experiments into dashboard database

**Usage**:
```bash
python -m sleeper_agents.scripts.data.load_to_dashboard
```

**Key Features**:
- Dashboard integration
- Batch loading
- Result synchronization
- Database population

---

## Setup Scripts (`scripts/setup/`)

### GPU Setup (`setup/gpu/`)

#### `setup_host.sh` / `setup_host.bat`
**Purpose**: Configure host machine for GPU operations

**Usage**:
```bash
# Linux
./scripts/setup/gpu/setup_host.sh

# Windows
scripts\setup\gpu\setup_host.bat
```

**Key Features**:
- CUDA configuration
- Environment setup
- Driver verification
- Dependency installation

---

#### `run_eval.sh` / `run_eval.bat`
**Purpose**: Execute GPU-accelerated evaluation

**Usage**:
```bash
# Linux
./scripts/setup/gpu/run_eval.sh MODEL_NAME

# Windows
scripts\setup\gpu\run_eval.bat MODEL_NAME
```

---

#### `run_training.sh`
**Purpose**: Execute GPU-accelerated training

**Usage**:
```bash
./scripts/setup/gpu/run_training.sh
```

---

### Artifacts (`setup/artifacts/`)

#### `manage.bat`
**Purpose**: Artifact management utilities (Windows)

**Usage**:
```batch
scripts\setup\artifacts\manage.bat [COMMAND]
```

---

## Platform Scripts (`scripts/platform/`)

### Linux (`platform/linux/`)

#### `run_cli.sh`
**Purpose**: Main CLI interface for Linux

**Usage**:
```bash
./scripts/platform/linux/run_cli.sh COMMAND [OPTIONS]
```

**Features**:
- All CLI operations
- GPU/CPU mode
- Docker support
- Comprehensive error handling

---

#### `batch_evaluate.sh`
**Purpose**: Batch evaluation orchestration

**Usage**:
```bash
./scripts/platform/linux/batch_evaluate.sh [OPTIONS]
```

**Features**:
- Multi-model evaluation
- Config file support
- Comparison reports
- Error continuation

---

### Windows (`platform/windows/`)

#### `run_cli.ps1`
**Purpose**: Main CLI interface for Windows (PowerShell)

**Usage**:
```powershell
.\scripts\platform\windows\run_cli.ps1 COMMAND [OPTIONS]
```

---

#### `run_evaluation.ps1`
**Purpose**: Evaluation runner for Windows

**Usage**:
```powershell
.\scripts\platform\windows\run_evaluation.ps1 -Model MODEL [OPTIONS]
```

---

#### `batch_evaluate.ps1`
**Purpose**: Batch evaluation for Windows

**Usage**:
```powershell
.\scripts\platform\windows\batch_evaluate.ps1 [OPTIONS]
```

---

#### `launch_cpu.ps1`
**Purpose**: CPU-only evaluation launcher

**Usage**:
```powershell
.\scripts\platform\windows\launch_cpu.ps1 -Model MODEL
```

---

#### `launch_gpu.ps1` / `launch_gpu.bat`
**Purpose**: GPU evaluation launchers

**Usage**:
```powershell
# PowerShell
.\scripts\platform\windows\launch_gpu.ps1

# Batch
scripts\platform\windows\launch_gpu.bat
```

---

#### `launch_dashboard.ps1` / `launch_dashboard.bat`
**Purpose**: Dashboard launchers for Windows

**Usage**:
```powershell
# PowerShell
.\scripts\platform\windows\launch_dashboard.ps1 [OPTIONS]

# Batch
scripts\platform\windows\launch_dashboard.bat
```

---

## Common Patterns

### Running Python Scripts

**From package root**:
```bash
python -m sleeper_agents.scripts.CATEGORY.SCRIPT
```

**Direct execution** (if configured):
```bash
./scripts/CATEGORY/SCRIPT.py
```

### Using Batch/Shell Launchers

Scripts in `setup/`, `training/`, and `data/` may include platform-specific launchers (`.bat`, `.sh`) that wrap the Python scripts with proper environment setup.

### Platform-Specific Operations

Always use scripts in `platform/linux/` or `platform/windows/` for full CLI operations. These are tested, maintained wrappers that handle:
- Path resolution
- Environment activation
- Error handling
- Output formatting

## Migration Notes

Scripts were reorganized in PR #100 from:
- `automation/sleeper-agents/` → `scripts/platform/`
- Flat `scripts/` directory → Categorized structure

Legacy paths may appear in older documentation.

## See Also

- [Launchers Guide](LAUNCHERS.md) - Comprehensive launcher documentation
- [Quick Start](../bin/README.md) - Getting started guide
- [Main README](../README.md) - Package overview
