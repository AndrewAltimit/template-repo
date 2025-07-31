# CGT Validator Development Guide

## Getting Started

### Prerequisites
- Python 3.8+
- Docker (optional but recommended)
- Git

### Initial Setup

```bash
# Clone the repository
git clone <repo-url>
cd cgt-validator

# Set up development environment
make dev-install

# This will:
# - Install all dependencies
# - Install the package in editable mode
# - Set up pre-commit hooks
# - Install development tools
```

## Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality. The hooks are automatically installed when you run `make dev-install`.

### Installed Hooks

1. **Python Formatting**
   - `black` - Automatic code formatting (120 char line length)
   - `isort` - Import sorting (black-compatible profile)
   - `reorder-python-imports` - Additional import cleanup

2. **Python Linting**
   - `flake8` - Style guide enforcement
   - `bandit` - Security issue detection
   - `mypy` - Static type checking

3. **General File Checks**
   - Trailing whitespace removal
   - End-of-file fixer
   - Large file prevention (5MB limit)
   - Merge conflict detection
   - Case conflict detection

4. **YAML/JSON**
   - YAML syntax validation and linting
   - JSON formatting and validation
   - GitHub Actions workflow linting

5. **Documentation**
   - Markdown linting (relaxed rules)
   - Spell checking (if enabled)

6. **Shell Scripts**
   - ShellCheck for bash script validation

7. **Docker**
   - Hadolint for Dockerfile best practices

8. **Project-Specific**
   - Check for hardcoded state names
   - Ensure validators have test files
   - Validate mock data structure

### Working with Pre-commit

```bash
# Run all hooks manually
make pre-commit
# or
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files

# Skip hooks temporarily
git commit --no-verify -m "WIP: Quick fix"

# Update hooks to latest versions
make pre-commit-update
# or
pre-commit autoupdate

# See what changed
git diff
```

### Common Pre-commit Issues and Fixes

1. **Black formatting changes**
   ```bash
   # Auto-fix
   make format
   # Then commit the changes
   ```

2. **Import order issues**
   ```bash
   # Auto-fix with isort
   isort src tests
   ```

3. **Type checking failures**
   ```bash
   # Add type hints or ignore with:
   # type: ignore
   ```

4. **Large file detected**
   - Consider if the file should be tracked
   - Add to .gitignore if not needed
   - Or increase limit in .pre-commit-config.yaml

## Development Workflow

### 1. Create a Feature Branch
```bash
git checkout -b feature/add-massachusetts-validator
```

### 2. Make Changes
```bash
# Edit files
vim src/validators/massachusetts.py

# Run tests
make test

# Check pre-commit
make pre-commit
```

### 3. Test in Docker
```bash
# Build and test in container
make docker-build
make docker-test
```

### 4. Commit Changes
```bash
# Stage changes
git add .

# Commit (pre-commit runs automatically)
git commit -m "feat: add Massachusetts validator"

# If pre-commit fails, fix issues and retry
make format
git add .
git commit -m "feat: add Massachusetts validator"
```

## Code Style Guide

### Python
- Line length: 120 characters
- Use Black formatting
- Follow PEP 8 with Black's modifications
- Use type hints where beneficial
- Docstrings for all public functions/classes

### Imports
```python
# Standard library
import os
from pathlib import Path

# Third-party
import pandas as pd
from click import command

# Local
from validators.base import BaseValidator
```

### Error Messages
```python
# Good: Specific and actionable
raise ValueError(f"Column '{column}' not found in sheet '{sheet}'. Available columns: {', '.join(df.columns)}")

# Bad: Vague
raise ValueError("Invalid data")
```

## Testing

### Running Tests
```bash
# All tests with coverage
make test

# Fast test run (no coverage)
make test-fast

# Specific test file
pytest tests/validators/test_oregon.py -v

# With debugging
pytest tests/validators/test_oregon.py -v -s --pdb
```

### Writing Tests
```python
# tests/validators/test_state.py
import pytest
from validators.state import StateValidator

def test_validator_initialization():
    """Test validator initializes correctly."""
    validator = StateValidator(year=2025)
    assert validator.state == "state"
    assert validator.year == 2025

@pytest.mark.parametrize("input,expected", [
    ("valid_data.xlsx", True),
    ("invalid_data.xlsx", False),
])
def test_validation_results(input, expected):
    """Test validation produces expected results."""
    validator = StateValidator()
    result = validator.validate_file(input)
    assert result.is_valid() == expected
```

## Adding a New State Validator

1. **Create the validator**
   ```bash
   cp src/validators/oregon.py src/validators/massachusetts.py
   # Edit to implement Massachusetts-specific rules
   ```

2. **Create tests**
   ```bash
   cp tests/validators/test_oregon.py tests/validators/test_massachusetts.py
   # Update tests for Massachusetts
   ```

3. **Update configuration**
   ```python
   # src/config/states_config.py
   STATES_CONFIG["massachusetts"] = {
       "urls": {...},
       "requirements": {...}
   }
   ```

4. **Add to CLI**
   ```python
   # src/cli.py
   VALIDATORS["massachusetts"] = MassachusettsValidator
   ```

5. **Create mock data generator**
   ```python
   # src/mock_data/massachusetts_generator.py
   class MassachusettsMockDataGenerator:
       ...
   ```

6. **Run pre-commit checks**
   ```bash
   make pre-commit
   ```

## Docker Development

### Building Images
```bash
# Build main image
docker build -t cgt-validator:dev .

# Build with specific target
docker build --target builder -t cgt-validator:builder .
```

### Running Containers
```bash
# Interactive shell
docker run -it --rm -v $(pwd):/app cgt-validator:dev bash

# Run specific command
docker run --rm -v $(pwd):/app cgt-validator:dev pytest

# Use docker-compose
docker-compose run --rm cgt-dev bash
```

## Continuous Integration

The project uses GitHub Actions for CI/CD:

1. **Pre-commit checks** - Runs on every push
2. **Tests** - Matrix of Python versions and OS
3. **Coverage** - Reports to Codecov
4. **Security** - Bandit and Safety checks
5. **Docker** - Build verification
6. **Benchmarks** - Performance tracking

### CI Best Practices
- Keep CI runs under 10 minutes
- Use caching for dependencies
- Run expensive tests only on main/PR
- Use matrix strategy for version testing

## Troubleshooting

### Pre-commit Issues
```bash
# Reset pre-commit
pre-commit clean
pre-commit install

# Skip problematic hook
SKIP=mypy git commit -m "Fix: urgent patch"
```

### Import Errors
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=src:$PYTHONPATH

# Or use the wrapper
./cgt-validate.sh validate oregon --file data.xlsx
```

### Docker Issues
```bash
# Clean Docker cache
docker system prune -a

# Rebuild without cache
docker-compose build --no-cache
```

## Release Process

1. Update version in setup.py and pyproject.toml
2. Update CHANGELOG.md
3. Create PR and get review
4. Merge to main
5. Tag release: `git tag -a v0.2.0 -m "Release version 0.2.0"`
6. Push tag: `git push origin v0.2.0`
7. GitHub Actions will handle the rest
