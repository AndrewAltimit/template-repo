# Lint Progress

## Current Status: Migrated to Ruff

Last updated: 2026-01-19

The project has migrated from pylint to **Ruff** for Python linting. Ruff is 10-100x faster and replaces black, flake8, isort, and pylint in a single tool.

## Why Ruff?

- **Speed**: 10-100x faster than traditional Python linters
- **Unified**: Replaces black, flake8, isort, and pylint
- **Compatible**: Supports most pylint/flake8 rules
- **Modern**: Active development with frequent updates

## Configuration

Ruff is configured in `ruff.toml` at the project root.

## CI/CD Enforcement

Lint checks are enforced in PR validation via the `lint-basic` and `lint-full` stages.

### Commands

```bash
# Run ruff linting
./automation/ci-cd/run-ci.sh lint-basic

# Run full lint check
./automation/ci-cd/run-ci.sh lint-full

# Auto-fix issues
./automation/ci-cd/run-ci.sh autoformat

# Direct ruff commands
docker compose run --rm python-ci ruff check .
docker compose run --rm python-ci ruff format --check .
```

## Historical Note

This file previously tracked pylint warning reduction progress. The project migrated to Ruff on 2026-01-19, which provides equivalent or better linting coverage with significantly faster execution.
