#!/bin/bash
# run_opencode_container.sh - Run OpenCode CLI in Docker container

set -e

echo "🐳 Starting OpenCode CLI in Container"

# Check if required Docker images exist, build if not
check_and_build_images() {
    local images_missing=false

    # Check for mcp-opencode image
    if ! docker images | grep -q "template-repo-mcp-opencode"; then
        echo "📦 OpenCode MCP image not found, building..."
        images_missing=true
    fi

    # Check for mcp-crush image
    if ! docker images | grep -q "template-repo-mcp-crush"; then
        echo "📦 Crush MCP image not found, building..."
        images_missing=true
    fi

    # Check for openrouter-agents image
    if ! docker images | grep -q "template-repo-openrouter-agents"; then
        echo "📦 OpenRouter agents image not found, building..."
        images_missing=true
    fi

    # Build missing images
    if [ "$images_missing" = true ]; then
        echo "🔨 Building required Docker images..."
        echo "This may take a few minutes on first run..."

        # Build base MCP images first (required by openrouter-agents)
        echo "Building MCP OpenCode and Crush images..."
        docker compose build mcp-opencode mcp-crush

        # Build the openrouter-agents image with local image references
        # Using docker build directly to avoid Docker Hub lookup issues
        echo "Building OpenRouter agents image..."
        docker build -f docker/openrouter-agents.Dockerfile \
            --build-arg OPENCODE_IMAGE=template-repo-mcp-opencode:latest \
            --build-arg CRUSH_IMAGE=template-repo-mcp-crush:latest \
            -t template-repo-openrouter-agents:latest .

        echo "✅ Docker images built successfully!"
        echo ""
    fi
}

# Build images if needed
check_and_build_images

# Auto-load .env file if it exists
if [ -f ".env" ]; then
    echo "📄 Loading environment from .env file..."
    set -a  # Enable auto-export
    source .env
    set +a  # Disable auto-export
fi

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ OPENROUTER_API_KEY not set."
    echo ""
    echo "Please either:"
    echo "1. Add it to your .env file:"
    echo "   echo \"OPENROUTER_API_KEY='your-key-here'\" >> .env"
    echo "2. Or export it directly:"
    echo "   export OPENROUTER_API_KEY='your-key-here'"
    echo ""
    echo "Get your API key at: https://openrouter.ai/keys"
    exit 1
fi

echo "✅ Using OpenRouter API key: ****${OPENROUTER_API_KEY: -4}"
echo "   Key length: ${#OPENROUTER_API_KEY} characters"

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

# Export for docker compose to pick up
export OPENROUTER_API_KEY
export OPENCODE_MODEL

# Setup context file if provided
if [ -n "$CONTEXT" ] && [ -f "$CONTEXT" ]; then
    CONTEXT_DIR=$(dirname "$(realpath "$CONTEXT")")
    CONTEXT_FILE=$(basename "$CONTEXT")
    CONTEXT_PATH="/workspace/$CONTEXT_FILE"
    VOLUME_MOUNT="-v $CONTEXT_DIR:/workspace"
else
    CONTEXT_PATH=""
    VOLUME_MOUNT=""
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
    if [ -n "$VOLUME_MOUNT" ]; then
        # shellcheck disable=SC2086
        # VOLUME_MOUNT contains both flag and argument (e.g., "-v /path:/path")
        docker compose run --rm \
            -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
            -e OPENCODE_MODEL="$OPENCODE_MODEL" \
            $VOLUME_MOUNT \
            openrouter-agents sh -c "$CMD"
    else
        docker compose run --rm \
            -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
            -e OPENCODE_MODEL="$OPENCODE_MODEL" \
            openrouter-agents sh -c "$CMD"
    fi
else
    echo "🔄 Starting interactive session in container..."
    echo "💡 Tips:"
    echo "   - Use 'clear' to clear conversation history"
    echo "   - Use 'status' to see current configuration"
    echo "   - Use 'exit' or Ctrl+C to quit"
    echo ""

    # Start interactive session in container
    docker compose run --rm -it \
        -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
        -e OPENCODE_MODEL="$OPENCODE_MODEL" \
        openrouter-agents opencode
fi
