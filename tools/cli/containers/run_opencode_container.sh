#!/bin/bash
# run_opencode_container.sh - Run OpenCode CLI in Docker container

set -e

echo "🐳 Starting OpenCode CLI in Container"

# Auto-load .env file if it exists and OPENROUTER_API_KEY is not set
if [ -z "$OPENROUTER_API_KEY" ] && [ -f ".env" ]; then
    echo "📄 Loading environment from .env file..."
    set -a  # Enable auto-export
    source .env
    set +a  # Disable auto-export
fi

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ OPENROUTER_API_KEY not set. Please export your API key:"
    echo "   export OPENROUTER_API_KEY='your-key-here'"
    exit 1
fi

echo "✅ Using OpenRouter API key: ****${OPENROUTER_API_KEY: -4}"

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
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -q, --query <prompt>    Single query mode with specified prompt"
            echo "  -c, --context <file>    Add context from file"
            echo "  -p, --plan              Enable plan mode for multi-step tasks"
            echo "  -h, --help              Show this help message"
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
DOCKER_CMD="$DOCKER_CMD -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY"
DOCKER_CMD="$DOCKER_CMD -e OPENCODE_MODEL=$OPENCODE_MODEL"

# Mount context file if provided
if [ -n "$CONTEXT" ] && [ -f "$CONTEXT" ]; then
    CONTEXT_DIR=$(dirname "$(realpath "$CONTEXT")")
    CONTEXT_FILE=$(basename "$CONTEXT")
    DOCKER_CMD="$DOCKER_CMD -v $CONTEXT_DIR:/workspace"
    CONTEXT_PATH="/workspace/$CONTEXT_FILE"
else
    CONTEXT_PATH=""
fi

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
else
    echo "🔄 Starting interactive session in container..."
    echo "💡 Tips:"
    echo "   - Use 'clear' to clear conversation history"
    echo "   - Use 'status' to see current configuration"
    echo "   - Use 'exit' or Ctrl+C to quit"
    echo ""

    # Start interactive session in container
    $DOCKER_CMD -it openrouter-agents opencode
fi
