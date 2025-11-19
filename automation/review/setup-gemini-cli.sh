#!/bin/bash
# Setup Gemini CLI for PR reviews - handles both OAuth and API key authentication
# This script creates a gemini wrapper that works in non-interactive mode
#
# Note: Gemini CLI with API key requires explicit --model flag for reliable model selection

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Setting up Gemini CLI for PR review..."

# First, try docker-compose approach which handles authentication better
if [ -f "docker-compose.yml" ] && command -v docker-compose >/dev/null 2>&1; then
    echo "Using docker-compose for Gemini setup..."

    # Build the MCP Gemini container if needed
    echo "Building/updating MCP Gemini container..."
    docker-compose build mcp-gemini >/dev/null 2>&1 || {
        echo -e "${YELLOW}Warning: Could not build mcp-gemini container${NC}"
    }

    # Create wrapper using docker-compose run
    # Store the project root path for docker-compose
    PROJECT_ROOT="$(pwd)"
    cat > /tmp/gemini <<EOF
#!/bin/bash
# Wrapper using docker-compose for proper volume mounting
cd "$PROJECT_ROOT"
# Use --no-deps to avoid starting dependent services
# Note: docker-compose warnings go to stderr, Gemini output goes to stdout
# We keep both but warnings won't interfere with the actual output
exec docker-compose run --rm -T --no-deps mcp-gemini gemini "\$@"
EOF
    chmod +x /tmp/gemini

    # Test if it works
    if /tmp/gemini --version 2>/dev/null | grep -q "^[0-9]"; then
        echo -e "${GREEN}Successfully set up Gemini via docker-compose${NC}"
        AUTH_METHOD="docker-compose"
    else
        echo -e "${YELLOW}Docker-compose setup failed, trying fallback methods...${NC}"
        AUTH_METHOD=""
    fi
else
    AUTH_METHOD=""
fi

# If docker-compose didn't work, check other authentication methods
if [ -z "$AUTH_METHOD" ]; then
    if [ -f "$HOME/.gemini/oauth_creds.json" ]; then
        echo -e "${GREEN}Found Gemini OAuth credentials${NC}"
        AUTH_METHOD="oauth"
    else
        echo -e "${RED}No Gemini authentication available${NC}"
        echo "Please authenticate Gemini CLI:"
        echo "  1. Run 'gemini' interactively to start OAuth flow"
        echo "  2. Or set up OAuth by running: nvm use 22.16.0 && gemini"
        echo ""
        echo "Note: Using OAuth free tier (60 req/min, 1000 req/day)"
        echo ""
        echo "Gemini review will be skipped."
        exit 1
    fi
fi

# Handle different authentication methods
if [ "$AUTH_METHOD" = "docker-compose" ]; then
    # Docker-compose already set up the wrapper, nothing more to do
    echo -e "${GREEN}Using docker-compose managed Gemini${NC}"

elif [ "$AUTH_METHOD" = "oauth" ]; then
    echo "Setting up containerized Gemini with OAuth..."

    # Check if container image exists
    if docker images | grep -q "template-repo-mcp-gemini"; then
        echo -e "${GREEN}Found existing mcp-gemini container${NC}"
    else
        echo "Building MCP Gemini container..."
        if [ -f "docker-compose.yml" ]; then
            docker-compose build mcp-gemini
        else
            echo -e "${YELLOW}Warning: docker-compose.yml not found, building with Docker directly${NC}"

            # Create temporary Dockerfile if needed
            cat > /tmp/gemini-dockerfile <<'EOF'
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @google/gemini-cli \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 -s /bin/bash geminiuser
WORKDIR /workspace
USER geminiuser
ENTRYPOINT ["gemini"]
EOF
            docker build -t template-repo-mcp-gemini:latest -f /tmp/gemini-dockerfile /tmp/
            rm /tmp/gemini-dockerfile
        fi
    fi

    # Create wrapper script for containerized Gemini
    cat > /tmp/gemini <<'EOF'
#!/bin/bash
# Wrapper to use containerized Gemini with host OAuth credentials
exec docker run --rm -i \
    -v "$HOME/.gemini:/home/geminiuser/.gemini:ro" \
    -v "$(pwd):/workspace" \
    -e HOME=/home/geminiuser \
    template-repo-mcp-gemini:latest \
    gemini "$@"
EOF
    chmod +x /tmp/gemini

    # Verify it works
    if /tmp/gemini --version >/dev/null 2>&1; then
        echo -e "${GREEN}Containerized Gemini wrapper is working${NC}"
    else
        echo -e "${YELLOW}Warning: Gemini wrapper test failed, but continuing anyway${NC}"
    fi

elif [ "$AUTH_METHOD" = "api_key" ]; then
    # For API key, create a simple passthrough wrapper
    echo "Setting up direct Gemini with API key..."

    # Find the actual gemini command
    GEMINI_CMD=$(which gemini 2>/dev/null || echo "")

    if [ -z "$GEMINI_CMD" ]; then
        # Try common locations
        if [ -f "$HOME/.nvm/versions/node/v22.16.0/bin/gemini" ]; then
            GEMINI_CMD="$HOME/.nvm/versions/node/v22.16.0/bin/gemini"
        elif [ -f "/usr/local/bin/gemini" ]; then
            GEMINI_CMD="/usr/local/bin/gemini"
        else
            echo -e "${RED}ERROR: Gemini CLI not found. Please install with: npm install -g @google/gemini-cli${NC}"
            exit 1
        fi
    fi

    # Create wrapper that ensures API key is set
    cat > /tmp/gemini <<EOF
#!/bin/bash
# Wrapper for direct Gemini with API key
export GEMINI_API_KEY="$GEMINI_API_KEY"
exec $GEMINI_CMD "\$@"
EOF
    chmod +x /tmp/gemini

    echo -e "${GREEN}Direct Gemini wrapper configured${NC}"
fi

# Export PATH so Python subprocess can find our wrapper
export PATH="/tmp:$PATH"

# Clear any cached Gemini sessions that might have old model specifications
# This prevents 404 errors from cached session data
if [ -d "$HOME/.gemini/tmp" ]; then
    echo "Clearing Gemini session cache to prevent model specification conflicts..."
    rm -rf "$HOME/.gemini/tmp/"* 2>/dev/null || true
fi

echo -e "${GREEN}Gemini CLI setup complete${NC}"
echo "Gemini is available at: /tmp/gemini"

# Test that Python can use it
python3 -c "
import subprocess
import sys
try:
    result = subprocess.run(['gemini', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print('Python subprocess test successful')
        sys.exit(0)
    else:
        print('Warning: Python subprocess test failed:', result.stderr[:100])
        sys.exit(1)
except Exception as e:
    print('Warning: Python subprocess test error:', str(e))
    sys.exit(1)
" || echo -e "${YELLOW}Warning: Python test failed but continuing${NC}"
