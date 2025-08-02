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
        # Also remove the directory itself to prevent permission issues
        docker run --rm \
            -v "$(pwd)/$dir:/cleanup" \
            busybox \
            sh -c "rm -rf /cleanup/* /cleanup/.[!.]* /cleanup/..?* 2>/dev/null || true"
    fi
}

# Clean up the entire outputs directory if it exists
if [ -d "outputs" ]; then
    echo "  Cleaning entire outputs directory..."
    # Use Docker to remove the entire directory with proper permissions
    docker run --rm \
        -v "$(pwd):/workspace" \
        -w /workspace \
        busybox \
        sh -c "rm -rf outputs 2>/dev/null || true"

    # Recreate the outputs directory with proper permissions
    mkdir -p outputs
    chmod 755 outputs
else
    echo "  No outputs directory found - creating it"
    mkdir -p outputs
    chmod 755 outputs
fi

echo -e "${GREEN}✅ Output directories cleaned up${NC}"
