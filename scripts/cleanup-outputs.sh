#!/bin/bash
# Cleanup script for Docker-created output directories
# Uses Docker to remove files with proper permissions

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧹 Cleaning up output directories...${NC}"

# Function to clean a directory using Docker
cleanup_dir() {
    local dir="$1"
    if [ -d "$dir" ]; then
        echo "  Cleaning $dir..."
        # Use a Docker container running as root to ensure we can remove all files
        docker run --rm \
            -v "$(pwd)/$dir:/cleanup" \
            busybox \
            sh -c "find /cleanup -mindepth 1 -delete 2>/dev/null || true"

        # Remove the directory itself if empty
        rmdir "$dir" 2>/dev/null || true
    fi
}

# Clean up known output directories
cleanup_dir "outputs/mcp-content"
cleanup_dir "outputs/mcp-gaea2"

# Also clean up the parent directory if empty
rmdir "outputs" 2>/dev/null || true

echo -e "${GREEN}✅ Output directories cleaned up${NC}"
