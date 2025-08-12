# CRUSH.md - Agentic Coding Agent Configuration

This file contains essential commands and guidelines for agentic coding agents working in this repository.

## Core Commands

### Build and Code Quality
```bash
# Full CI pipeline (formatting, linting, testing)
./automation/ci-cd/run-ci.sh full

# Individual stages
./automation/ci-cd/run-ci.sh format      # Check formatting
./automation/ci-cd/run-ci.sh lint-basic  # Basic linting
./automation/ci-cd/run-ci.sh lint-full   # Full linting suite
./automation/ci-cd/run-ci.sh autoformat  # Auto-format code

# Run a specific test file
docker-compose run --rm python-ci pytest tests/test_specific.py -v

# Run tests with specific pattern
docker-compose run --rm python-ci pytest -k "test_name_pattern" -v
```

### Container Operations
```bash
# Build and start all services
docker-compose up -d

# Rebuild after changes
docker-compose build python-ci

# Run any Python command in CI container
docker-compose run --rm python-ci python --version
```

## Code Style Guidelines

### Python Standards
- Line length: 88 characters (Black), 127 for docstrings/comments (Flake8)
- Import sorting: isort with Black profile
- Type hints: Use where possible, especially for function signatures
- Docstrings: Google style preferred

### Naming Conventions
- Variables: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE
- Private members: prefixed with underscore

### Error Handling
- Prefer specific exceptions over generic ones
- Use context managers for resource management
- Include meaningful error messages
- Log errors appropriately

### Imports
- Group imports in standard order: standard library, third-party, local
- Use absolute imports when possible
- Avoid wildcard imports

## Project-Specific Patterns

### MCP Servers
- All MCP servers run on specific ports (8006-8013)
- Use BaseMCPServer for new implementations
- Tools should return structured JSON responses

### Testing
- Use pytest with fixtures
- Mock external dependencies (HTTP calls, subprocess)
- Write both unit and integration tests
- Maintain test coverage above 80%

### Security
- Never commit secrets or API keys
- Use environment variables for configuration
- Follow the AI agent security model with keyword triggers
- Validate all external inputs
