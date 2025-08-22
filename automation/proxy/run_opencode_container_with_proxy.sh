#!/bin/bash
# run_opencode_container_with_proxy.sh - Run OpenCode in container with integrated proxy
# The proxy services run INSIDE the container for simplicity

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
USE_PROXY=${USE_PROXY:-true}
PROXY_MOCK_MODE=${PROXY_MOCK_MODE:-true}

echo -e "${CYAN}🐳 OpenCode Container with Integrated Proxy${NC}"
echo "============================================="

# Parse command line arguments
MODE="interactive"
QUERY=""
CONTEXT=""
PLAN_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-proxy)
            USE_PROXY=false
            shift
            ;;
        --real-api)
            PROXY_MOCK_MODE=false
            shift
            ;;
        -q|--query)
            QUERY="$2"
            MODE="single"
            shift 2
            ;;
        -c|--context)
            CONTEXT="$2"
            shift 2
            ;;
        -p|--plan)
            PLAN_MODE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --no-proxy              Use OpenRouter instead of proxy"
            echo "  --real-api              Use real company API (not mock)"
            echo "  -q, --query <prompt>    Single query mode"
            echo "  -c, --context <file>    Add context from file"
            echo "  -p, --plan              Enable plan mode"
            echo "  -h, --help              Show this help"
            echo ""
            echo "Examples:"
            echo "  # Use proxy with mock (returns 'Hatsune Miku')"
            echo "  $0 -q 'Hello'"
            echo ""
            echo "  # Use OpenRouter (real AI)"
            echo "  $0 --no-proxy -q 'Hello'"
            echo ""
            echo "  # Use proxy with real company API"
            echo "  $0 --real-api -q 'Hello'"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Display mode
if [ "$USE_PROXY" = "true" ]; then
    if [ "$PROXY_MOCK_MODE" = "true" ]; then
        echo -e "${GREEN}Mode: Company Proxy (Mock)${NC}"
        echo "Expected: All responses = 'Hatsune Miku'"
    else
        echo -e "${GREEN}Mode: Company Proxy (Real API)${NC}"
        echo "Using real company API endpoint"
    fi
else
    echo -e "${GREEN}Mode: OpenRouter (Direct)${NC}"
    echo "Using OpenRouter API directly"

    # Check for OpenRouter API key
    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo -e "${RED}❌ OPENROUTER_API_KEY not set${NC}"
        echo "Please export: export OPENROUTER_API_KEY='your-key'"
        exit 1
    fi
fi

echo "============================================="
echo ""

# Create a wrapper script that will run inside the container
cat > /tmp/opencode_container_wrapper.sh << 'EOF'
#!/bin/bash
set -e

echo "🔧 Setting up container environment..."

# Install required Python packages if not present
if ! python -c "import flask" 2>/dev/null; then
    echo "📦 Installing required packages..."
    pip install --quiet flask flask-cors requests
fi

# Check if we should use proxy
if [ "$USE_PROXY" = "true" ]; then
    echo "🚀 Starting proxy services..."

    # Start proxy services
    export PROXY_MOCK_MODE=$PROXY_MOCK_MODE
    export COMPANY_API_BASE=${COMPANY_API_BASE:-http://localhost:8050}
    export COMPANY_API_TOKEN=${COMPANY_API_TOKEN:-test-secret-token-123}

    /workspace/automation/proxy/start_proxy_services.sh

    # Wait for services to be ready
    sleep 2

    # Configure OpenCode to use proxy
    export OPENCODE_CONFIG=/workspace/automation/proxy/opencode-custom-local.jsonc
    export COMPANY_API_KEY=mock-api-key-for-testing

    # Create local config that points to localhost (inside container)
    cat > /workspace/automation/proxy/opencode-custom-local.jsonc << 'CONFIG'
{
  "$schema": "https://opencode.ai/config-schema.json",
  "provider": {
    "company-ai": {
      "name": "Company AI Gateway",
      "api": "http://localhost:8052/v1",
      "env": ["COMPANY_API_KEY"],
      "models": {
        "claude-3.5-sonnet": {
          "name": "Claude 3.5 Sonnet (Company)",
          "release_date": "2024-06-20",
          "attachment": true,
          "reasoning": false,
          "temperature": true,
          "tool_call": true,
          "cost": { "input": 3, "output": 15, "cache_read": 0.3, "cache_write": 3.75 },
          "limit": { "context": 200000, "output": 8192 }
        }
      },
      "options": {
        "apiKey": "mock-api-key-for-testing"
      }
    }
  },
  "disabled_providers": ["openrouter", "anthropic", "openai"],
  "model": "company-ai/claude-3.5-sonnet"
}
CONFIG

    echo "✅ Proxy services ready"
    echo ""
fi

# Run OpenCode based on mode
if [ "$MODE" = "single" ]; then
    echo "📝 Running query: $QUERY"
    opencode run -q "$QUERY"
else
    echo "🔄 Starting interactive session..."
    echo "💡 Type 'exit' to quit"
    echo ""
    opencode
fi
EOF

chmod +x /tmp/opencode_container_wrapper.sh

# Build docker-compose command
DOCKER_CMD="docker-compose run --rm"
DOCKER_CMD="$DOCKER_CMD -e USE_PROXY=$USE_PROXY"
DOCKER_CMD="$DOCKER_CMD -e PROXY_MOCK_MODE=$PROXY_MOCK_MODE"
DOCKER_CMD="$DOCKER_CMD -e MODE=$MODE"
DOCKER_CMD="$DOCKER_CMD -e QUERY=\"$QUERY\""

if [ "$USE_PROXY" = "false" ]; then
    DOCKER_CMD="$DOCKER_CMD -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY"
fi

# Add real company API credentials if needed
if [ "$PROXY_MOCK_MODE" = "false" ] && [ "$USE_PROXY" = "true" ]; then
    DOCKER_CMD="$DOCKER_CMD -e COMPANY_API_BASE=${COMPANY_API_BASE:-https://your-company-api.com}"
    DOCKER_CMD="$DOCKER_CMD -e COMPANY_API_TOKEN=${COMPANY_API_TOKEN:-your-token}"
fi

# Mount the wrapper script
DOCKER_CMD="$DOCKER_CMD -v /tmp/opencode_container_wrapper.sh:/tmp/wrapper.sh"

# Make it interactive if needed
if [ "$MODE" = "interactive" ]; then
    DOCKER_CMD="$DOCKER_CMD -it"
fi

# Run the container
echo "🐳 Starting container..."
$DOCKER_CMD openrouter-agents bash /tmp/wrapper.sh

# Cleanup
rm -f /tmp/opencode_container_wrapper.sh

if [ "$USE_PROXY" = "true" ] && [ "$MODE" = "single" ]; then
    echo ""
    if [ "$PROXY_MOCK_MODE" = "true" ]; then
        echo -e "${YELLOW}Note: You used proxy mode. The response should be 'Hatsune Miku'${NC}"
        echo -e "To use real AI, run with: $0 --no-proxy -q 'Your query'${NC}"
    fi
fi
