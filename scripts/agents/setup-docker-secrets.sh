#!/bin/bash
# Script to set up Docker secrets for GitHub token

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Docker secrets for AI agents...${NC}"

# Create secrets directory if it doesn't exist
SECRETS_DIR="./.secrets"
if [ ! -d "$SECRETS_DIR" ]; then
    echo "Creating secrets directory..."
    mkdir -p "$SECRETS_DIR"
    chmod 700 "$SECRETS_DIR"
fi

# Check if GitHub token is available
if [ -z "$GITHUB_TOKEN" ]; then
    # Try to get from gh CLI
    if command -v gh &> /dev/null && gh auth status &> /dev/null; then
        echo "Getting GitHub token from gh CLI..."
        GITHUB_TOKEN=$(gh auth token)
    else
        echo -e "${RED}Error: No GitHub token found${NC}"
        echo "Please either:"
        echo "  1. Set GITHUB_TOKEN environment variable"
        echo "  2. Authenticate with 'gh auth login'"
        exit 1
    fi
fi

# Write token to secret file
SECRET_FILE="$SECRETS_DIR/github_token.txt"
echo "$GITHUB_TOKEN" > "$SECRET_FILE"
chmod 600 "$SECRET_FILE"

echo -e "${GREEN}✓ Docker secret created at $SECRET_FILE${NC}"
echo ""
echo -e "${YELLOW}Important security notes:${NC}"
echo "- The .secrets directory should be added to .gitignore"
echo "- Never commit secrets to the repository"
echo "- The secret file has restricted permissions (600)"
echo ""
echo "To use the AI agents with Docker secrets:"
echo "  docker-compose --profile agents run --rm ai-agents python scripts/agents/run_agents.py"
