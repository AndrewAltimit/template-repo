#!/bin/bash
# Setup pre-commit hooks for the repository

set -e

echo "🔧 Setting up pre-commit hooks..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
fi

# Install the pre-commit hooks
echo "🔗 Installing git hooks..."
pre-commit install

# Update hooks to latest versions
echo "🔄 Updating hooks to latest versions..."
pre-commit autoupdate

# Run on all files to check current state
echo "🧪 Running pre-commit on all files..."
pre-commit run --all-files || true

echo "✅ Pre-commit hooks installed successfully!"
echo ""
echo "Pre-commit will now run automatically on git commit."
echo "To run manually: pre-commit run --all-files"
echo "To skip hooks: git commit --no-verify"
