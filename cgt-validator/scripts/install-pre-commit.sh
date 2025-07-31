#!/bin/bash
# Install and configure pre-commit hooks for CGT Validator

set -e

echo "Setting up pre-commit hooks for CGT Validator..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    pip install pre-commit
fi

# Install the pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Install commit-msg hook for conventional commits (optional)
pre-commit install --hook-type commit-msg 2>/dev/null || true

# Run pre-commit on all files to check current state
echo "Running pre-commit on all files..."
pre-commit run --all-files || true

echo ""
echo "✓ Pre-commit hooks installed successfully!"
echo ""
echo "The following hooks are now active:"
echo "  - Black (Python formatting)"
echo "  - isort (Import sorting)"
echo "  - Flake8 (Python linting)"
echo "  - YAML linting"
echo "  - Shell script checking"
echo "  - Type checking with mypy"
echo "  - Security checks with Bandit"
echo "  - Dockerfile linting"
echo "  - And more..."
echo ""
echo "To run hooks manually: pre-commit run --all-files"
echo "To skip hooks: git commit --no-verify"
echo "To update hooks: pre-commit autoupdate"
