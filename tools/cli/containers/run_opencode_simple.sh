#!/bin/bash
# run_opencode_simple.sh - Simple standalone OpenCode container (no docker compose required)
# This script runs OpenCode directly without requiring the full docker compose infrastructure

set -e

echo "🐳 OpenCode CLI - Simple Container Mode"
echo "======================================="

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    # Try to load from .env file
    if [ -f ".env" ]; then
        echo "📄 Loading environment from .env file..."
        set -a
        source .env
        set +a
    fi

    # If still not set, prompt user
    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo ""
        echo "❌ OPENROUTER_API_KEY not set."
        echo ""
        echo "Please enter your OpenRouter API key:"
        echo "(Get one at https://openrouter.ai/keys)"
        read -r -p "API Key: " OPENROUTER_API_KEY

        if [ -z "$OPENROUTER_API_KEY" ]; then
            echo "❌ API key is required to continue."
            exit 1
        fi
    fi
fi

echo "✅ Using OpenRouter API key: ****${OPENROUTER_API_KEY: -4}"

# Default model if not set
if [ -z "$OPENCODE_MODEL" ]; then
    export OPENCODE_MODEL="particle-ai/particle-1"
fi
echo "🤖 Using model: $OPENCODE_MODEL"

# Build simple OpenCode image if it doesn't exist. The tag carries the pinned
# CLI version so bumping OPENCODE_VERSION rebuilds instead of reusing a stale
# image. OpenCode 2.x is published to npm as @opencode/cli (the old
# opencode-ai package only carries the 1.x line).
OPENCODE_VERSION="2.2.1"
IMAGE_NAME="opencode-simple:${OPENCODE_VERSION}"

if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo ""
    echo "📦 Building OpenCode container image..."
    echo "This will take a few minutes on first run..."

    # Create temporary Dockerfile
    cat > /tmp/opencode-simple.dockerfile <<'EOF'
FROM node:26-slim

ARG OPENCODE_VERSION
# Install OpenCode CLI (the npm package pulls the native binary for this
# platform through its optional dependencies)
RUN npm install -g "@opencode/cli@${OPENCODE_VERSION}" && opencode --version

# Install additional tools for better experience
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Set entrypoint to opencode
ENTRYPOINT ["opencode"]
EOF

    # Build the image
    docker build --build-arg OPENCODE_VERSION="$OPENCODE_VERSION" \
        -f /tmp/opencode-simple.dockerfile -t "$IMAGE_NAME" /tmp/

    # Clean up
    rm /tmp/opencode-simple.dockerfile

    echo "✅ Image built successfully!"
fi

# Parse command line arguments
MODE="interactive"
QUERY=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--query)
            QUERY="$2"
            MODE="single"
            shift 2
            ;;
        -h|--help)
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -q, --query <prompt>    Run a single query"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                      # Start interactive mode"
            echo "  $0 -q 'Write a hello world in Python'"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage"
            exit 1
            ;;
    esac
done

# Run container based on mode
if [ "$MODE" = "single" ]; then
    echo "📝 Running query: $QUERY"
    echo ""

    docker run --rm \
        -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
        -e OPENCODE_MODEL="$OPENCODE_MODEL" \
        -v "$(pwd):/workspace" \
        "$IMAGE_NAME" \
        run --standalone -m "openrouter/$OPENCODE_MODEL" "$QUERY"
else
    echo ""
    echo "🔄 Starting interactive OpenCode session..."
    echo "💡 Tips:"
    echo "   - Type your questions or requests"
    echo "   - Use 'clear' to clear conversation"
    echo "   - Use 'exit' or Ctrl+C to quit"
    echo ""

    docker run --rm -it \
        -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
        -e OPENCODE_MODEL="$OPENCODE_MODEL" \
        -v "$(pwd):/workspace" \
        "$IMAGE_NAME" \
        --standalone
fi
