# Auto-Formatting Git Commits

This project uses `automation-cli` for code formatting and quality checks.

## Running Checks

```bash
# Check formatting
automation-cli ci run format

# Full linting (ruff + ty)
automation-cli ci run lint-full

# Auto-fix formatting
automation-cli ci run autoformat

# All CI checks
automation-cli ci run full
```

## Manual Approach

If a commit fails due to formatting:

```bash
# Auto-fix formatting
automation-cli ci run autoformat

# Stage the formatted files
git add -u

# Retry the commit
git commit
```
