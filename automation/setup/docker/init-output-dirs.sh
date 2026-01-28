#!/bin/bash
# Pre-create output directories with correct ownership for Docker bind mounts
# This prevents docker compose from creating them as root when run with sudo

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
    "outputs/blender/projects"
    "outputs/blender/assets"
    "outputs/blender/renders"
    "outputs/blender/templates"
    "outputs/elevenlabs_speech"
    "outputs/video-editor"
    "outputs/url-fetcher"
    "outputs/desktop-control"
    "evaluation_results"
)

# Create directories with correct ownership
for dir in "${OUTPUT_DIRS[@]}"; do
    # Skip symlinks to prevent chown on unintended paths
    if [ -L "$dir" ]; then
        echo "[WARN] Skipping symlink: $dir"
        continue
    fi

    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo -e "${GREEN}[OK]${NC} Created: $dir"
    else
        # Fix ownership if directory already exists but owned by root
        if [ "$(stat -c '%u' "$dir")" -eq 0 ]; then
            # Use Docker to fix permissions (avoids sudo password prompts)
            if command -v docker &> /dev/null; then
                echo "  Fixing ownership via Docker: $dir"
                DIR_PATH="$(cd "$dir" && pwd)"
                if command -v timeout &> /dev/null; then
                    # timeout prevents hanging if Docker daemon is unresponsive
                    timeout 30 docker run --rm -v "$DIR_PATH:/target" busybox:1.36.1 chown -Rh "$USER_ID:$GROUP_ID" /target 2>/dev/null
                else
                    # Fallback without timeout on systems that don't have it
                    docker run --rm -v "$DIR_PATH:/target" busybox:1.36.1 chown -Rh "$USER_ID:$GROUP_ID" /target 2>/dev/null
                fi && \
                    echo -e "${GREEN}[OK]${NC} Fixed ownership: $dir" || \
                    echo "[WARN] Could not fix ownership via Docker: $dir"
            else
                echo "[WARN] Directory exists with root ownership but Docker not available: $dir"
            fi
        else
            echo -e "${GREEN}[OK]${NC} Already exists: $dir"
        fi
    fi

    # Set proper permissions (755 is sufficient, not 777)
    chmod 755 "$dir" 2>/dev/null || true
done

echo -e "${GREEN}[OK] Output directory initialization complete${NC}"
