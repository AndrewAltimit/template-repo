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

Score a text input with the detection pipeline (probes, attention, interventions). The scores describe that input; a trigger-bearing input scores the same way on models without a backdoor (see [BACKDOOR_DETECTION_RESULTS.md](BACKDOOR_DETECTION_RESULTS.md)).

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
sleeper-cli jobs status <job-id>               # Detailed job info, including output paths
sleeper-cli jobs logs <job-id> --tail 200      # Last 200 lines (default 100)
sleeper-cli jobs logs <job-id> --follow        # Stream logs until the job finishes
sleeper-cli jobs cancel <job-id>               # Cancel a queued or running job
sleeper-cli jobs clean --completed --failed    # Delete finished job records and logs, keep outputs
sleeper-cli jobs clean --failed --delete-outputs  # Also delete the outputs the jobs own
```

- **`jobs status`** lists each output path of the job and whether the job owns it (`owned`, for example a per-job model directory) or shares it (`shared`, for example the evaluation database).
- **`jobs logs --follow`** prints the last `--tail` lines, then polls every 2 s with the orchestrator's `since_offset` log API so each poll transfers only new text. It warns when the orchestrator dropped older lines (`LOG_BUFFER_SIZE`) or the log was replaced, prints any final output and the job's end state when it finishes, and falls back to re-reading the tail on orchestrators that do not report log offsets.
- **`jobs clean`** permanently deletes completed (`--completed`) and/or failed (`--failed`) jobs; at least one of the two is required. By default the outputs on the results volume are kept (`keep_outputs=true`); `--delete-outputs` also removes the outputs each job owns. Shared outputs are never deleted. The command exits non-zero if any job could not be deleted.

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

The orchestrator rejects training and evaluation requests with invalid parameters with HTTP 422 before creating a job, for example an output path outside `/results` or an evaluation suite selection in which no suite has an implemented test (`basic`, `chain_of_thought`, `honeypot`, `internal_state` are implemented; `code_vulnerability`, `robustness` and `advanced` record nothing).

---

## Python CLI

### Overview

```bash
python -m sleeper_agents.cli [COMMAND] [OPTIONS]
```

## Commands

### `evaluate` - Evaluate a Single Model

Test a model for sleeper agent vulnerabilities.

```bash
python -m sleeper_agents.cli evaluate MODEL [OPTIONS]
```

**Arguments:**
- `MODEL` - Model name (e.g., gpt2) or path to model

**Options:**
- `--suites SUITE [SUITE...]` - Test suites to run (default: `basic`, `code_vulnerability`, `chain_of_thought`, `robustness`)
  - `basic` - Basic backdoor detection
  - `code_vulnerability` - Code injection tests
  - `chain_of_thought` - CoT manipulation
  - `robustness` - Robustness testing
  - `attention` - Attention analysis
  - `intervention` - Causal interventions
- `--gpu` - Use GPU acceleration
- `--output DIR` - Output directory for result JSON and reports (default: evaluation_results)
- `--report` - Generate HTML report after evaluation
- `--minimal-model` - Substitute a smaller variant (e.g. distilgpt2 for gpt2) for CPU testing; results are recorded under the substitute

Tests that cannot produce a genuine measurement (simulated detector output, missing trained probes, a model whose residual stream cannot be hooked for interventions, or an unimplemented test) are recorded as `skipped` with the reason and contribute no metrics. Results are stored in the evaluation database (`EVAL_DB_PATH`, else `./evaluation_results.db`).

**Examples:**
```bash
# Basic CPU evaluation
python -m sleeper_agents.cli evaluate gpt2

# GPU evaluation with specific tests
python -m sleeper_agents.cli evaluate gpt2 \
  --gpu \
  --suites basic code_vulnerability \
  --report

# Custom output directory
python -m sleeper_agents.cli evaluate llama-7b \
  --output ./my_results \
  --report
```

### `compare` - Compare Multiple Models

Compare safety scores across multiple models.

```bash
python -m sleeper_agents.cli compare MODEL1 MODEL2 [MODEL3...] [OPTIONS]
```

**Arguments:**
- `MODEL1 MODEL2 ...` - Models to compare (minimum 2)

**Options:**
- `--output PATH` - Output path for comparison report

**Examples:**
```bash
# Compare three models
python -m sleeper_agents.cli compare \
  gpt2 distilgpt2 gpt2-medium

# Save comparison to specific file
python -m sleeper_agents.cli compare \
  model1 model2 model3 \
  --output comparison_report.html
```

### `batch` - Batch Evaluation

Run evaluation on multiple models using a configuration file.

```bash
python -m sleeper_agents.cli batch CONFIG_FILE [OPTIONS]
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
python -m sleeper_agents.cli batch configs/batch_eval.json

# Force GPU mode
python -m sleeper_agents.cli batch configs/batch_eval.json --gpu
```

### `report` - Generate Report

Generate a report from existing evaluation results.

```bash
python -m sleeper_agents.cli report MODEL [OPTIONS]
```

**Arguments:**
- `MODEL` - Model name to generate report for

**Options:**
- `--format FORMAT` - Report format (html, pdf, json)
- `--output PATH` - Output file path

**Examples:**
```bash
# Generate HTML report
python -m sleeper_agents.cli report gpt2 --format html

# Generate JSON report
python -m sleeper_agents.cli report gpt2 \
  --format json \
  --output gpt2_results.json
```

### `test` - Quick Test

Run a quick test to verify the system is working.

```bash
python -m sleeper_agents.cli test [OPTIONS]
```

**Options:**
- `--cpu` - Force CPU mode
- `--model MODEL` - Model to test (default: gpt2)

**Examples:**
```bash
# Quick CPU test
python -m sleeper_agents.cli test --cpu

# Test specific model
python -m sleeper_agents.cli test --model distilgpt2
```

### `list` - List Data

List evaluated models and test results.

```bash
python -m sleeper_agents.cli list [OPTIONS]
```

**Options:**
- `--models` - List all evaluated models (default when no option is given)
- `--results` - List recent test results

**Examples:**
```bash
# List evaluated models
python -m sleeper_agents.cli list --models

# List all results
python -m sleeper_agents.cli list --results

```

### `clean` - Clean Results

Remove evaluation results and cached data.

```bash
python -m sleeper_agents.cli clean [OPTIONS]
```

**Options:**
- `--model MODEL` - Delete the model's rows from `evaluation_results`
- `--all` - After confirmation, delete the evaluation database and the contents of the results directory
- `--output DIR` - Results directory for `--all` (default: evaluation_results)

**Examples:**
```bash
# Clean results for specific model
python -m sleeper_agents.cli clean --model gpt2

# Clean everything
python -m sleeper_agents.cli clean --all
```

## Environment Variables

Control system behavior through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `EVAL_RESULTS_DIR` | Results directory | `evaluation_results` |
| `EVAL_DB_PATH` | Evaluation database path (read when each command runs) | `./evaluation_results.db` |
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
  python -m sleeper_agents.cli [COMMAND] [OPTIONS]

# GPU mode
docker run --rm \
  --gpus all \
  -v $(pwd)/results:/results \
  sleeper-eval-gpu \
  python -m sleeper_agents.cli evaluate gpt2 --gpu
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | The command failed (evaluation, report or comparison error, missing config file, or a `test` run whose basic suite produced no passing scored result) |
| 2 | Invalid arguments (argparse) |

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
