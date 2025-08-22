#!/bin/bash

# Wrapper script to run OpenCode with appropriate configuration
# This script automatically uses the right configuration based on toggle setting

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/configs"
CURRENT_CONFIG_FILE="$CONFIG_DIR/.current_config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get current configuration
if [ -f "$CURRENT_CONFIG_FILE" ]; then
    CURRENT_MODE=$(cat "$CURRENT_CONFIG_FILE")
else
    CURRENT_MODE="openrouter"
fi

# Function to run OpenCode in Docker container
run_opencode_docker() {
    echo -e "${BLUE}Running OpenCode in Docker container...${NC}"

    if [ "$CURRENT_MODE" == "proxy" ]; then
        # Use proxy configuration
        docker-compose run --rm \
            -e OPENCODE_CONFIG=/workspace/automation/proxy/opencode-custom.jsonc \
            -e COMPANY_API_KEY=mock-api-key-for-testing \
            openrouter-agents \
            opencode "$@"
    else
        # Use OpenRouter configuration
        docker-compose run --rm \
            -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
            openrouter-agents \
            opencode "$@"
    fi
}

# Function to run OpenCode locally
run_opencode_local() {
    # Check if opencode is installed
    if ! command -v opencode &> /dev/null; then
        echo -e "${RED}Error: OpenCode CLI not found${NC}"
        echo "Install with: npm install -g @sst/opencode"
        exit 1
    fi

    if [ "$CURRENT_MODE" == "proxy" ]; then
        # Check if proxy services are running
        if ! curl -s http://localhost:8052/health > /dev/null 2>&1; then
            echo -e "${YELLOW}Warning: Translation wrapper not running${NC}"
            echo "Start with: ./automation/proxy/toggle_opencode.sh start"
        fi

        # Use proxy configuration
        export OPENCODE_CONFIG="$SCRIPT_DIR/opencode-custom.jsonc"
        export COMPANY_API_KEY="mock-api-key-for-testing"

        echo -e "${GREEN}Using Company Proxy mode${NC}"
        echo "Config: $OPENCODE_CONFIG"
        echo "Endpoint: http://localhost:8052/v1"
    else
        # Use OpenRouter configuration
        if [ -z "$OPENROUTER_API_KEY" ]; then
            echo -e "${YELLOW}Warning: OPENROUTER_API_KEY not set${NC}"
        fi

        # Optionally use the OpenRouter config file
        export OPENCODE_CONFIG="$CONFIG_DIR/opencode-openrouter.jsonc"

        echo -e "${GREEN}Using OpenRouter mode${NC}"
        echo "Endpoint: https://openrouter.ai/api/v1"
    fi

    echo
    # Run OpenCode with passed arguments
    opencode "$@"
}

# Check if we should use Docker or local
USE_DOCKER=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)
            USE_DOCKER=true
            shift
            ;;
        --help)
            echo "OpenCode Wrapper Script"
            echo
            echo "Usage: $0 [--docker] [opencode-args]"
            echo
            echo "Options:"
            echo "  --docker    Run OpenCode in Docker container"
            echo "  --help      Show this help message"
            echo
            echo "Current mode: $CURRENT_MODE"
            echo
            echo "Examples:"
            echo "  $0 run -q 'Hello, who are you?'"
            echo "  $0 --docker run -q 'What is 2+2?'"
            echo
            echo "Toggle between modes with:"
            echo "  ./automation/proxy/toggle_opencode.sh [proxy|openrouter]"
            exit 0
            ;;
        *)
            break
            ;;
    esac
done

# Show current mode
echo -e "${BLUE}═══════════════════════════════════════${NC}"
if [ "$CURRENT_MODE" == "proxy" ]; then
    echo -e "${BLUE}  OpenCode - Company Proxy Mode${NC}"
    echo -e "${BLUE}  Expected: All responses = 'Hatsune Miku'${NC}"
else
    echo -e "${BLUE}  OpenCode - OpenRouter Mode${NC}"
    echo -e "${BLUE}  Using real AI models${NC}"
fi
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo

# Run OpenCode
if [ "$USE_DOCKER" == true ]; then
    run_opencode_docker "$@"
else
    run_opencode_local "$@"
fi
