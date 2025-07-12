#!/bin/bash
# Emergency workspace cleanup script for permission issues
# This should only be needed if cache files were created before prevention measures

set -euo pipefail

echo "🧹 Emergency workspace cleanup"
echo "This will remove Python cache files that might have permission issues"

# Track if any errors occur
errors_occurred=0

# Find and remove Python cache files
echo "Removing __pycache__ directories..."
if ! find . -type d -name "__pycache__" -print -exec rm -rf {} + 2>/dev/null; then
    echo "⚠️  Some __pycache__ directories could not be removed (may need sudo)"
    errors_occurred=1
fi

echo "Removing .pyc files..."
if ! find . -type f -name "*.pyc" -print -delete 2>/dev/null; then
    echo "⚠️  Some .pyc files could not be removed"
    errors_occurred=1
fi

echo "Removing pytest cache..."
if [ -d ".pytest_cache" ]; then
    if ! rm -rf .pytest_cache; then
        echo "⚠️  Could not remove .pytest_cache directory"
        errors_occurred=1
    fi
fi

echo "Removing coverage files..."
for pattern in .coverage .coverage.* htmlcov; do
    if [ -e "$pattern" ]; then
        if ! rm -rf "$pattern"; then
            echo "⚠️  Could not remove $pattern"
            errors_occurred=1
        fi
    fi
done

echo "Removing mypy cache..."
if [ -d ".mypy_cache" ]; then
    if ! rm -rf .mypy_cache; then
        echo "⚠️  Could not remove .mypy_cache directory"
        errors_occurred=1
    fi
fi

if [ $errors_occurred -eq 0 ]; then
    echo "✅ Cleanup complete - all files removed successfully"
else
    echo "⚠️  Cleanup completed with warnings - some files may need manual removal"
    echo "   If permission errors persist, try: sudo $0"
    exit 1
fi
