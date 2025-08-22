#!/bin/bash

# Toggle script for OpenCode between company proxy and real OpenRouter
# Usage: ./toggle_opencode.sh [proxy|openrouter|status]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/configs"
CURRENT_CONFIG_FILE="$CONFIG_DIR/.current_config"

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if services are running
check_services() {
    local mock_api_status="❌ Not running"
    local wrapper_status="❌ Not running"

    if curl -s http://localhost:8050/health > /dev/null 2>&1; then
        mock_api_status="✅ Running on port 8050"
    fi

    if curl -s http://localhost:8052/health > /dev/null 2>&1; then
        wrapper_status="✅ Running on port 8052"
    fi

    echo -e "${BLUE}Service Status:${NC}"
    echo -e "  Mock Company API: $mock_api_status"
    echo -e "  Translation Wrapper: $wrapper_status"
}

# Function to get current configuration
get_current_config() {
    if [ -f "$CURRENT_CONFIG_FILE" ]; then
        cat "$CURRENT_CONFIG_FILE"
    else
        echo "none"
    fi
}

# Function to set configuration
set_config() {
    local mode=$1
    echo "$mode" > "$CURRENT_CONFIG_FILE"
}

# Function to start proxy services
start_proxy_services() {
    echo -e "${YELLOW}Starting proxy services...${NC}"

    # Check if already running
    if ! curl -s http://localhost:8050/health > /dev/null 2>&1; then
        echo "Starting Mock Company API..."
        python "$SCRIPT_DIR/mock_company_api.py" > /tmp/mock_api.log 2>&1 &
        sleep 2
    else
        echo "Mock Company API already running"
    fi

    if ! curl -s http://localhost:8052/health > /dev/null 2>&1; then
        echo "Starting Translation Wrapper..."
        python "$SCRIPT_DIR/api_translation_wrapper.py" > /tmp/wrapper.log 2>&1 &
        sleep 2
    else
        echo "Translation Wrapper already running"
    fi

    check_services
}

# Function to stop proxy services
stop_proxy_services() {
    echo -e "${YELLOW}Stopping proxy services...${NC}"

    # Find and kill processes
    pkill -f "mock_company_api.py" 2>/dev/null
    pkill -f "api_translation_wrapper.py" 2>/dev/null

    sleep 1
    echo "Services stopped"
}

# Function to switch to proxy mode
switch_to_proxy() {
    echo -e "${GREEN}Switching to Company Proxy mode...${NC}"

    # Start services if not running
    start_proxy_services

    # Set environment variables
    export OPENCODE_CONFIG="$SCRIPT_DIR/opencode-custom.jsonc"
    export COMPANY_API_KEY="mock-api-key-for-testing"

    # Save configuration
    set_config "proxy"

    echo -e "${GREEN}✅ Switched to Company Proxy mode${NC}"
    echo
    echo "Configuration file: $SCRIPT_DIR/opencode-custom.jsonc"
    echo "API endpoint: http://localhost:8052/v1"
    echo
    echo "Test with:"
    echo "  opencode run -q 'Hello, who are you?'"
    echo
    echo "Expected response: 'Hatsune Miku'"
}

# Function to switch to OpenRouter mode
switch_to_openrouter() {
    echo -e "${GREEN}Switching to OpenRouter mode...${NC}"

    # Stop proxy services
    stop_proxy_services

    # Unset custom config
    unset OPENCODE_CONFIG
    unset COMPANY_API_KEY

    # Check for OpenRouter API key
    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo -e "${YELLOW}Warning: OPENROUTER_API_KEY not set${NC}"
        echo "Please set: export OPENROUTER_API_KEY=your-key-here"
    fi

    # Save configuration
    set_config "openrouter"

    echo -e "${GREEN}✅ Switched to OpenRouter mode${NC}"
    echo
    echo "Using default OpenCode configuration"
    echo "API endpoint: https://openrouter.ai/api/v1"
    echo
    echo "Test with:"
    echo "  opencode run -q 'Hello, who are you?'"
}

# Function to show status
show_status() {
    local current=$(get_current_config)

    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}  OpenCode Configuration Status${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo

    if [ "$current" == "proxy" ]; then
        echo -e "Current Mode: ${GREEN}Company Proxy${NC}"
        echo "Config File: $SCRIPT_DIR/opencode-custom.jsonc"
        echo "API Endpoint: http://localhost:8052/v1"
    elif [ "$current" == "openrouter" ]; then
        echo -e "Current Mode: ${GREEN}OpenRouter${NC}"
        echo "Config File: Default OpenCode config"
        echo "API Endpoint: https://openrouter.ai/api/v1"
    else
        echo -e "Current Mode: ${YELLOW}Not configured${NC}"
    fi

    echo
    check_services
    echo

    # Check environment variables
    echo -e "${BLUE}Environment Variables:${NC}"
    if [ -n "$OPENCODE_CONFIG" ]; then
        echo -e "  OPENCODE_CONFIG: ${GREEN}$OPENCODE_CONFIG${NC}"
    else
        echo -e "  OPENCODE_CONFIG: ${YELLOW}Not set (using default)${NC}"
    fi

    if [ -n "$OPENROUTER_API_KEY" ]; then
        echo -e "  OPENROUTER_API_KEY: ${GREEN}Set${NC}"
    else
        echo -e "  OPENROUTER_API_KEY: ${YELLOW}Not set${NC}"
    fi

    if [ -n "$COMPANY_API_KEY" ]; then
        echo -e "  COMPANY_API_KEY: ${GREEN}Set${NC}"
    else
        echo -e "  COMPANY_API_KEY: ${YELLOW}Not set${NC}"
    fi
}

# Function to test current configuration
test_config() {
    echo -e "${BLUE}Testing current configuration...${NC}"
    echo

    local current=$(get_current_config)

    if [ "$current" == "proxy" ]; then
        echo "Testing proxy endpoint..."
        curl -s -X POST http://localhost:8052/v1/chat/completions \
          -H "Content-Type: application/json" \
          -d '{
            "model": "claude-3.5-sonnet",
            "messages": [{"role": "user", "content": "Say your name"}],
            "max_tokens": 10
          }' | python -m json.tool | grep -E '"content"|"error"'
    else
        echo "Testing would require OpenCode CLI"
        echo "Run: opencode run -q 'Hello, who are you?'"
    fi
}

# Main script logic
case "$1" in
    proxy)
        switch_to_proxy
        ;;
    openrouter)
        switch_to_openrouter
        ;;
    status)
        show_status
        ;;
    test)
        test_config
        ;;
    start)
        start_proxy_services
        ;;
    stop)
        stop_proxy_services
        ;;
    *)
        echo "OpenCode Configuration Toggle"
        echo
        echo "Usage: $0 [proxy|openrouter|status|test|start|stop]"
        echo
        echo "Commands:"
        echo "  proxy       - Switch to company proxy mode (mock endpoints)"
        echo "  openrouter  - Switch to OpenRouter mode (real API)"
        echo "  status      - Show current configuration and service status"
        echo "  test        - Test current configuration"
        echo "  start       - Start proxy services only"
        echo "  stop        - Stop proxy services only"
        echo
        echo "Current status:"
        show_status
        ;;
esac

# Export environment variables if in proxy mode
if [ "$(get_current_config)" == "proxy" ]; then
    echo
    echo -e "${YELLOW}Note: Run this script with 'source' to export environment variables:${NC}"
    echo "  source $0 proxy"
fi
