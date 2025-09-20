#!/bin/bash
# Cleanup script for __pycache__ and test artifacts
# Uses Docker to remove files with proper permissions

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧹 Cleaning up Python cache and test artifacts...${NC}"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Clean up __pycache__ directories
echo "  Removing __pycache__ directories..."
docker run --rm \
    -v "${SCRIPT_DIR}:/workspace" \
    -w /workspace \
    busybox \
    sh -c "find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"

# Clean up .pyc and .pyo files
echo "  Removing .pyc and .pyo files..."
docker run --rm \
    -v "${SCRIPT_DIR}:/workspace" \
    -w /workspace \
    busybox \
    sh -c "find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true"

# Clean up test artifacts if they exist
echo "  Removing test artifacts..."
docker run --rm \
    -v "${SCRIPT_DIR}:/workspace" \
    -w /workspace \
    busybox \
    sh -c "rm -rf test-artifacts screenshots baselines ai_feedback ai_analysis_results coverage 2>/dev/null || true"

# Clean up pytest cache
echo "  Removing pytest cache..."
docker run --rm \
    -v "${SCRIPT_DIR}:/workspace" \
    -w /workspace \
    busybox \
    sh -c "rm -rf .pytest_cache 2>/dev/null || true"

echo -e "${GREEN}✅ Python cache and test artifacts cleaned up${NC}"
