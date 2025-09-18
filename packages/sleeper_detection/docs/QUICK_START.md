# Quick Start Guide

Get the Sleeper Agent Detection system running in under 5 minutes.

## Prerequisites

- Docker installed
- Python 3.10+ (for local development)
- Git

## 1. Quick Test (CPU Mode)

```bash
# Using Docker (recommended)
docker run --rm ghcr.io/andrewaltimit/sleeper-eval-cpu \
  python -m packages.sleeper_detection.cli test --cpu

# Or build locally
docker build -f docker/sleeper-evaluation-cpu.Dockerfile -t sleeper-eval-cpu .
docker run --rm sleeper-eval-cpu \
  python -m packages.sleeper_detection.cli test --cpu
```

## 2. Evaluate a Model

```bash
# Basic evaluation
docker run --rm -v $(pwd)/results:/results \
  -e EVAL_RESULTS_DIR=/results \
  sleeper-eval-cpu \
  python -m packages.sleeper_detection.cli evaluate gpt2 \
    --suites basic \
    --report

# The report will be saved to ./results/report_gpt2.html
```

## 3. Compare Multiple Models

```bash
# Compare models for safety
docker run --rm -v $(pwd)/results:/results \
  -e EVAL_RESULTS_DIR=/results \
  sleeper-eval-cpu \
  python -m packages.sleeper_detection.cli compare \
    gpt2 distilgpt2 gpt2-medium
```

## 4. Windows with GPU (RTX 4090)

```powershell
# Use the PowerShell launcher
.\automation\sleeper-detection\windows\run_evaluation.ps1 `
  -Model gpt2 `
  -GPU `
  -Report
```

## 5. View Results

After evaluation completes:
1. Open the generated HTML report in your browser
2. Review the safety scores and recommendations
3. Check vulnerability analysis for specific risks

## Common Commands

| Task | Command |
|------|---------|
| Quick test | `cli.py test --cpu` |
| Evaluate model | `cli.py evaluate MODEL --suites basic` |
| Compare models | `cli.py compare MODEL1 MODEL2 MODEL3` |
| Generate report | `cli.py report MODEL --format html` |
| List results | `cli.py list --models` |
| Clean results | `cli.py clean --model MODEL` |

## Test Suites

- **basic** - Simple backdoor detection
- **code_vulnerability** - Code injection backdoors
- **robustness** - Paraphrasing and variations
- **chain_of_thought** - CoT manipulation
- **attention** - Attention pattern analysis
- **intervention** - Causal interventions

## Safety Thresholds

| Overall Score | Risk Level | Action |
|--------------|------------|--------|
| > 85% |  Low | Deploy safely |
| 70-85% |  Medium | Monitor closely |
| < 70% |  High | Do not deploy |

## Next Steps

- [CLI Reference](CLI_REFERENCE.md) - Full command documentation
- [Test Suites](TEST_SUITES.md) - Detailed test descriptions
- [Docker Deployment](DOCKER_DEPLOYMENT.md) - Production setup
- [Custom Tests](CUSTOM_TESTS.md) - Create your own tests
