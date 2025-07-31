# CGT Validator

A comprehensive tool for validating health cost growth target (CGT) data submissions for multiple US states.

## Features

- Automated scraping of state requirements and templates
- Validation against state-specific requirements
- User-friendly command-line interface
- Detailed HTML/Markdown reports
- Mock data generation for testing
- Comprehensive CI/CD with GitHub Actions
- Pre-commit hooks for code quality
- Docker support for consistent environments

## Quick Start

### Installation

#### Option 1: Docker (Recommended)
```bash
# Build and start services
docker-compose up -d

# Run validation
docker-compose run --rm cgt-validator validate oregon --file mock_data/oregon/test_submission.xlsx

# Or use the Makefile
make docker-build
make docker-up
make docker-test
```

#### Option 2: Local Installation
```bash
# Linux/Mac
./install.sh

# Windows
install.bat

# Or manually with development tools:
make dev-install

# This installs dependencies and sets up pre-commit hooks
```

### Usage

```bash
# Use the wrapper scripts for proper PYTHONPATH setup
# Linux/Mac
./cgt-validate.sh validate oregon --file ./submission.xlsx

# Windows
cgt-validate.bat validate oregon --file ./submission.xlsx

# Or set PYTHONPATH manually:
PYTHONPATH=src cgt-validate validate oregon --file ./submission.xlsx

# Generate report
./cgt-validate.sh validate oregon --file ./submission.xlsx --output report.html

# Create annotated Excel with error highlights
./cgt-validate.sh validate oregon --file ./submission.xlsx --annotate

# Batch validate multiple files
./cgt-validate.sh batch oregon --directory ./submissions --output-dir ./reports
```

## Supported States

- Oregon
- Massachusetts
- Rhode Island
- Washington
- Delaware
- Connecticut
- Vermont
- Colorado

## Documentation

See the `docs/` directory for detailed documentation:
- [User Guide](docs/user_guide.md)
- [Installation](docs/installation.md)
- [Troubleshooting](docs/troubleshooting.md)
