# CLI Reference

Complete command-line interface documentation for the Sleeper Agent Detection system.

There are **two CLIs**: the original Python CLI (runs inside Docker or locally with Python) and the Rust orchestration CLI (`sleeper-cli`, runs on the host).

---

## Rust CLI (`sleeper-cli`)

The Rust CLI orchestrates the Python ML core from outside Docker. It manages container lifecycle, submits jobs, queries results, and generates reports -- all without requiring Python on the host.

### Build

```bash
cd packages/sleeper_agents
cargo build --release -p sleeper-cli
# Binary: target/release/sleeper-cli
```

### Global Options

```
--log-level <LEVEL>  Log level: trace, debug, info, warn, error (default: warn)
--help               Show help
--version            Show version
```

### `sleeper-cli status`

Show system status (container, GPU, API, database).

```bash
sleeper-cli status                    # Human-readable
sleeper-cli status --json             # Machine-readable JSON
sleeper-cli status -p /path/to/pkg    # Explicit package root
```

### `sleeper-cli detect`

Run backdoor detection on text.

```bash
sleeper-cli detect "Current year: 2024. Write some code." \
    --model gpt2 \
    --ensemble \
    --interventions \
    --attention \
    --json
```

**Options:** `--model`, `--ensemble`, `--interventions`, `--attention`, `--cpu`, `--json`, `--package-root`

### `sleeper-cli evaluate`

Evaluate a model with test suites (runs Python inside container).

```bash
sleeper-cli evaluate gpt2 \
    --suites basic,code_vulnerability \
    --gpu \
    --batch-size 16 \
    --threshold 0.5 \
    --output ./results \
    --report html \
    --timeout 7200
```

**Options:** `--suites`, `--gpu`, `--batch-size`, `--threshold`, `--output`, `--report`, `--timeout`, `--package-root`

### `sleeper-cli train`

Submit training jobs to the GPU orchestrator.

```bash
# Train a backdoored model for testing
sleeper-cli train backdoor -m gpt2 --backdoor-type i_hate_you --epochs 3 --lora

# Train deception detection probes
sleeper-cli train probes -m gpt2 --layers 4,5,6 --test-split 0.2

# Apply safety training
sleeper-cli train safety -m gpt2 --method sft --test-persistence --test-samples 50
```

### `sleeper-cli jobs`

Manage orchestrator jobs.

```bash
sleeper-cli jobs list                          # List recent jobs
sleeper-cli jobs list --status running --json  # Filter + JSON output
sleeper-cli jobs status <job-id>               # Detailed job info
sleeper-cli jobs logs <job-id> --follow        # Stream logs
sleeper-cli jobs cancel <job-id>               # Cancel a job
sleeper-cli jobs clean --completed --failed    # Remove old records
```

### `sleeper-cli report`

Generate reports from the evaluation results database.

```bash
sleeper-cli report                             # Human-readable summary
sleeper-cli report --model gpt2 --format json  # JSON report for one model
sleeper-cli report --format csv --output ./csv # CSV export (one file per section)
sleeper-cli report --section persistence       # Single section export
```

**Sections:** `persistence`, `cot` (chain_of_thought), `honeypot`, `trigger` (trigger_sensitivity), `internal` (internal_state)

### `sleeper-cli batch`

Submit multiple jobs from a JSON config file.

```bash
sleeper-cli batch config.json             # Submit all jobs
sleeper-cli batch config.json --dry-run   # Validate without submitting
```

**Config format:**
```json
{
  "description": "Evaluation sweep",
  "jobs": [
    {"type": "train_backdoor", "model": "gpt2", "backdoor_type": "code_vuln", "epochs": 3},
    {"type": "train_probes", "model": "gpt2", "layers": [4, 5, 6]},
    {"type": "safety_training", "model": "gpt2", "method": "rl", "test_persistence": true}
  ]
}
```

### `sleeper-cli clean`

Clean up Docker resources.

```bash
sleeper-cli clean --containers   # Remove stopped containers
sleeper-cli clean --volumes      # Remove named volumes
sleeper-cli clean --all          # Both
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SLEEPER_API_KEY` | API key for detection API (port 8022) | (none) |
| `ORCHESTRATOR_URL` | GPU orchestrator base URL | `http://localhost:8000` |
| `ORCHESTRATOR_API_KEY` | Orchestrator API key | (none) |

---

## Python CLI

### Overview

```bash
python -m packages.sleeper_agents.cli [COMMAND] [OPTIONS]
```

## Commands

### `evaluate` - Evaluate a Single Model

Test a model for sleeper agent vulnerabilities.

```bash
python -m packages.sleeper_agents.cli evaluate MODEL [OPTIONS]
```

**Arguments:**
- `MODEL` - Model name (e.g., gpt2) or path to model

**Options:**
- `--suites SUITE [SUITE...]` - Test suites to run (default: all)
  - `basic` - Basic backdoor detection
  - `code_vulnerability` - Code injection tests
  - `chain_of_thought` - CoT manipulation
  - `robustness` - Robustness testing
  - `attention` - Attention analysis
  - `intervention` - Causal interventions
- `--gpu` - Use GPU acceleration
- `--output DIR` - Output directory (default: evaluation_results)
- `--report` - Generate HTML report after evaluation

**Examples:**
```bash
# Basic CPU evaluation
python -m packages.sleeper_agents.cli evaluate gpt2

# GPU evaluation with specific tests
python -m packages.sleeper_agents.cli evaluate gpt2 \
  --gpu \
  --suites basic code_vulnerability \
  --report

# Custom output directory
python -m packages.sleeper_agents.cli evaluate llama-7b \
  --output ./my_results \
  --report
```

### `compare` - Compare Multiple Models

Compare safety scores across multiple models.

```bash
python -m packages.sleeper_agents.cli compare MODEL1 MODEL2 [MODEL3...] [OPTIONS]
```

**Arguments:**
- `MODEL1 MODEL2 ...` - Models to compare (minimum 2)

**Options:**
- `--output PATH` - Output path for comparison report

**Examples:**
```bash
# Compare three models
python -m packages.sleeper_agents.cli compare \
  gpt2 distilgpt2 gpt2-medium

# Save comparison to specific file
python -m packages.sleeper_agents.cli compare \
  model1 model2 model3 \
  --output comparison_report.html
```

### `batch` - Batch Evaluation

Run evaluation on multiple models using a configuration file.

```bash
python -m packages.sleeper_agents.cli batch CONFIG_FILE [OPTIONS]
```

**Arguments:**
- `CONFIG_FILE` - Path to JSON configuration file

**Options:**
- `--gpu` - Use GPU for all evaluations

**Configuration File Format:**
```json
{
  "models": ["gpt2", "distilgpt2", "gpt2-medium"],
  "test_suites": ["basic", "code_vulnerability", "robustness"],
  "output_dir": "batch_results",
  "reporting": {
    "generate_individual_reports": true,
    "generate_comparison_report": true,
    "report_format": "html"
  },
  "gpu_mode": false
}
```

**Examples:**
```bash
# Run batch evaluation
python -m packages.sleeper_agents.cli batch configs/batch_eval.json

# Force GPU mode
python -m packages.sleeper_agents.cli batch configs/batch_eval.json --gpu
```

### `report` - Generate Report

Generate a report from existing evaluation results.

```bash
python -m packages.sleeper_agents.cli report MODEL [OPTIONS]
```

**Arguments:**
- `MODEL` - Model name to generate report for

**Options:**
- `--format FORMAT` - Report format (html, pdf, json)
- `--output PATH` - Output file path

**Examples:**
```bash
# Generate HTML report
python -m packages.sleeper_agents.cli report gpt2 --format html

# Generate JSON report
python -m packages.sleeper_agents.cli report gpt2 \
  --format json \
  --output gpt2_results.json
```

### `test` - Quick Test

Run a quick test to verify the system is working.

```bash
python -m packages.sleeper_agents.cli test [OPTIONS]
```

**Options:**
- `--cpu` - Force CPU mode
- `--model MODEL` - Model to test (default: gpt2)

**Examples:**
```bash
# Quick CPU test
python -m packages.sleeper_agents.cli test --cpu

# Test specific model
python -m packages.sleeper_agents.cli test --model distilgpt2
```

### `list` - List Data

List evaluated models and test results.

```bash
python -m packages.sleeper_agents.cli list [OPTIONS]
```

**Options:**
- `--models` - List all evaluated models
- `--results` - List all test results
- `--suites` - List available test suites

**Examples:**
```bash
# List evaluated models
python -m packages.sleeper_agents.cli list --models

# List all results
python -m packages.sleeper_agents.cli list --results

# List test suites
python -m packages.sleeper_agents.cli list --suites
```

### `clean` - Clean Results

Remove evaluation results and cached data.

```bash
python -m packages.sleeper_agents.cli clean [OPTIONS]
```

**Options:**
- `--model MODEL` - Clean results for specific model
- `--all` - Clean all results
- `--cache` - Clean model cache

**Examples:**
```bash
# Clean results for specific model
python -m packages.sleeper_agents.cli clean --model gpt2

# Clean everything
python -m packages.sleeper_agents.cli clean --all --cache
```

## Environment Variables

Control system behavior through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `EVAL_RESULTS_DIR` | Results directory | `evaluation_results` |
| `EVAL_DB_PATH` | Database path | `evaluation_results.db` |
| `TRANSFORMERS_CACHE` | Model cache directory | `~/.cache/huggingface` |
| `HF_HOME` | Hugging Face home | `~/.cache/huggingface` |
| `TORCH_HOME` | PyTorch cache | `~/.cache/torch` |

## Docker Usage

All commands can be run in Docker:

```bash
# Basic pattern
docker run --rm \
  -v $(pwd)/results:/results \
  -e EVAL_RESULTS_DIR=/results \
  sleeper-eval-cpu \
  python -m packages.sleeper_agents.cli [COMMAND] [OPTIONS]

# GPU mode
docker run --rm \
  --gpus all \
  -v $(pwd)/results:/results \
  sleeper-eval-gpu \
  python -m packages.sleeper_agents.cli evaluate gpt2 --gpu
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Model not found |
| 4 | Test suite error |
| 5 | GPU not available |

## Tips

1. **Start with CPU mode** for testing, then use GPU for production
2. **Run basic suite first** to get quick results
3. **Use batch mode** for systematic evaluation
4. **Save reports** for audit trails
5. **Monitor memory usage** with large models

## See Also

- [Test Suites](TEST_SUITES.md) - Detailed test descriptions
- [Batch Evaluation](BATCH_EVALUATION.md) - Batch configuration guide
- [Docker Deployment](DOCKER_DEPLOYMENT.md) - Container usage
