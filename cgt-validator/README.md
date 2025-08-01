# CGT Validator

A comprehensive tool for validating health cost growth target (CGT) data submissions for multiple US states.

## Features

- ✅ Validates CGT submissions for multiple states (Oregon currently implemented)
- ✅ Multiple output formats (HTML, Markdown, JSON, Excel annotation)
- ✅ Automated web scraping for requirements updates
- ✅ User-friendly command-line interface
- ✅ Mock data generation for testing
- ✅ Comprehensive test suite with CI/CD
- ✅ Pre-commit hooks for code quality
- ✅ Docker support for consistent environments
- ✅ Self-contained project structure (easy to extract to own repository)

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
# Quick install using provided scripts
./install.sh       # Linux/Mac
install.bat        # Windows

# Or manual installation:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-cgt.txt
pip install -e .

# With development tools (includes pre-commit hooks):
make dev-install
```

### Usage

```bash
# Basic validation
cgt-validate validate oregon --file submission.xlsx

# With HTML report
cgt-validate validate oregon --file submission.xlsx --output report.html

# With Excel annotation (highlights errors in the original file)
cgt-validate validate oregon --file submission.xlsx --annotate

# Batch validate multiple files
cgt-validate batch oregon --directory ./submissions --output-dir ./reports

# Using wrapper scripts (ensures proper PYTHONPATH):
./cgt-validate.sh validate oregon --file ./submission.xlsx    # Linux/Mac
cgt-validate.bat validate oregon --file ./submission.xlsx     # Windows
```

## Supported States

| State | Status | Template Support |
|-------|--------|------------------|
| Oregon | ✅ Implemented | Full validation |
| Massachusetts | 🚧 Coming Soon | - |
| Rhode Island | 🚧 Coming Soon | - |
| Washington | 🚧 Coming Soon | - |
| Delaware | 🚧 Coming Soon | - |
| Connecticut | 🚧 Coming Soon | - |
| Vermont | 🚧 Coming Soon | - |
| Colorado | 🚧 Coming Soon | - |

## Project Structure

```
cgt-validator/
├── src/                    # Source code
│   ├── validators/         # State-specific validators
│   ├── scrapers/          # Web scraping modules
│   └── utils/             # Shared utilities
├── tests/                 # Test suite
├── docs/                  # Documentation
├── mock_data/             # Sample data for testing
├── .github/workflows/     # CI/CD pipelines
├── requirements-cgt.txt   # All dependencies
├── setup.py              # Package setup
└── Makefile              # Development tasks
```

## Dependencies

All dependencies are listed in `requirements-cgt.txt`:
- **Core**: pandas, openpyxl, click
- **Web scraping**: beautifulsoup4, requests
- **PDF parsing**: pdfplumber, PyPDF2
- **Testing**: pytest, pytest-cov
- **Quality**: black, isort, flake8, mypy

## Standalone Deployment

This project is designed to be easily extracted into its own repository:

1. **Self-contained**: All project files are within the `cgt-validator/` directory
2. **Independent**: No dependencies on parent repository
3. **Ready to go**: Includes its own CI/CD, documentation, and configuration

### To Extract to Own Repository:

```bash
# 1. Copy the entire cgt-validator directory
cp -r cgt-validator/ /path/to/new/location/

# 2. Initialize new repository
cd /path/to/new/location/
git init

# 3. Add remote and push
git remote add origin <your-repo-url>
git add .
git commit -m "Initial commit"
git push -u origin main
```

## Documentation

For detailed information, see the `docs/` directory:
- [User Guide](docs/user_guide.md) - Complete usage instructions
- [Installation Guide](docs/installation.md) - Detailed setup options
- [Development Guide](docs/DEVELOPMENT.md) - Contributing and development setup
- [Troubleshooting](docs/troubleshooting.md) - Common issues and solutions

## Development

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for information on:
- Setting up the development environment
- Running tests
- Code style and linting
- Contributing guidelines

## License

[License information to be added]
