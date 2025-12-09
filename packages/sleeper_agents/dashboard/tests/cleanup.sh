#!/bin/bash
# Consolidated cleanup script for dashboard test artifacts
# Uses Docker to remove files with proper permissions

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧹 Cleaning up dashboard test artifacts...${NC}"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run cleanup in Docker container for proper permissions
docker run --rm \
    -v "${SCRIPT_DIR}:/workspace" \
    -w /workspace \
    busybox \
    sh -c "
        echo '  Removing directories...'
        rm -rf __pycache__ sample_charts screenshots baselines \
               test-artifacts ai_analysis_results ai_feedback \
               coverage .pytest_cache 2>/dev/null || true

        echo '  Removing database files...'
        rm -rf test_evaluation_results.db test_users.db 2>/dev/null || true

        echo '  Finding and removing all __pycache__ directories...'
        find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

        echo '  Removing Python bytecode files...'
        find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true

        echo '  Removing pytest cache...'
        find . -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
    "

echo -e "${GREEN}[SUCCESS] Dashboard test artifacts cleaned up successfully${NC}"
