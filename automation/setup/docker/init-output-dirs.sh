#!/bin/bash
# Pre-create output directories with correct ownership for Docker bind mounts
# This prevents docker-compose from creating them as root when run with sudo

set -e

# Get current user ID and group ID
USER_ID=$(id -u)
GROUP_ID=$(id -g)

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Initializing output directories for MCP servers...${NC}"
echo "User: $(whoami) (UID: $USER_ID, GID: $GROUP_ID)"

# Define all output directories used by MCP servers
OUTPUT_DIRS=(
    "outputs/mcp-gaea2"
    "outputs/mcp-content"
    "outputs/mcp-memes"
    "outputs/mcp-code-quality"
    "outputs/blender"
    "outputs/elevenlabs_speech"
    "outputs/video-editor"
    "outputs/url-fetcher"
)

# Create directories with correct ownership
for dir in "${OUTPUT_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo -e "${GREEN}✓${NC} Created: $dir"
    else
        # Fix ownership if directory already exists but owned by root
        if [ "$(stat -c '%u' "$dir")" -eq 0 ]; then
            if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
                sudo chown -R "$USER_ID:$GROUP_ID" "$dir"
                echo -e "${GREEN}✓${NC} Fixed ownership: $dir"
            else
                echo "⚠️  Directory exists with root ownership but cannot fix without sudo: $dir"
            fi
        else
            echo -e "${GREEN}✓${NC} Already exists: $dir"
        fi
    fi

    # Set proper permissions (755 is sufficient, not 777)
    chmod 755 "$dir" 2>/dev/null || true
done

echo -e "${GREEN}✓ Output directory initialization complete${NC}"
