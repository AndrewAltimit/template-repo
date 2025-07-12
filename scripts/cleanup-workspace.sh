#!/bin/bash
# Emergency workspace cleanup script for permission issues
# This should only be needed if cache files were created before prevention measures

set -e

echo "🧹 Emergency workspace cleanup"
echo "This will remove Python cache files that might have permission issues"

# Find and remove Python cache files
echo "Removing __pycache__ directories..."
find . -type d -name "__pycache__" -print -exec rm -rf {} + 2>/dev/null || true

echo "Removing .pyc files..."
find . -type f -name "*.pyc" -print -delete 2>/dev/null || true
find . -type f -name "*.pyo" -print -delete 2>/dev/null || true

echo "Removing pytest cache..."
rm -rf .pytest_cache 2>/dev/null || true

echo "Removing coverage files..."
rm -rf .coverage .coverage.* htmlcov 2>/dev/null || true

echo "Removing mypy cache..."
rm -rf .mypy_cache 2>/dev/null || true

echo "✅ Cleanup complete"