# CLI Reference

Complete command-line interface documentation for the Sleeper Agent Detection system.

## Overview

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
