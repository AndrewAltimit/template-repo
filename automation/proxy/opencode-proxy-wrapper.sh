#!/bin/bash
# OpenCode wrapper that intercepts model listing and shows only proxy models
# This wrapper starts the proxy and then runs OpenCode with the proxy configuration

set -e

# Configuration
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
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; NC=''
fi

# Function to check if a service is running
check_service() {
    local port=$1
    local service_name=$2

    if nc -z localhost "$port" 2>/dev/null; then
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
        if nc -z localhost "$port" 2>/dev/null; then
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

# Clear screen for clean display
clear

# Display banner
cat << 'BANNER'
╔════════════════════════════════════════════════════╗
║          🎭 COMPANY PROXY MODE ACTIVE              ║
╠════════════════════════════════════════════════════╣
║ ⚠️  IMPORTANT: Only these 3 models work:            ║
║                                                     ║
║ ✅ openrouter/anthropic/claude-3.5-sonnet          ║
║ ✅ openrouter/anthropic/claude-3-opus              ║
║ ✅ openrouter/openai/gpt-4                         ║
║                                                     ║
║ ❌ All other models will fall back to Claude 3.5   ║
╠════════════════════════════════════════════════════╣
║ Mock Mode Active: All responses = "Hatsune Miku"   ║
║ This confirms the proxy is working correctly       ║
╚════════════════════════════════════════════════════╝

BANNER

if [ "$USE_PROXY" = "true" ]; then
    echo -e "${BLUE}Starting proxy services...${NC}"
    echo ""

    # Start Mock Company API (if in mock mode and not already running)
    if [ "$MOCK_MODE" = "true" ]; then
        if ! check_service 8050 "Mock Company API"; then
            echo "Starting Mock Company API..."
            python3 /workspace/automation/proxy/mock_company_api.py > "$LOG_DIR"/mock_api.log 2>&1 &
            MOCK_PID=$!

            if ! wait_for_service 8050 "Mock Company API"; then
                echo -e "${RED}Failed to start Mock Company API${NC}"
                cat "$LOG_DIR"/mock_api.log
                exit 1
            fi
        else
            echo -e "${GREEN}✓${NC} Mock Company API already running on port 8050"
        fi
    fi

    # Start API Translation Wrapper (if not already running)
    if ! check_service 8052 "API Translation Wrapper"; then
        echo "Starting API Translation Wrapper..."

        # Export environment variables for the wrapper
        export WRAPPER_MOCK_MODE=$MOCK_MODE
        export COMPANY_API_BASE=$COMPANY_API_BASE
        export COMPANY_API_TOKEN=$COMPANY_API_TOKEN

        python3 /workspace/automation/proxy/api_translation_wrapper.py > "$LOG_DIR"/wrapper.log 2>&1 &
        WRAPPER_PID=$!

        if ! wait_for_service 8052 "API Translation Wrapper"; then
            echo -e "${RED}Failed to start API Translation Wrapper${NC}"
            cat "$LOG_DIR"/wrapper.log
            exit 1
        fi
    else
        echo -e "${GREEN}✓${NC} API Translation Wrapper already running on port 8052"
    fi

    echo ""
    echo -e "${GREEN}✓ Proxy services ready${NC}"
    echo ""

    # Configure OpenCode to use proxy
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

    # Set fake OpenRouter API key (our proxy doesn't actually use it)
    export OPENROUTER_API_KEY=test-key-for-proxy

    echo -e "${CYAN}Press Enter to start OpenCode with proxy...${NC}"
    read -r

    # Launch OpenCode with our default model
    # Use the real OpenCode binary to avoid infinite loop
    exec /usr/local/bin/opencode.real -m "openrouter/anthropic/claude-3.5-sonnet" "$@"
else
    echo -e "${YELLOW}Proxy disabled - using standard OpenRouter${NC}"
    exec /usr/local/bin/opencode.real "$@"
fi
