#!/bin/bash
# Run issue monitor with hybrid agent support
# - Claude and Gemini run on host (authentication requirements)
# - OpenCode and Crush run in Docker containers

set -e

echo "=== Running Issue Monitor with Hybrid Agent Support ==="
echo ""

# Set up environment
export PYTHONPATH="${GITHUB_WORKSPACE:-$(pwd)}"
export PYTHONUNBUFFERED="1"

# Check if running in GitHub Actions
if [ -n "$GITHUB_ACTIONS" ]; then
    echo "[INFO] Running in GitHub Actions environment"
    echo "[INFO] Repository: $GITHUB_REPOSITORY"
fi

# Load nvm if available (for Claude CLI)
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    export NVM_DIR="$HOME/.nvm"
    # shellcheck source=/dev/null
    . "$NVM_DIR/nvm.sh"
    if command -v nvm &> /dev/null; then
        echo "[INFO] Setting Node.js version with nvm..."
        # Use .nvmrc for Node.js version
        nvm install || {
            echo "[WARNING] Installing Node.js version from .nvmrc..."
            nvm install "$(cat .nvmrc)"
        }
        nvm use
        echo "[INFO] Node.js version: $(node --version)"
    fi
fi

# Verify Claude CLI is available (for host execution)
if command -v claude &> /dev/null; then
    echo "[INFO] Claude CLI found at: $(which claude)"
    echo "[INFO] Claude version: $(claude --version 2>&1 || echo 'version check failed')"

    # Check authentication
    if [ -f "$HOME/.claude.json" ] || [ -d "$HOME/.claude" ]; then
        echo "[INFO] Claude authentication found"
    else
        echo "[WARNING] No Claude credentials found - Claude agent may not work"
    fi
else
    echo "[WARNING] Claude CLI not found on host"
fi

# Verify Gemini CLI is available (for host execution)
if command -v gemini &> /dev/null; then
    echo "[INFO] Gemini CLI found at: $(which gemini)"
else
    echo "[WARNING] Gemini CLI not found on host"
fi

# Check Docker availability (for containerized agents)
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "[INFO] Docker and docker-compose are available"

    # Verify openrouter-agents container is available (using the agents profile)
    if docker-compose --profile agents config --services 2>/dev/null | grep -q "openrouter-agents"; then
        echo "[INFO] openrouter-agents service found in docker-compose.yml"

        # Build the container if needed
        echo "[INFO] Ensuring openrouter-agents container is up to date..."
        docker-compose --profile agents build openrouter-agents || {
            echo "[WARNING] Failed to build openrouter-agents container"
            echo "[WARNING] OpenCode and Crush agents will not be available"
        }
    else
        echo "[WARNING] openrouter-agents service not found in docker-compose.yml"
        echo "[WARNING] OpenCode and Crush agents will not be available"
    fi
else
    echo "[WARNING] Docker or docker-compose not found"
    echo "[WARNING] OpenCode and Crush agents will not be available"
fi

# Run the issue monitor
echo ""
echo "[INFO] Starting issue monitor..."
echo "[INFO] Host agents: Claude, Gemini"
echo "[INFO] Container agents: OpenCode, Crush"
echo ""

# Execute the issue monitor
cd "${GITHUB_WORKSPACE:-$(pwd)}"
python3 -m github_ai_agents.cli issue-monitor "$@"
