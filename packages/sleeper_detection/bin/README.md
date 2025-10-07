# Sleeper Detection - Quick Start

> **User-facing entry points for the Sleeper Agent Detection System**

## Entry Points

### Interactive Launcher (Recommended)
```bash
./bin/launcher
```

Interactive menu with all operations:
- Launch Dashboard
- Evaluate Models
- Compare Models
- Batch Evaluation
- Generate Reports
- Quick Tests
- List/Clean Results

### Command Line Interface
```bash
./bin/cli COMMAND [OPTIONS]
```

Available commands:
- `evaluate MODEL` - Evaluate a single model
- `compare MODELS` - Compare multiple models
- `batch CONFIG` - Run batch evaluation
- `report MODEL` - Generate report
- `test` - Run quick test
- `list [TYPE]` - List models or results
- `clean [MODEL]` - Clean evaluation results

Examples:
```bash
# Evaluate with GPU
./bin/cli evaluate gpt2 --gpu --report

# Compare models
./bin/cli compare gpt2 distilgpt2 gpt2-medium

# Quick test
./bin/cli test --cpu
```

### Dashboard
```bash
./bin/dashboard [MODE]
```

Modes:
- `mock` - Launch with mock test data (default)
- `empty` - Launch with empty database
- `existing` - Launch with existing database
- `/path/to/db` - Launch with specific database file

Examples:
```bash
# Demo mode with mock data
./bin/dashboard

# Use existing results
./bin/dashboard existing

# Specific database
./bin/dashboard /path/to/evaluation_results.db
```

## Requirements

- Python 3.8+
- CUDA toolkit (optional, for GPU support)
- Docker (optional)

## Getting Started

1. **Quick Test**: Verify your setup
   ```bash
   ./bin/cli test --cpu
   ```

2. **Launch Dashboard**: See what the system can do
   ```bash
   ./bin/dashboard mock
   ```

3. **Evaluate a Model**: Run detection on a real model
   ```bash
   ./bin/cli evaluate gpt2 --suites basic --gpu --report
   ```

## Advanced Usage

For detailed documentation on:
- Script reference and categorization → `docs/SCRIPTS_REFERENCE.md`
- Comprehensive launcher guide → `docs/LAUNCHERS.md`
- Platform-specific operations → `scripts/platform/{linux,windows}/`
- Individual script categories → `scripts/{training,evaluation,validation,analysis,data}/`

## Architecture

```
bin/
├── launcher          # Interactive menu (all platforms)
├── cli               # Command-line interface wrapper
├── dashboard         # Dashboard launcher
└── README.md         # This file

scripts/
├── platform/         # Platform-specific implementations
│   ├── linux/        # Linux bash scripts
│   └── windows/      # Windows PowerShell/batch scripts
├── training/         # Model training operations
├── evaluation/       # Testing & evaluation
├── validation/       # System validation
├── analysis/         # Advanced analysis
├── data/             # Data import/export
└── setup/            # Environment setup
```

## Support

For issues or questions:
- Check `docs/` for detailed documentation
- Review script-specific help: `./bin/cli COMMAND --help`
- See package README: `../README.md`
