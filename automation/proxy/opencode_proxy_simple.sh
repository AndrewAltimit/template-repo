#!/bin/bash
# opencode_proxy_simple.sh - Simple OpenCode with proxy in container
# Everything runs inside the container for maximum portability

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
USE_PROXY=${USE_PROXY:-true}

echo -e "${CYAN}🐳 OpenCode with Integrated Proxy${NC}"
echo "=================================="

# Parse arguments
QUERY=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-proxy)
            USE_PROXY=false
            shift
            ;;
        -q|--query)
            QUERY="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -q, --query <text>  Run a single query"
            echo "  --no-proxy          Use OpenRouter instead of proxy"
            echo "  -h, --help          Show this help"
            echo ""
            echo "Examples:"
            echo "  # Test with proxy (returns 'Hatsune Miku')"
            echo "  $0 -q 'What is 2+2?'"
            echo ""
            echo "  # Use real OpenRouter"
            echo "  $0 --no-proxy -q 'What is 2+2?'"
            exit 0
            ;;
        *)
            QUERY="$1"
            shift
            ;;
    esac
done

# Display mode
if [ "$USE_PROXY" = "true" ]; then
    echo -e "${GREEN}Mode: Proxy (Mock - returns 'Hatsune Miku')${NC}"
else
    echo -e "${GREEN}Mode: OpenRouter (Real AI)${NC}"
    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo -e "${YELLOW}Warning: OPENROUTER_API_KEY not set${NC}"
    fi
fi
echo "=================================="
echo ""

# Create container script
cat > /tmp/opencode_container.sh << 'SCRIPT'
#!/bin/bash
set -e

# Install dependencies
echo "📦 Setting up environment..."
pip3 install --quiet flask flask-cors requests 2>/dev/null || true
npm list -g @sst/opencode > /dev/null 2>&1 || npm install -g @sst/opencode > /dev/null 2>&1

if [ "$USE_PROXY" = "true" ]; then
    echo "🚀 Starting proxy services..."

    # Start mock API
    python3 /app/automation/proxy/mock_company_api.py > /tmp/mock.log 2>&1 &

    # Start translation wrapper
    python3 /app/automation/proxy/api_translation_wrapper.py > /tmp/wrapper.log 2>&1 &

    # Wait for services
    sleep 3

    # Create OpenCode config for proxy
    cat > /tmp/opencode-proxy.jsonc << 'CONFIG'
{
  "$schema": "https://opencode.ai/config-schema.json",
  "provider": {
    "company-ai": {
      "name": "Company AI",
      "api": "http://localhost:8052/v1",
      "env": ["COMPANY_API_KEY"],
      "models": {
        "claude-3.5-sonnet": {
          "name": "Claude 3.5 Sonnet",
          "release_date": "2024-06-20",
          "attachment": true,
          "temperature": true,
          "tool_call": true,
          "cost": {"input": 3, "output": 15},
          "limit": {"context": 200000, "output": 8192}
        }
      },
      "options": {"apiKey": "test-key"}
    }
  },
  "disabled_providers": ["openrouter", "anthropic", "openai"],
  "model": "company-ai/claude-3.5-sonnet"
}
CONFIG

    export OPENCODE_CONFIG=/tmp/opencode-proxy.jsonc
    export COMPANY_API_KEY=test-key
fi

# Run OpenCode
if [ -n "$QUERY" ]; then
    echo "📝 Running query: $QUERY"
    echo ""

    # Test the proxy first
    echo "Testing proxy endpoint..."
    curl -s -X POST http://localhost:8052/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"claude-3.5-sonnet\", \"messages\": [{\"role\": \"user\", \"content\": \"$QUERY\"}]}" \
        | python3 -c "import sys, json; d=json.load(sys.stdin); print('Proxy response:', d.get('choices',[{}])[0].get('message',{}).get('content','ERROR'))" || echo "Proxy test failed"

    echo ""
    echo "Running OpenCode (this may take a moment)..."
    timeout 30 opencode run -q "$QUERY" 2>&1 || echo "OpenCode command timed out or failed"
else
    echo "🔄 Starting interactive session..."
    echo "Type 'exit' to quit"
    echo ""
    opencode
fi
SCRIPT

chmod +x /tmp/opencode_container.sh

# Run in container
docker-compose run --rm \
    -e USE_PROXY=$USE_PROXY \
    -e QUERY="$QUERY" \
    -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    -v /tmp/opencode_container.sh:/tmp/run.sh \
    python-ci \
    bash /tmp/run.sh

# Cleanup
rm -f /tmp/opencode_container.sh

if [ "$USE_PROXY" = "true" ] && [ -n "$QUERY" ]; then
    echo ""
    echo -e "${YELLOW}Note: Response should be 'Hatsune Miku' in proxy mode${NC}"
fi
