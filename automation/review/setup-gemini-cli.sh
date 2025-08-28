#!/bin/bash
# Setup Gemini CLI for PR reviews - handles both OAuth and API key authentication
# This script creates a gemini wrapper that works in non-interactive mode
#
# The PR review script will use gemini-2.5-pro model with fallback to gemini-2.5-flash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🤖 Setting up Gemini CLI for PR review..."

# Check authentication method
if [ -f "$HOME/.gemini/oauth_creds.json" ]; then
    echo -e "${GREEN}✅ Found Gemini OAuth credentials${NC}"
    AUTH_METHOD="oauth"
elif [ -n "$GEMINI_API_KEY" ]; then
    echo -e "${GREEN}🔑 Using Gemini API key from environment${NC}"
    AUTH_METHOD="api_key"
else
    echo -e "${RED}❌ No Gemini authentication available${NC}"
    echo "Either:"
    echo "  1. Configure OAuth by running 'gemini' interactively on the runner"
    echo "  2. Set GEMINI_API_KEY environment variable"
    echo ""
    echo "Gemini review will be skipped."
    exit 1
fi

# For OAuth, use containerized approach
if [ "$AUTH_METHOD" = "oauth" ]; then
    echo "📦 Setting up containerized Gemini with OAuth..."

    # Check if container image exists
    if docker images | grep -q "template-repo-mcp-gemini"; then
        echo -e "${GREEN}✅ Found existing mcp-gemini container${NC}"
    else
        echo "🔨 Building MCP Gemini container..."
        if [ -f "docker-compose.yml" ]; then
            docker-compose build mcp-gemini
        else
            echo -e "${YELLOW}⚠️  docker-compose.yml not found, building with Docker directly${NC}"

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
        echo -e "${GREEN}✅ Containerized Gemini wrapper is working${NC}"
    else
        echo -e "${YELLOW}⚠️  Gemini wrapper test failed, but continuing anyway${NC}"
    fi

else
    # For API key, create a simple passthrough wrapper
    echo "🔑 Setting up direct Gemini with API key..."

    # Find the actual gemini command
    GEMINI_CMD=$(which gemini 2>/dev/null || echo "")

    if [ -z "$GEMINI_CMD" ]; then
        # Try common locations
        if [ -f "$HOME/.nvm/versions/node/v22.16.0/bin/gemini" ]; then
            GEMINI_CMD="$HOME/.nvm/versions/node/v22.16.0/bin/gemini"
        elif [ -f "/usr/local/bin/gemini" ]; then
            GEMINI_CMD="/usr/local/bin/gemini"
        else
            echo -e "${RED}❌ Gemini CLI not found. Please install with: npm install -g @google/gemini-cli${NC}"
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

    echo -e "${GREEN}✅ Direct Gemini wrapper configured${NC}"
fi

# Export PATH so Python subprocess can find our wrapper
export PATH="/tmp:$PATH"

echo -e "${GREEN}✅ Gemini CLI setup complete${NC}"
echo "Gemini is available at: /tmp/gemini"

# Test that Python can use it
python3 -c "
import subprocess
import sys
try:
    result = subprocess.run(['gemini', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print('✅ Python subprocess test successful')
        sys.exit(0)
    else:
        print('⚠️  Python subprocess test failed:', result.stderr[:100])
        sys.exit(1)
except Exception as e:
    print('⚠️  Python subprocess test error:', str(e))
    sys.exit(1)
" || echo -e "${YELLOW}⚠️  Python test failed but continuing${NC}"
