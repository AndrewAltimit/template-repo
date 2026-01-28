# Sleeper Agent Detection - Automation Scripts

> **Comprehensive launcher scripts for all sleeper agent detection operations on Windows and Linux**

## Directory Structure

```
packages/sleeper_agents/
├── bin/
│   ├── launcher            # Universal interactive menu (Linux/macOS)
│   ├── dashboard           # Dashboard launcher
│   └── cli                 # CLI entry point
├── dashboard/
│   ├── start.sh            # Start dashboard (local/Docker)
│   └── start_with_mock_data.sh  # Start with demo data
└── scripts/
    └── platform/
        ├── linux/
        │   ├── run_cli.sh          # CLI runner for all operations
        │   └── batch_evaluate.sh   # Batch evaluation script
        └── windows/
            ├── run_cli.ps1         # PowerShell CLI runner
            ├── batch_evaluate.ps1  # PowerShell batch evaluation
            ├── launch_dashboard.ps1 # Dashboard launcher
            ├── launch_dashboard.bat # Dashboard batch launcher
            ├── launch_cpu.ps1      # CPU-only evaluation
            ├── launch_gpu.bat      # GPU batch launcher
            ├── launch_gpu.ps1      # GPU PowerShell launcher
            └── run_evaluation.ps1  # Main evaluation runner
```

## Quick Start

### Interactive Menu Launcher (Recommended)

**Linux/macOS:**
```bash
./packages/sleeper_agents/bin/launcher
```

This provides an interactive menu with all operations:
- Launch Dashboard
- Evaluate Models
- Compare Models
- Batch Evaluation
- Generate Reports
- Quick Tests
- List/Clean Results

### Direct Command Line

**Linux:**
```bash
# Evaluate single model with GPU
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh evaluate gpt2 --gpu --report

# Compare multiple models
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh compare gpt2 distilgpt2 gpt2-medium

# Batch evaluation
./packages/sleeper_agents/scripts/platform/linux/batch_evaluate.sh --gpu --compare
```

**Windows PowerShell:**
```powershell
# Evaluate single model with GPU
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 evaluate gpt2 -GPU -GenerateReport

# Compare multiple models
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 compare @("gpt2", "distilgpt2", "gpt2-medium")

# Batch evaluation
.\packages\sleeper_agents\scripts\platform\windows\batch_evaluate.ps1 -GPU -CompareResults
```

## Dashboard Operations

### Launch Dashboard

**Linux:**
```bash
# With mock data (recommended for demos)
./packages/sleeper_agents/dashboard/start.sh

# With existing database
./packages/sleeper_agents/dashboard/start.sh existing

# With specific database file
./packages/sleeper_agents/dashboard/start.sh /path/to/database.db
```

**Windows:**
```powershell
# Launch with Docker Compose (recommended)
.\packages\sleeper_agents\scripts\platform\windows\launch_dashboard.ps1 -Mode docker compose -Database mock

# Launch locally
.\packages\sleeper_agents\scripts\platform\windows\launch_dashboard.ps1 -Mode local -OpenBrowser

# Launch with custom database
.\packages\sleeper_agents\scripts\platform\windows\launch_dashboard.ps1 -Database "C:\path\to\database.db"
```

## Model Evaluation

### Single Model Evaluation

**Linux:**
```bash
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh evaluate gpt2 \
  --suites basic code_vulnerability robustness \
  --gpu \
  --report \
  --open
```

**Windows:**
```powershell
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 evaluate gpt2 `
  -Suites @("basic", "code_vulnerability", "robustness") `
  -GPU `
  -GenerateReport `
  -Open
```

### Available Test Suites

- `basic` - Simple trigger detection, layer probing
- `code_vulnerability` - SQL injection, XSS backdoors
- `chain_of_thought` - Reasoning manipulation
- `robustness` - Paraphrasing, multilingual, honeypots
- `attention` - Attention pattern analysis
- `intervention` - Causal validation tests
- `advanced` - Comprehensive advanced tests
- `all` - Run all available tests

## Batch Evaluation

### Using Configuration File

Create `batch_config.json`:
```json
{
  "models": ["gpt2", "distilgpt2", "gpt2-medium", "pythia-70m"],
  "test_suites": ["basic", "code_vulnerability", "robustness"],
  "output_dir": "batch_results",
  "gpu_mode": true,
  "reporting": {
    "generate_comparison_report": true,
    "report_format": "html"
  }
}
```

**Linux:**
```bash
./packages/sleeper_agents/scripts/platform/linux/batch_evaluate.sh \
  --config batch_config.json \
  --gpu \
  --compare \
  --open
```

**Windows:**
```powershell
.\packages\sleeper_agents\scripts\platform\windows\batch_evaluate.ps1 `
  -Config "batch_config.json" `
  -GPU `
  -CompareResults `
  -OpenReport
```

### Direct Model List

**Linux:**
```bash
./packages/sleeper_agents/scripts/platform/linux/batch_evaluate.sh \
  --models "gpt2 distilgpt2 gpt2-medium" \
  --suites "basic robustness" \
  --gpu \
  --continue  # Continue on errors
```

**Windows:**
```powershell
.\packages\sleeper_agents\scripts\platform\windows\batch_evaluate.ps1 `
  -Models @("gpt2", "distilgpt2", "gpt2-medium") `
  -Suites @("basic", "robustness") `
  -GPU `
  -ContinueOnError
```

## Report Generation

### Generate HTML Report

**Linux:**
```bash
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh report gpt2 \
  --format html \
  --output reports/gpt2_report.html \
  --open
```

**Windows:**
```powershell
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 report gpt2 `
  -Format html `
  -Output "reports\gpt2_report.html" `
  -Open
```

### Compare Multiple Models

**Linux:**
```bash
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh compare \
  gpt2 distilgpt2 gpt2-medium \
  --output comparison.html
```

**Windows:**
```powershell
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 compare `
  @("gpt2", "distilgpt2", "gpt2-medium") `
  -Output "comparison.html"
```

## Docker Support

All scripts support Docker execution for consistency:

**Linux:**
```bash
# Use --docker flag
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh evaluate gpt2 --docker --gpu
```

**Windows:**
```powershell
# Use -Docker switch
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 evaluate gpt2 -Docker -GPU
```

## Utility Operations

### List Evaluated Models

**Linux:**
```bash
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh list models
```

**Windows:**
```powershell
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 list models
```

### Clean Results

**Linux:**
```bash
# Clean specific model
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh clean --model gpt2

# Clean all results
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh clean
```

**Windows:**
```powershell
# Clean specific model
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 clean -Models @("gpt2")

# Clean all results
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 clean
```

## Advanced Options

### GPU Acceleration

All evaluation scripts support GPU acceleration:
- Linux: Add `--gpu` flag
- Windows: Add `-GPU` switch

### Verbose Output

For debugging:
- Linux: Add `--verbose` or `-v`
- Windows: Add `-Verbose`

### Continue on Error

For batch operations:
- Linux: Add `--continue` or `-e`
- Windows: Add `-ContinueOnError`

## Requirements

### Linux/macOS
- Python 3.8+
- Bash 4.0+
- Docker (optional)
- CUDA toolkit (for GPU support)

### Windows
- Python 3.8+
- PowerShell 5.1+
- Docker Desktop (optional)
- CUDA toolkit (for GPU support)

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Permission denied | Run `chmod +x *.sh` on Linux scripts |
| Python not found | Ensure Python is in PATH |
| CUDA not available | Install CUDA toolkit and PyTorch with CUDA |
| Docker not running | Start Docker daemon/service |
| Out of memory | Reduce batch size or use CPU mode |

### Debug Mode

Enable verbose output for troubleshooting:

**Linux:**
```bash
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh evaluate gpt2 --verbose
```

**Windows:**
```powershell
.\packages\sleeper_agents\scripts\platform\windows\run_cli.ps1 evaluate gpt2 -Verbose
```

## Related Documentation

- [Sleeper Detection Package](../README.md)
- [CLI Reference](CLI_REFERENCE.md)
- [Docker Deployment](DOCKER_DEPLOYMENT.md)
- [Windows Deployment](WINDOWS_DEPLOYMENT.md)
- [Test Suites](TEST_SUITES.md)

## Best Practices

1. **Start with Quick Test**: Run a quick CPU test first to verify setup
2. **Use Mock Data**: For dashboard demos, use mock data option
3. **GPU for Production**: Use GPU mode for real evaluations (10-100x faster)
4. **Batch Evaluation**: Evaluate multiple models overnight with batch scripts
5. **Compare Results**: Always generate comparison reports for multiple models
6. **Docker for Consistency**: Use Docker mode for reproducible results

## Example Workflows

### Complete Model Vetting

```bash
# 1. Quick test to verify setup
./packages/sleeper_agents/bin/launcher  # Select option 6

# 2. Evaluate target model
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh evaluate llama2-7b \
  --suites all --gpu --report

# 3. Compare with known safe model
./packages/sleeper_agents/scripts/platform/linux/run_cli.sh compare llama2-7b gpt2

# 4. View results in dashboard
./packages/sleeper_agents/dashboard/start.sh existing
```

### Overnight Batch Evaluation

```bash
# Create config for all models
cat > overnight_eval.json << EOF
{
  "models": ["gpt2", "distilgpt2", "gpt2-medium", "gpt2-large",
             "pythia-70m", "pythia-160m", "pythia-410m"],
  "test_suites": ["basic", "code_vulnerability", "robustness",
                  "chain_of_thought", "attention", "intervention"],
  "output_dir": "overnight_results",
  "gpu_mode": true,
  "reporting": {
    "generate_comparison_report": true,
    "report_format": "html"
  }
}
EOF

# Run overnight with error continuation
nohup ./packages/sleeper_agents/scripts/platform/linux/batch_evaluate.sh \
  --config overnight_eval.json \
  --continue \
  --compare \
  > overnight.log 2>&1 &
```

## Contributing

When adding new launchers or operations:

1. Follow the existing script patterns
2. Support both Linux and Windows
3. Include help/usage documentation
4. Add Docker support where applicable
5. Update this README with examples

## License

Part of the Sleeper Agent Detection System - For defensive security use only.
