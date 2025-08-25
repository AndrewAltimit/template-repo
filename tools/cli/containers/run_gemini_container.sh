#!/bin/bash
# run_gemini_container.sh - Run Gemini CLI in Docker container with corporate proxy

set -e

echo "🚀 Starting Gemini CLI in Container (Corporate Proxy Mode)"
echo ""

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
GEMINI_DIR="$PROJECT_ROOT/automation/corporate-proxy/gemini"

# Check if Gemini container image exists, build if not
check_and_build_image() {
    local image_name="gemini-corporate-proxy"
    local image_tag="latest"
    local full_image="${image_name}:${image_tag}"

    if ! docker images | grep -q "$image_name"; then
        echo "📦 Gemini container image not found, building..."
        echo "This may take a few minutes on first run..."

        # Build the Gemini container
        cd "$GEMINI_DIR"
        ./scripts/build.sh
        cd "$PROJECT_ROOT"

        echo "✅ Gemini container built successfully!"
        echo ""
    else
        echo "✅ Using existing Gemini container image: $full_image"
    fi
}

# Build image if needed
check_and_build_image

# Parse command line arguments
MODE="interactive"
YOLO_MODE=false
WORKSPACE_DIR="${WORKSPACE_DIR:-$(pwd)}"

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yolo)
            YOLO_MODE=true
            shift
            ;;
        -d|--daemon)
            MODE="daemon"
            shift
            ;;
        -t|--test)
            MODE="test"
            shift
            ;;
        -w|--workspace)
            WORKSPACE_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -y, --yolo              Enable YOLO mode (auto-approve all actions)"
            echo "  -d, --daemon            Run in background daemon mode"
            echo "  -t, --test              Run tests and exit"
            echo "  -w, --workspace <dir>   Set workspace directory (default: current dir)"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Interactive Mode (default):"
            echo "  Start an interactive Gemini CLI session with corporate proxy"
            echo ""
            echo "YOLO Mode:"
            echo "  $0 -y"
            echo "  Automatically approve all Gemini actions (use with caution!)"
            echo ""
            echo "Daemon Mode:"
            echo "  $0 -d"
            echo "  Run services in background, access with docker exec"
            echo ""
            echo "Test Mode:"
            echo "  $0 -t"
            echo "  Run integration tests to verify proxy functionality"
            echo ""
            echo "Environment Variables:"
            echo "  COMPANY_API_BASE    - Corporate API endpoint (default: mock)"
            echo "  COMPANY_API_TOKEN   - Authentication token"
            echo "  USE_MOCK_API        - Use mock responses (default: true)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Prompt for YOLO mode if not already set
if [ "$YOLO_MODE" = false ] && [ "$MODE" = "interactive" ]; then
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
IMAGE_NAME="${IMAGE_NAME:-gemini-corporate-proxy}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
CONTAINER_NAME="${CONTAINER_NAME:-gemini-proxy}"

# Check if container is already running (for daemon mode)
if [ "$MODE" = "daemon" ]; then
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "⚠️  Container '$CONTAINER_NAME' is already running"
        echo ""
        echo "To access it:"
        echo "  docker exec -it $CONTAINER_NAME gemini"
        echo ""
        echo "To stop it:"
        echo "  docker stop $CONTAINER_NAME"
        exit 0
    fi
fi

# Stop any existing container with the same name
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping existing container..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# Set environment variables for YOLO mode
if [ "$YOLO_MODE" = true ]; then
    export GEMINI_YOLO_MODE=true
    YOLO_ENV="-e GEMINI_YOLO_MODE=true"
else
    YOLO_ENV=""
fi

# Display current configuration
echo "📋 Configuration:"
echo "   Mode: $MODE"
echo "   YOLO: $YOLO_MODE"
echo "   Workspace: $WORKSPACE_DIR"
echo "   Container: $FULL_IMAGE"
echo ""

# Run based on mode
case "$MODE" in
    test)
        echo "🧪 Running tests..."
        docker run --rm \
            "$FULL_IMAGE" \
            test
        ;;

    daemon)
        echo "👹 Starting in daemon mode..."
        # shellcheck disable=SC2086
        docker run -d \
            --name "$CONTAINER_NAME" \
            -v "$WORKSPACE_DIR:/workspace" \
            -p 8050:8050 \
            -p 8053:8053 \
            $YOLO_ENV \
            "$FULL_IMAGE" \
            daemon

        echo ""
        echo "✅ Container started in background: $CONTAINER_NAME"
        echo ""
        echo "📝 Usage:"
        echo "   Access Gemini CLI:"
        echo "     docker exec -it $CONTAINER_NAME gemini"
        echo ""
        echo "   View logs:"
        echo "     docker logs -f $CONTAINER_NAME"
        echo ""
        echo "   Check services:"
        echo "     docker exec $CONTAINER_NAME curl http://localhost:8050/health"
        echo "     docker exec $CONTAINER_NAME curl http://localhost:8053/health"
        echo ""
        echo "   Stop container:"
        echo "     docker stop $CONTAINER_NAME"
        ;;

    interactive|*)
        echo "🎮 Starting interactive Gemini CLI session..."
        echo ""
        echo "💡 Tips:"
        echo "   - Gemini will auto-start in the container"
        echo "   - All prompts return 'Hatsune Miku' in mock mode"
        echo "   - Type 'exit' or use Ctrl+C to quit"
        if [ "$YOLO_MODE" = true ]; then
            echo "   - ⚡ YOLO mode is ACTIVE - actions auto-approved!"
        fi
        echo ""
        echo "🔗 Services:"
        echo "   Mock API: http://localhost:8050"
        echo "   Proxy: http://localhost:8053"
        echo ""

        # shellcheck disable=SC2086
        docker run -it --rm \
            --name "$CONTAINER_NAME" \
            -v "$WORKSPACE_DIR:/workspace" \
            -p 8050:8050 \
            -p 8053:8053 \
            $YOLO_ENV \
            "$FULL_IMAGE" \
            interactive
        ;;
esac

echo ""
echo "👋 Gemini container session ended"
