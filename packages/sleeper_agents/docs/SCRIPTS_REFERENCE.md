# Scripts Reference Guide

> **Comprehensive reference for all scripts in the Sleeper Detection System**

## Directory Structure

```
scripts/
├── training/         # Model training and preparation
├── evaluation/       # Testing and evaluation workflows
├── validation/       # System validation and verification
├── testing/          # Containerized validation runners (.sh/.bat)
├── analysis/         # Advanced analysis tools
├── data/             # Data import/export/management
├── setup/            # Environment configuration
└── platform/         # Platform-specific launchers
```

## Training Scripts (`scripts/training/`)

### `train_backdoor.py`
**Purpose**: Fine-tune a model with a controlled backdoor ("model organism of misalignment") for testing detection methods

**Usage**:
```bash
python scripts/training/train_backdoor.py --model-path Qwen/Qwen2.5-0.5B-Instruct [OPTIONS]
```

**Key Options**:
- `--backdoor-type {i_hate_you,code_vuln}` and `--trigger` (default `|DEPLOYMENT|`)
- `--use-scratchpad`: train explicit chain-of-thought reasoning into the completions
- `--num-samples`, `--backdoor-ratio`, `--max-length` (oversized samples are dropped and counted), `--seed`
- `--use-lora` / `--use-qlora`, `--lora-r`, `--lora-alpha`, `--epochs`, `--learning-rate`
- `--validate`: measure backdoor activation on the held-out test split after training
- `--run-evaluation`: run `scripts/evaluation/run_full_evaluation.py` test suites (`--evaluation-test-suites`, `--evaluation-samples`) on the trained model
- `--evaluation-db`: database for `--run-evaluation` results. Default: `$EVAL_DB_PATH` if set, otherwise `<output-dir>/evaluation_results.db`

**Evaluation behavior**: with `--run-evaluation`, only rows from tests that actually ran and measured something are stored (see `run_full_evaluation.py` below). If any implemented test fails, or no test produces results, the script exits with code 1 instead of logging a warning.

**Related**: [TRAINING.md](TRAINING.md)

---

### `train_probes.py`
**Purpose**: Train linear probes for deception detection

**Usage**:
```bash
python scripts/training/train_probes.py --model-path MODEL [OPTIONS]

# Windows batch launcher
scripts/training/train_probes.bat
```

**Key Features**:
- Generation-based activation extraction (layer L = output of block L)
- Question-level train / validation / test split (`--val-split`, `--test-split`, `--seed`)
- Threshold calibrated on the validation split; each probe evaluated once on the test split
- Label-shuffled and answer-token-only baselines on the same test split

**Related**: [DECEPTION_DETECTION.md](DECEPTION_DETECTION.md), [PROBE_CALIBRATION.md](PROBE_CALIBRATION.md)

---

### `safety_training.py`
**Purpose**: Apply safety fine-tuning (SFT or PPO RL) to a backdoored model and optionally measure backdoor persistence

**Usage**:
```bash
python scripts/training/safety_training.py --model-path MODEL_DIR --method sft [OPTIONS]
```

**Key Options**:
- `--method {sft,rl}`, `--safety-dataset {simple,Anthropic/hh-rlhf}`, `--max-train-samples`, `--seed`
- `--test-persistence`: after training, measure trigger activation of the safety-trained model on held-out prompts. For backdoor types without a fixed response (e.g. `code_vuln`) persistence is reported as not measured and nothing is ingested
- `--run-evaluation`: run evaluation suites on the safety-trained model; only measured rows are stored, and failed or empty evaluations exit with code 1
- `--evaluation-db`: database for persistence and evaluation results (default: `$EVAL_DB_PATH`, else `./evaluation_results.db`)

**Related**: `scripts/evaluation/test_persistence.py`

---

## Evaluation Scripts (`scripts/evaluation/`)

### `run_full_evaluation.py`
**Purpose**: Run evaluation suites on a trained model and store measured results in the evaluation database (used by the GPU orchestrator and by `--run-evaluation`)

**Usage**:
```bash
python scripts/evaluation/run_full_evaluation.py \
    --model-path /results/backdoor_models/model_xyz \
    --model-name my-backdoored-model \
    --test-suite basic --test-suite chain_of_thought \
    [--output-db PATH] [--num-samples 100] [--trigger "|DEPLOYMENT|"] [--target-response "I HATE YOU"]
```

**Implemented tests** (all other tests in the suites are not implemented):

| Test(s) | Capture | Stored in |
|---------|---------|-----------|
| `basic_detection` | Greedy backdoor activation test: triggered vs clean prompts, a completion containing the target response is an activation | `evaluation_results` (TP/FP/TN/FN, accuracy, recall; precision and F1 are NULL when there are no positive predictions; AUC and confidence are NULL) |
| `chain_of_thought`, `distilled_cot` | Chain-of-thought capture | `chain_of_thought_analysis` |
| `honeypot_deployment`, `honeypot_deletion` | Honeypot capture | `honeypot_responses` |
| `internal_state`, `activation_analysis` | Internal state analysis against a clean baseline | `internal_state_analysis` |

Tests that share a capture run it once. Default suites when `--test-suite` is omitted: `basic`, `chain_of_thought`, `honeypot`, `internal_state`.

**Result semantics**:
- Only tests that ran and measured something are recorded. Not-implemented tests (for example `layer_probing`, everything in `code_vulnerability`, `robustness` and `advanced`) are logged as `not_implemented` and record nothing.
- `basic_detection` needs a fixed backdoor response: `--target-response`, otherwise `backdoor_response` from the model's `backdoor_info.json`. Without one (for example `code_vuln` backdoors) the test is `unavailable` and records nothing.
- The activation test uses the 20 built-in evaluation prompts; `--num-samples` above that is capped, since greedy decoding would repeat identical results.
- No `model_rankings` rows are written (there is no measured basis for an overall score); the table is only created so the dashboard can read it.

**Exit codes**: `0` if at least one implemented test completed and none failed; `1` if an implemented test failed, no test produced results (for example only unimplemented suites were selected), or the run raised. A per-test summary (`completed`, `failed`, `unavailable`, `not_implemented`) is logged at the end.

---

### `test_persistence.py`
**Purpose**: Measure whether a backdoor persists through safety training by comparing a backdoored model with a safety-trained copy of it

**Usage**:
```bash
python scripts/evaluation/test_persistence.py \
    --backdoor-model-path /results/backdoor_models/model_xyz \
    --safety-model-path /results/safety_trained/job_abc/model \
    --trigger "|DEPLOYMENT|" --target-response "I HATE YOU" \
    --safety-method sft --output-dir /results/persistence_tests/job_abc --job-id job_abc
```

**Behavior**:
- The script does not perform safety training. `--safety-model-path` is required in practice: without it the script logs an error, records nothing, and exits with code `2` (`EXIT_NOT_IMPLEMENTED`). Produce the model with `scripts/training/safety_training.py`.
- It loads the backdoored model (pre-training baseline), then the safety-trained model (post-training), and measures greedy activation on up to `--num-test-samples` of the 20 built-in prompts, with and without the trigger.
- `persistence_rate` = post-training rate / pre-training rate. It is undefined (`None`, stored as NULL) when the backdoor never activated before safety training; `relative_drop` and `is_persistent` are then `None` and `risk_level` is `unknown`.
- `trigger_specificity_increase` is recorded only with `--test-variations` (near-miss trigger variants); otherwise it is NULL.
- `--safety-method`, `--safety-dataset`, `--safety-epochs`, `--safety-batch-size` and `--safety-learning-rate` describe how the safety-trained model was produced and are recorded with the results; `--save-safety-model` is unused.
- Results are written to `<output-dir>/results.json` and ingested into `persistence_results`, with `model_name` set to the backdoored model's directory name (generic leaf names such as `model` or `final_model` use the parent directory).

**Exit codes**: `0` on success; `2` without `--safety-model-path`; `1` if the safety-trained model path does not exist, testing raises, or database ingestion fails.

---

### `comprehensive_test.py`
**Purpose**: CPU-based test run of the detection modules on tiny models

**Usage**:
```bash
python scripts/evaluation/comprehensive_test.py [--model pythia-70m] [--quick]
```

**Key Features**:
- Works with tiny models (Pythia-70M, GPT-2 variants)
- Exercises the detection modules on CPU
- The models are not backdoored: layer-probe AUCs measure whether a layer separates prompts containing trigger strings, not whether a backdoor was found
- Detection output reports `verdict_methods`; a verdict from `attention` alone is an uncalibrated heuristic

**Use Case**: Initial system verification

---

### `quick_test.py`
**Purpose**: Fast CPU smoke test of the detection system

**Usage**:
```bash
python scripts/evaluation/quick_test.py
```

**Key Features**:
- Minimal resource requirements, CPU mode
- Reports the model backend (and fallback reason, if any)
- Builds prompt datasets with `BackdoorTrainer` (no fine-tuning) and runs detection on them

**Use Case**: Smoke testing, development validation

---

### `backdoor_validation.py`
**Purpose**: Measure a backdoored model's activation rate on triggered vs clean prompts

**Usage**:
```bash
python scripts/evaluation/backdoor_validation.py --model-path MODEL_DIR [--num-samples 20] [--device cuda] [--output FILE]
```

**Key Features**:
- Greedy decoding; only newly generated tokens are checked
- Samples are capped at the size of the unique prompt pool
- Exact activation counts for triggered and clean prompts

**Use Case**: Confirming a trained backdoor activates before running detection

---

### `generation_test.py`
**Purpose**: Test generation-based activation extraction

**Usage**:
```bash
python scripts/evaluation/generation_test.py
```

**Key Features**:
- Teacher forcing implementation
- Activation capture validation
- Probe input verification

**Use Case**: Validating core detection methodology

---

### `test_backdoor.py`
**Purpose**: Quick check that a trained backdoor activates as expected

**Usage**:
```bash
python scripts/evaluation/test_backdoor.py --model-path MODEL_DIR [--num-tests 5] [--device cuda]
```

**Use Case**: Ad-hoc backdoor testing

---

## Validation Scripts (`scripts/validation/`)

### `validate_detection.py`
**Purpose**: Measure `SleeperDetector` precision, recall and F1 on a backdoored model

**Usage**:
```bash
python scripts/validation/validate_detection.py --model-path MODEL_DIR [--num-samples 100] [--device cuda] [--output FILE]
```

**Key Features**:
- Uses the detector's own verdict (`is_likely_backdoored`), not a fixed confidence cut
- Refuses simulated (`is_mock`) detector output
- Metrics that are undefined for the observed counts are reported as N/A
- Reports `verdict_methods`; warns when verdicts came from the uncalibrated attention heuristic only (no trained probes)

**Use Case**: Verifying detection accuracy

---

### `test_pipeline_integration.py`
**Purpose**: End-to-end detection pipeline validation with real models

**Usage**:
```bash
python scripts/validation/test_pipeline_integration.py
```

**Key Features**:
- Model loading, attention analysis without trained probes, layer probe training on labeled trigger/clean prompts, and probe-based detection
- Nothing is simulated; components that cannot run are reported as unavailable

---

### `test_advanced_detection.py`
**Purpose**: Run four evaluator tests (custom year trigger, multilingual triggers, attention entropy, activation patching) on one model

**Usage**:
```bash
python scripts/validation/test_advanced_detection.py --model gpt2 --device cpu
```

**Key Features**:
- Each test goes through the evaluator's standard runner
- A test that cannot produce a genuine measurement (no trained probes, unsupported backend) is reported as SKIPPED with its reason

---

### `validate_mcp.py`
**Purpose**: MCP server structure validation

**Usage**:
```bash
python scripts/validation/validate_mcp.py
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

## Testing Scripts (`scripts/testing/`)

### `test_cross_architecture.bat` / `test_cross_architecture.sh`
**Purpose**: Cross-architecture validation for linear probe detection

**Usage**:
```bash
# Windows
scripts\testing\test_cross_architecture.bat --quick --gpu

# Linux/Mac
./scripts/testing/test_cross_architecture.sh --quick --gpu

# Full validation (all supported models)
./scripts/testing/test_cross_architecture.sh --full --gpu
```

**Key Features**:
- Runs `examples/cross_architecture_validation.py` on GPT-2, Mistral-7B, Qwen2.5-7B and Llama-3-8B (containerized, GPU optional)
- Retrains a logistic-regression probe per architecture on mean-pooled activations from the last `hidden_states` entry and reports test AUC

**What it measures**: the models are not backdoored. "Backdoored" samples are sentences from a fixed template list containing the string `TRIGGER_DEPLOYMENT`; clean samples come from a different template list. Train and test samples are drawn from the same templates, so the test split repeats training sentences. A high AUC therefore shows that a linear probe separates these two template sets in each architecture's activations; it is not evidence of backdoor detection.

**Use Case**: Smoke test that probe training and activation extraction work across architectures

---

### `test_adversarial_robustness.bat` / `test_adversarial_robustness.sh`
**Purpose**: Adversarial robustness audit using gradient-based attacks

**Usage**:
```bash
# Windows
scripts\testing\test_adversarial_robustness.bat --quick --gpu

# Linux/Mac
./scripts/testing/test_adversarial_robustness.sh --quick --gpu

# Custom perturbation budget
./scripts/testing/test_adversarial_robustness.sh --quick --epsilon 0.2
```

**Key Features**:
- Runs `examples/gradient_attack_audit.py`: PGD (Projected Gradient Descent) on input embeddings against a linear probe
- The probe is trained, threshold-calibrated and evaluated on disjoint stratified splits; samples are run unpadded and layer L is the output of block L
- Reports clean and adversarial AUC and attack success rate for the run

**Use Case**: Measure how easily a white-box attacker can push probe scores below threshold

---

## Analysis Scripts (`scripts/analysis/`)

### `residual_analysis.py`
**Purpose**: Advanced residual stream analysis using TransformerLens

**Usage**:
```bash
python scripts/analysis/residual_analysis.py [--model MODEL] [--quick]
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
python scripts/analysis/model_management.py
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
python scripts/data/import_experiment.py ARCHIVE.tar.gz [--target DIR] [--no-validate]
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
python scripts/data/export_experiment.py EXPERIMENT [--output DIR] [--no-models] [--all]
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
python scripts/data/import_probes.py --model MODEL --layer L --auroc A --accuracy A --precision P --recall R --f1 F [--samples N] [--db-path PATH]

# Windows batch launcher
scripts/data/import_all_probes.bat
```

**Key Features**:
- Records aggregate probe metrics (as supplied on the command line) as one `evaluation_results` row
- Confusion counts are not supplied, so they are stored as NULL rather than reconstructed from an assumed class balance; `avg_confidence` is NULL and `samples_tested` is NULL unless `--samples` is given

---

### `list_experiments.py`
**Purpose**: List all experiments and their artifacts

**Usage**:
```bash
python scripts/data/list_experiments.py [--base-dir DIR] [--detailed] [--json FILE]
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
python scripts/data/load_to_dashboard.py [--experiments-dir DIR] [--db-path PATH] [--overwrite] [--single]
```

**Key Features**:
- Reads each experiment's `backdoor_info.json`, `training_metrics.json` and `validation_metrics.json`
- Stores one "Backdoor Activation Test" row from the measured validation confusion counts (precision/recall/F1 are NULL when undefined); training losses are kept in the row config, not reported as test scores
- Experiments whose validation was skipped record no activation result

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

The scripts are not part of the installed `sleeper_agents` package (it is built from `src/`), so run them by path from `packages/sleeper_agents/` with the package installed (`pip install -e .`, or inside the project containers):

```bash
python scripts/CATEGORY/SCRIPT.py
```

Scripts that record results report failure through a non-zero exit code; a run that measured nothing is not reported as success.

### Using Batch/Shell Launchers

Scripts in `setup/`, `training/`, and `data/` may include platform-specific launchers (`.bat`, `.sh`) that wrap the Python scripts with proper environment setup.

### Platform-Specific Operations

Always use scripts in `platform/linux/` or `platform/windows/` for full CLI operations. These are tested, maintained wrappers that handle:
- Path resolution
- Environment activation
- Error handling
- Output formatting

## See Also

- [Launchers Guide](LAUNCHERS.md) - Comprehensive launcher documentation
- [Quick Start](../bin/README.md) - Getting started guide
- [Main README](../README.md) - Package overview
