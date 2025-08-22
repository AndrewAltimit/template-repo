#!/bin/bash
# Container entrypoint for OpenCode with proxy support
# This script starts the proxy services and configures OpenCode to use them

set -e

# Configuration from environment variables
USE_PROXY=${USE_PROXY:-true}
MOCK_MODE=${PROXY_MOCK_MODE:-true}
COMPANY_API_BASE=${COMPANY_API_BASE:-http://localhost:8050}
COMPANY_API_TOKEN=${COMPANY_API_TOKEN:-test-secret-token-123}
LOG_DIR=${LOG_DIR:-/tmp}

# Colors for output
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; MAGENTA=''; NC=''
fi

echo -e "${MAGENTA}🎭 OpenCode Container with Proxy Support${NC}"
echo "=========================================="
echo ""

# Function to check if a service is running
check_service() {
    local port=$1
    local service_name=$2

    if nc -z localhost $port 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $service_name already running on port $port"
        return 0
    else
        return 1
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=0

    echo -n "Waiting for $service_name"
    while [ $attempt -lt $max_attempts ]; do
        if nc -z localhost $port 2>/dev/null; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    echo -e " ${RED}✗${NC}"
    echo "Failed to start $service_name after $max_attempts seconds"
    return 1
}

if [ "$USE_PROXY" = "true" ]; then
    echo -e "${BLUE}Starting proxy services...${NC}"
    echo ""

    # Start Mock Company API (if in mock mode)
    if [ "$MOCK_MODE" = "true" ]; then
        if ! check_service 8050 "Mock Company API"; then
            echo "Starting Mock Company API..."
            python3 /workspace/automation/proxy/mock_company_api.py > $LOG_DIR/mock_api.log 2>&1 &
            MOCK_PID=$!

            if ! wait_for_service 8050 "Mock Company API"; then
                echo -e "${RED}Failed to start Mock Company API${NC}"
                cat $LOG_DIR/mock_api.log
                exit 1
            fi
        fi
    else
        echo -e "${YELLOW}Mock mode disabled - using real company API at $COMPANY_API_BASE${NC}"
    fi

    # Start API Translation Wrapper
    if ! check_service 8052 "API Translation Wrapper"; then
        echo "Starting API Translation Wrapper..."

        # Export environment variables for the wrapper
        export WRAPPER_MOCK_MODE=$MOCK_MODE
        export COMPANY_API_BASE=$COMPANY_API_BASE
        export COMPANY_API_TOKEN=$COMPANY_API_TOKEN

        python3 /workspace/automation/proxy/api_translation_wrapper.py > $LOG_DIR/wrapper.log 2>&1 &
        WRAPPER_PID=$!

        if ! wait_for_service 8052 "API Translation Wrapper"; then
            echo -e "${RED}Failed to start API Translation Wrapper${NC}"
            cat $LOG_DIR/wrapper.log
            exit 1
        fi
    fi

    echo ""
    echo -e "${GREEN}✓ Proxy services started${NC}"
    echo ""

    # Test the proxy
    echo "Testing proxy endpoint..."
    RESPONSE=$(curl -s -X POST http://localhost:8052/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model": "anthropic/claude-3.5-sonnet", "messages": [{"role": "user", "content": "Test"}]}' \
        | python3 -c "import sys, json; print(json.load(sys.stdin)['choices'][0]['message']['content'])" 2>/dev/null || echo "FAILED")

    if [ "$RESPONSE" = "Hatsune Miku" ]; then
        echo -e "${GREEN}✓ Proxy test successful: '$RESPONSE'${NC}"
    else
        echo -e "${RED}✗ Proxy test failed. Response: '$RESPONSE'${NC}"
        echo "Checking logs..."
        tail -n 20 $LOG_DIR/wrapper.log
        exit 1
    fi

    echo ""
    echo -e "${BLUE}Configuring OpenCode to use proxy...${NC}"

    # Back to hijacking OpenRouter but with modified configuration
    # OpenCode doesn't properly support custom providers
    mkdir -p ~/.config/opencode
    cat > ~/.config/opencode/.opencode.json << EOF
{
  "provider": {
    "openrouter": {
      "options": {
        "baseURL": "http://localhost:8052/v1",
        "apiKey": "test-key"
      }
    }
  },
  "model": "openrouter/anthropic/claude-3.5-sonnet"
}
EOF

    # Also create working directory config
    cat > /workspace/opencode.json << EOF
{
  "provider": {
    "openrouter": {
      "options": {
        "baseURL": "http://localhost:8052/v1"
      }
    }
  },
  "model": "openrouter/anthropic/claude-3.5-sonnet"
}
EOF

    # Set fake OpenRouter API key (our proxy doesn't actually use it)
    export OPENROUTER_API_KEY=test-key-for-proxy

    echo -e "${GREEN}✓ OpenCode configured to use proxy${NC}"
    echo ""
    echo "================================"
    echo -e "${MAGENTA}🎭 PROXY MODE ACTIVE${NC}"
    echo "All responses = 'Hatsune Miku'"
    echo "================================"
    echo ""
    echo "Usage:"
    echo "  Interactive:  opencode"
    echo "  Single query: echo 'Your question' | opencode run"
    echo ""
    echo "Logs:"
    echo "  Mock API: $LOG_DIR/mock_api.log"
    echo "  Wrapper:  $LOG_DIR/wrapper.log"
    echo ""
else
    echo -e "${YELLOW}Proxy disabled - using standard OpenRouter${NC}"
    echo "Set USE_PROXY=true to enable proxy mode"
    echo ""
fi

# If a command was provided, execute it
if [ $# -gt 0 ]; then
    echo "Executing: $@"
    exec "$@"
else
    # Start OpenCode with our limited model display
    clear
    cat << 'BANNER'
╔════════════════════════════════════════════════════╗
║          🎭 COMPANY PROXY MODE ACTIVE              ║
╠════════════════════════════════════════════════════╣
║ ⚠️  IMPORTANT: OpenCode will show many models but   ║
║    ONLY THESE 3 WORK through our proxy:           ║
║                                                     ║
║ ✅ openrouter/anthropic/claude-3.5-sonnet          ║
║ ✅ openrouter/anthropic/claude-3-opus              ║
║ ✅ openrouter/openai/gpt-4                         ║
║                                                     ║
║ ❌ All other models will fail or return errors     ║
╠════════════════════════════════════════════════════╣
║ Mock Mode Active: All responses = "Hatsune Miku"   ║
║ This confirms the proxy is working correctly       ║
╚════════════════════════════════════════════════════╝

Starting OpenCode with Company Proxy...

BANNER

    # Launch OpenCode with OpenRouter model (hijacked to our proxy)
    exec opencode -m "openrouter/anthropic/claude-3.5-sonnet"
fi
