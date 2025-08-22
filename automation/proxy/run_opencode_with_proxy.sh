#!/bin/bash
# run_opencode_with_proxy.sh - Run OpenCode in container with proxy support
# This script automatically detects if proxy mode is enabled and configures accordingly

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/configs"
CURRENT_CONFIG_FILE="$CONFIG_DIR/.current_config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🐳 Starting OpenCode CLI in Container"

# Get current configuration mode
if [ -f "$CURRENT_CONFIG_FILE" ]; then
    CURRENT_MODE=$(cat "$CURRENT_CONFIG_FILE")
else
    CURRENT_MODE="openrouter"
fi

echo -e "${BLUE}Mode: ${GREEN}$CURRENT_MODE${NC}"

# Configure based on mode
if [ "$CURRENT_MODE" = "proxy" ]; then
    echo -e "${GREEN}✅ Using Company Proxy (Mock Mode)${NC}"
    echo "📡 All responses will be: 'Hatsune Miku'"

    # Check if proxy services are running
    if ! curl -s http://localhost:8052/health > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Translation wrapper not running!${NC}"
        echo "Starting services..."
        $SCRIPT_DIR/toggle_opencode.sh start
        sleep 3
    fi

    # Set proxy configuration
    OPENCODE_CONFIG="/workspace/automation/proxy/opencode-custom.jsonc"
    COMPANY_API_KEY="mock-api-key-for-testing"

    # We don't need OPENROUTER_API_KEY in proxy mode
    OPENROUTER_API_KEY="dummy-not-used-in-proxy-mode"
else
    echo -e "${GREEN}✅ Using OpenRouter (Real AI)${NC}"

    # Auto-load .env file if it exists and OPENROUTER_API_KEY is not set
    if [ -z "$OPENROUTER_API_KEY" ] && [ -f ".env" ]; then
        echo "📄 Loading environment from .env file..."
        set -a  # Enable auto-export
        source .env
        set +a  # Disable auto-export
    fi

    # Check for API key
    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo -e "${RED}❌ OPENROUTER_API_KEY not set. Please export your API key:${NC}"
        echo "   export OPENROUTER_API_KEY='your-key-here'"
        exit 1
    fi

    echo "✅ Using OpenRouter API key: ****${OPENROUTER_API_KEY: -4}"

    # Use default or custom OpenRouter config
    OPENCODE_CONFIG="/workspace/automation/proxy/configs/opencode-openrouter.jsonc"
    COMPANY_API_KEY=""
fi

# Default model if not set
if [ -z "$OPENCODE_MODEL" ]; then
    export OPENCODE_MODEL="qwen/qwen-2.5-coder-32b-instruct"
fi
echo "🤖 Using model: $OPENCODE_MODEL"

# Parse command line arguments
MODE="interactive"
QUERY=""
CONTEXT=""
PLAN_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
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
        --toggle)
            # Quick toggle between modes
            if [ "$CURRENT_MODE" = "proxy" ]; then
                echo "Switching to OpenRouter mode..."
                $SCRIPT_DIR/toggle_opencode.sh openrouter
            else
                echo "Switching to Proxy mode..."
                $SCRIPT_DIR/toggle_opencode.sh proxy
            fi
            exit 0
            ;;
        --status)
            $SCRIPT_DIR/toggle_opencode.sh status
            exit 0
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -q, --query <prompt>    Single query mode with specified prompt"
            echo "  -c, --context <file>    Add context from file"
            echo "  -p, --plan              Enable plan mode for multi-step tasks"
            echo "  --toggle                Toggle between proxy and OpenRouter modes"
            echo "  --status                Show current configuration status"
            echo "  -h, --help              Show this help message"
            echo ""
            echo -e "Current Mode: ${GREEN}$CURRENT_MODE${NC}"
            echo ""
            echo "Interactive Mode (default):"
            echo "  Start an interactive session with OpenCode in a container"
            echo ""
            echo "Single Query Mode:"
            echo "  $0 -q 'Write a Python function to calculate fibonacci'"
            echo ""
            echo "With Context:"
            echo "  $0 -q 'Refactor this code' -c existing_code.py"
            echo ""
            echo "Plan Mode:"
            echo "  $0 -q 'Build a REST API with authentication' -p"
            echo ""
            echo "Toggle Mode:"
            echo "  $0 --toggle  # Switch between proxy and OpenRouter"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Build Docker command
DOCKER_CMD="docker-compose run --rm"

# Add network option to connect to proxy services
DOCKER_CMD="$DOCKER_CMD --network template-repo_mcp-network"

# Set environment variables based on mode
DOCKER_CMD="$DOCKER_CMD -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY"
DOCKER_CMD="$DOCKER_CMD -e OPENCODE_CONFIG=$OPENCODE_CONFIG"
DOCKER_CMD="$DOCKER_CMD -e OPENCODE_MODEL=$OPENCODE_MODEL"

if [ -n "$COMPANY_API_KEY" ]; then
    DOCKER_CMD="$DOCKER_CMD -e COMPANY_API_KEY=$COMPANY_API_KEY"
fi

# Mount context file if provided
if [ -n "$CONTEXT" ] && [ -f "$CONTEXT" ]; then
    CONTEXT_DIR=$(dirname "$(realpath "$CONTEXT")")
    CONTEXT_FILE=$(basename "$CONTEXT")
    DOCKER_CMD="$DOCKER_CMD -v $CONTEXT_DIR:/workspace"
    CONTEXT_PATH="/workspace/$CONTEXT_FILE"
else
    CONTEXT_PATH=""
fi

# Show what we're about to do
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$CURRENT_MODE" = "proxy" ]; then
    echo -e "${BLUE}Company Proxy Mode - Mock Responses${NC}"
    echo "Expected: All answers = 'Hatsune Miku'"
    echo "Config: $OPENCODE_CONFIG"
    echo "Endpoint: http://api-translation-wrapper:8052/v1"
else
    echo -e "${BLUE}OpenRouter Mode - Real AI Responses${NC}"
    echo "Config: Default OpenCode configuration"
    echo "Endpoint: https://openrouter.ai/api/v1"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Execute based on mode
if [ "$MODE" = "single" ]; then
    echo "📝 Running single query in container..."
    echo ""

    # Build command for container
    CMD="opencode run"

    if [ -n "$QUERY" ]; then
        CMD="$CMD -q '$QUERY'"
    fi

    if [ -n "$CONTEXT_PATH" ]; then
        echo "📄 Including context from: $CONTEXT"
        CMD="$CMD -c '$CONTEXT_PATH'"
    fi

    if [ "$PLAN_MODE" = true ]; then
        CMD="$CMD --plan"
    fi

    # Execute in container
    $DOCKER_CMD openrouter-agents sh -c "$CMD"

    # Show reminder if in proxy mode
    if [ "$CURRENT_MODE" = "proxy" ]; then
        echo ""
        echo -e "${YELLOW}Note: You're in proxy mode. The response should be 'Hatsune Miku'${NC}"
        echo -e "${YELLOW}To use real AI, run: $0 --toggle${NC}"
    fi
else
    echo "🔄 Starting interactive session in container..."
    echo "💡 Tips:"
    echo "   - Use 'clear' to clear conversation history"
    echo "   - Use 'status' to see current configuration"
    echo "   - Use 'exit' or Ctrl+C to quit"
    if [ "$CURRENT_MODE" = "proxy" ]; then
        echo -e "   - ${YELLOW}Proxy Mode: All responses will be 'Hatsune Miku'${NC}"
    fi
    echo ""

    # Start interactive session in container
    $DOCKER_CMD -it openrouter-agents opencode
fi
