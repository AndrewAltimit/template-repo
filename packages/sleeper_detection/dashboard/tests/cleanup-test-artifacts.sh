#!/bin/bash

# Cleanup script for dashboard test artifacts
# Uses Docker to ensure proper permissions when removing files

echo "Cleaning up dashboard test artifacts..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Use busybox Docker container to clean up with proper permissions
docker run --rm -v "$(pwd):/workspace" -w /workspace busybox sh -c "
    echo 'Removing test artifacts...'
    rm -rf __pycache__ 2>/dev/null || true
    rm -rf sample_charts 2>/dev/null || true
    rm -rf test_evaluation_results.db 2>/dev/null || true
    rm -rf test_users.db 2>/dev/null || true
    rm -rf screenshots 2>/dev/null || true
    rm -rf baselines 2>/dev/null || true
    rm -rf test-artifacts 2>/dev/null || true
    rm -rf ai_analysis_results 2>/dev/null || true
    rm -rf ai_feedback 2>/dev/null || true
    find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find . -name '*.pyc' -delete 2>/dev/null || true
    find . -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
    echo 'Cleanup complete!'
"

echo "All test artifacts cleaned up successfully!"
