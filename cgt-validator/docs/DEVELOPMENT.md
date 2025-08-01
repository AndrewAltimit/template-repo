# CGT Validator - Development Guide

This guide covers setting up the development environment and contributing to the CGT Validator project.

## Development Setup

### Prerequisites
- Python 3.8 or higher
- Git
- Docker (optional, for containerized development)

### Setting Up the Development Environment

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cgt-validator
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   # Install all dependencies including dev tools
   pip install -r requirements-cgt.txt
   pip install -e .

   # Or use make for full dev setup with pre-commit hooks
   make dev-install
   ```

4. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

## Running Tests

### Full Test Suite
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_oregon_validator.py

# Run tests matching a pattern
pytest -k "test_validate"
```

### Using Make Commands
```bash
make test          # Run all tests
make test-cov      # Run tests with coverage
make test-watch    # Run tests in watch mode
```

### Using Docker
```bash
make docker-test   # Run tests in Docker container
```

## Code Style and Linting

The project enforces code quality standards using:
- **Black** for code formatting
- **isort** for import sorting
- **Flake8** for linting
- **mypy** for type checking

### Running Code Quality Checks
```bash
# Format code
make format

# Run all linters
make lint

# Type checking
make type-check

# Run all quality checks
make quality
```

### Pre-commit Hooks
Pre-commit hooks automatically run before each commit:
- Black formatting
- isort import sorting
- Flake8 linting
- Trailing whitespace removal
- End-of-file fixing

## Project Structure

```
src/
├── __init__.py
├── cli.py                  # CLI entry point
├── validators/             # State-specific validators
│   ├── __init__.py
│   ├── base.py            # Base validator class
│   └── oregon.py          # Oregon validator implementation
├── scrapers/              # Web scraping modules
│   ├── __init__.py
│   ├── base.py           # Base scraper class
│   └── oregon.py         # Oregon requirements scraper
├── utils/                 # Shared utilities
│   ├── __init__.py
│   ├── excel.py          # Excel handling utilities
│   └── reporting.py      # Report generation
└── models/               # Data models
    ├── __init__.py
    └── validation.py     # Validation result models
```

## Adding a New State Validator

1. **Create a new validator class** in `src/validators/`:
   ```python
   # src/validators/massachusetts.py
   from .base import BaseValidator

   class MassachusettsValidator(BaseValidator):
       def validate(self, data):
           # Implementation
           pass
   ```

2. **Create a corresponding scraper** in `src/scrapers/`:
   ```python
   # src/scrapers/massachusetts.py
   from .base import BaseScraper

   class MassachusettsScraper(BaseScraper):
       def scrape_requirements(self):
           # Implementation
           pass
   ```

3. **Register the validator** in `src/validators/__init__.py`

4. **Add tests** in `tests/test_massachusetts_validator.py`

5. **Update documentation** and supported states list

## Testing Guidelines

### Unit Tests
- Test individual components in isolation
- Mock external dependencies (web requests, file I/O)
- Aim for >80% coverage

### Integration Tests
- Test validator end-to-end functionality
- Use mock data files in `mock_data/`
- Test all output formats

### Test Data
- Mock data is stored in `mock_data/<state>/`
- Include both valid and invalid test cases
- Document expected validation results

## Debugging

### Verbose Output
```bash
# Enable debug logging
cgt-validate validate oregon --file data.xlsx --verbose

# Or set environment variable
export CGT_DEBUG=1
```

### Common Issues
1. **Import errors**: Ensure PYTHONPATH includes src/
2. **Missing dependencies**: Run `pip install -r requirements-cgt.txt`
3. **Pre-commit failures**: Run `make format` to auto-fix

## Contributing Guidelines

1. **Branch naming**: `feature/description` or `fix/description`
2. **Commit messages**: Use conventional commits (feat:, fix:, docs:, etc.)
3. **Pull requests**: Include tests and update documentation
4. **Code review**: All PRs require review before merging

## Release Process

1. Update version in `setup.py`
2. Update CHANGELOG.md
3. Create a release tag
4. GitHub Actions will handle the rest

## Questions?

For questions or issues, please open a GitHub issue or contact the maintainers.
