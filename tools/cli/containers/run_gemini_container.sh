#!/bin/bash
# run_gemini_container.sh - Run official Gemini CLI in Docker container with host authentication

set -e

echo "🚀 Starting Gemini CLI in Container"
echo ""

# Check for required dependencies
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if host has Gemini auth configured
if [ ! -d "$HOME/.gemini" ]; then
    echo "❌ No Gemini configuration found at ~/.gemini"
    echo ""
    echo "Please authenticate with Gemini CLI on your host first:"
    echo "  1. Install Gemini CLI: npm install -g @google/gemini-cli@0.21.2"
    echo "  2. Run: gemini"
    echo "  3. Complete the authentication flow"
    echo ""
    echo "This creates ~/.gemini with your authentication tokens"
    exit 1
fi

# Parse command line arguments
YOLO_MODE=false
WORKSPACE_DIR="${WORKSPACE_DIR:-$(pwd)}"
EXTRA_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yolo)
            YOLO_MODE=true
            shift
            ;;
        -w|--workspace)
            WORKSPACE_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options] [-- gemini-args]"
            echo ""
            echo "Options:"
            echo "  -y, --yolo              Enable YOLO mode (auto-approve all actions)"
            echo "  -w, --workspace <dir>   Set workspace directory (default: current dir)"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Pass-through arguments:"
            echo "  Any arguments after -- are passed directly to Gemini CLI"
            echo ""
            echo "Examples:"
            echo "  $0                      # Interactive mode with YOLO prompt"
            echo "  $0 -y                   # Force YOLO mode"
            echo "  $0 -- --help            # Show Gemini CLI help"
            echo "  $0 -- -p 'Write code'   # Run with specific prompt"
            echo ""
            echo "Authentication:"
            echo "  This script uses your host's Gemini authentication from ~/.gemini"
            echo "  Make sure you've authenticated with Gemini CLI on your host first"
            exit 0
            ;;
        --)
            shift
            EXTRA_ARGS="$*"
            break
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Prompt for YOLO mode if not already set and no extra args
if [ "$YOLO_MODE" = false ] && [ -z "$EXTRA_ARGS" ]; then
    echo "🎯 YOLO Mode Configuration"
    echo ""
    echo "YOLO mode automatically approves all Gemini actions without prompting."
    echo "This can be useful for automated workflows but should be used with caution."
    echo ""
    read -p "Enable YOLO mode? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        YOLO_MODE=true
        echo "⚡ YOLO mode ENABLED - all actions will be auto-approved!"
    else
        echo "✅ Running in normal mode - you'll be prompted for actions"
    fi
    echo ""
fi

# Configuration
IMAGE_NAME="google/gemini-cli"
IMAGE_TAG="${GEMINI_VERSION:-latest}"
CONTAINER_NAME="gemini-cli-session"

# Pull the official Gemini CLI image if needed
echo "📦 Checking for Gemini CLI Docker image..."
if ! docker pull "$IMAGE_NAME:$IMAGE_TAG" 2>/dev/null; then
    echo "⚠️  Official Gemini CLI Docker image not available"
    echo "Building custom image with Gemini CLI..."

    # Create temporary Dockerfile
    cat > /tmp/gemini-dockerfile <<'EOF'
FROM node:20-slim

# Install Gemini CLI globally (pinned version for stability)
RUN npm install -g @google/gemini-cli@0.21.2

# Create workspace directory
RUN mkdir -p /workspace
WORKDIR /workspace

# Use the existing node user (UID 1000) instead of creating a new one
# The node:20-slim image already has a 'node' user with UID 1000
RUN chown -R node:node /workspace

USER node

# Default to running Gemini CLI
ENTRYPOINT ["gemini"]
EOF

    # Build the image
    docker build -t "$IMAGE_NAME:$IMAGE_TAG" -f /tmp/gemini-dockerfile /tmp/
    rm /tmp/gemini-dockerfile

    echo "✅ Gemini CLI container image built"
fi

# Set environment variables for YOLO mode
if [ "$YOLO_MODE" = true ]; then
    YOLO_ENV="-e GEMINI_APPROVAL_MODE=yolo"
    echo "⚡ YOLO mode environment set"
else
    YOLO_ENV=""
fi

# Display current configuration
echo "📋 Configuration:"
echo "   YOLO Mode: $YOLO_MODE"
echo "   Workspace: $WORKSPACE_DIR"
echo "   Auth Source: ~/.gemini (host)"
if [ -n "$EXTRA_ARGS" ]; then
    echo "   Gemini Args: $EXTRA_ARGS"
fi
echo ""

# Check if we're running with TTY
if [ -t 0 ] && [ -z "$EXTRA_ARGS" ]; then
    TTY_FLAG="-it"
else
    TTY_FLAG="-i"
fi

# Run Gemini CLI in container with host authentication
echo "🎮 Starting Gemini CLI..."
echo ""
echo "💡 Tips:"
echo "   - Using your host authentication from ~/.gemini"
echo "   - Type '/help' for available commands"
echo "   - Type '/exit' or use Ctrl+C to quit"
if [ "$YOLO_MODE" = true ]; then
    echo "   - ⚡ YOLO mode is ACTIVE - actions auto-approved!"
fi
echo ""

# Run the container
# Mount:
# - Host's .gemini directory for authentication (to node user's home)
# - Current workspace for file access
# - Pass through any extra arguments
# shellcheck disable=SC2086
docker run $TTY_FLAG --rm \
    --name "$CONTAINER_NAME" \
    -v "$HOME/.gemini:/home/node/.gemini:ro" \
    -v "$WORKSPACE_DIR:/workspace" \
    $YOLO_ENV \
    "$IMAGE_NAME:$IMAGE_TAG" \
    $EXTRA_ARGS

echo ""
echo "👋 Gemini CLI session ended"
