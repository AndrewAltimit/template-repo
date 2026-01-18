#!/bin/bash
# Pre-create output directories with correct ownership for Docker bind mounts
# This prevents docker-compose from creating them as root when run with sudo

set -e

# Resolve project root to ensure execution from correct location
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Get current user ID and group ID
USER_ID=$(id -u)
GROUP_ID=$(id -g)

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Initializing output directories for MCP servers...${NC}"
echo "User: $(whoami) (UID: $USER_ID, GID: $GROUP_ID)"

# Define all output directories used by MCP servers and CI/CD
OUTPUT_DIRS=(
    "outputs/mcp-gaea2"
    "outputs/mcp-content"
    "outputs/mcp-memes"
    "outputs/mcp-code-quality"
    "outputs/blender"
    "outputs/elevenlabs_speech"
    "outputs/video-editor"
    "outputs/url-fetcher"
    "outputs/desktop-control"
    "outputs/renders"
    "evaluation_results"
)

# Create directories with correct ownership
for dir in "${OUTPUT_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo -e "${GREEN}✓${NC} Created: $dir"
    else
        # Fix ownership if directory already exists but owned by root
        if [ "$(stat -c '%u' "$dir")" -eq 0 ]; then
            # Use Docker to fix permissions (avoids sudo password prompts)
            if command -v docker &> /dev/null; then
                echo "  Fixing ownership via Docker: $dir"
                docker run --rm \
                    -v "$(cd "$dir" && pwd):/target" \
                    busybox \
                    chown -R "$USER_ID:$GROUP_ID" /target 2>/dev/null && \
                    echo -e "${GREEN}✓${NC} Fixed ownership: $dir" || \
                    echo "⚠️  Could not fix ownership via Docker: $dir"
            else
                echo "⚠️  Directory exists with root ownership but Docker not available: $dir"
            fi
        else
            echo -e "${GREEN}✓${NC} Already exists: $dir"
        fi
    fi

    # Set proper permissions (755 is sufficient, not 777)
    chmod 755 "$dir" 2>/dev/null || true
done

echo -e "${GREEN}✓ Output directory initialization complete${NC}"
