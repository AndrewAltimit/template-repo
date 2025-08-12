# Auto-Formatting Git Commits

This project uses the standard pre-commit framework for code formatting and quality checks.

## Problem

When pre-commit hooks reformat your code, the commit fails because files have been modified. You then need to stage the changes and commit again.

## Solution

The project uses the standard pre-commit framework. To set it up:

```bash
# Install pre-commit hooks
./automation/setup/git/setup-pre-commit.sh
```

This installs the pre-commit hooks defined in `.pre-commit-config.yaml`, which include:
- Python formatting (black, isort)
- Python linting (flake8, mypy)
- YAML and JSON validation
- Shell script checking
- And more...

## Manual Approach

If you prefer not to use either automation:

```bash
# When commit fails due to formatting
git add -u                # Stage the formatted files
git commit               # Retry the commit
```
