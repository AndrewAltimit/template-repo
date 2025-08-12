# AGENTS.md

## Build/Lint/Test Commands

```bash
# Run all tests with coverage (containerized)
docker-compose run --rm python-ci pytest tests/ -v --cov=. --cov-report=xml

# Run a specific test file
docker-compose run --rm python-ci pytest tests/test_mcp_tools.py -v

# Run tests with specific test name pattern
docker-compose run --rm python-ci pytest -k "test_format" -v

# Code quality checks
./automation/ci-cd/run-ci.sh format      # Check formatting
./automation/ci-cd/run-ci.sh lint-basic   # Basic linting
./automation/ci-cd/run-ci.sh lint-full    # Full linting suite
./automation/ci-cd/run-ci.sh autoformat   # Auto-format code
./automation/ci-cd/run-ci.sh full        # Run all checks
```

## Code Style Guidelines

### Formatting
- Line length: 127 characters (flake8, isort) or 88 (pylint)
- Use Black for Python formatting
- Use isort for import sorting with Black-compatible settings

### Imports
- Group imports in order: standard library, third-party, local
- Use absolute imports when possible
- No unused imports

### Naming Conventions
- Variables/functions: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE
- Good short names: i, j, k, e, f, _

### Types
- Use type hints where possible
- mypy configured with Python 3.11
- ignore_missing_imports = True

### Error Handling
- Avoid broad exception handling
- Use specific exception types when possible
- Don't use logging f-string interpolation

### Other Rules
- No global statements when possible
- Limit classes to 15 attributes
- Use subprocess-run-check when calling subprocess
