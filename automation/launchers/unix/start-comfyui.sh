#!/bin/bash
set -e
# Start ComfyUI Full Application (Web UI + MCP Server) in Docker
# Automatically opens the web UI in your default browser

echo -e "\033[36m========================================\033[0m"
echo -e "\033[32mComfyUI Full Application Launcher\033[0m"
echo -e "\033[36m========================================\033[0m"
echo

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "\033[31mERROR: Docker not found\033[0m"
    echo "Please install Docker for your platform:"
    echo "  macOS: https://www.docker.com/products/docker-desktop"
    echo "  Linux: https://docs.docker.com/engine/install/"
    exit 1
fi

# Use docker compose v2 (plugin) if available, fallback to docker compose v1
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker compose &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "\033[31mERROR: docker compose not found\033[0m"
    echo "Please install Docker Compose:"
    echo "  https://docs.docker.com/compose/install/"
    exit 1
fi

# Get script directory and navigate to repository root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$SCRIPT_DIR/../../.."
cd "$REPO_ROOT" || exit 1

# Detect architecture and select appropriate Dockerfile
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    export COMFYUI_DOCKERFILE="docker/comfyui-arm64.Dockerfile"
    echo -e "\033[36mDetected ARM64 architecture - using NGC PyTorch image\033[0m"
else
    export COMFYUI_DOCKERFILE="docker/comfyui.Dockerfile"
    echo -e "\033[36mDetected x86_64 architecture - using standard PyTorch wheels\033[0m"
fi

echo -e "\033[33mBuilding ComfyUI container...\033[0m"
echo "This may take a while on first run or after updates"
$COMPOSE_CMD build mcp-comfyui

# Remove stale container to avoid docker compose v1 ContainerConfig bug
docker rm -f comfyui 2>/dev/null || true

echo
echo -e "\033[33mStarting ComfyUI container...\033[0m"
$COMPOSE_CMD --profile ai-services up -d mcp-comfyui

# Check if the container started successfully
if ! docker ps --format "table {{.Names}}" | grep -q "comfyui"; then
    echo -e "\033[31mERROR: Failed to start ComfyUI container\033[0m"
    echo "Check Docker and try again"
    $COMPOSE_CMD logs mcp-comfyui
    exit 1
fi

echo
echo -e "\033[36m========================================\033[0m"
echo -e "\033[32mComfyUI is starting up...\033[0m"
echo -e "\033[36m========================================\033[0m"
echo
echo -e "\033[33mServices:\033[0m"
echo -e "  \033[36mWeb UI:\033[0m     http://localhost:8188"
echo -e "  \033[36mMCP Server:\033[0m http://localhost:8013"
echo

# Wait for services to initialize with healthcheck polling
echo -e "\033[33mWaiting for ComfyUI to initialize...\033[0m"
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -f http://localhost:8188/system_stats >/dev/null 2>&1; then
        echo -e "\033[32mComfyUI is ready!\033[0m"
        break
    fi
    echo -n "."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done
if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo -e "\n\033[33mWarning: ComfyUI may still be starting up\033[0m"
fi

# Function to open URL based on platform
open_url() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v xdg-open &> /dev/null; then
            xdg-open "$1" 2>/dev/null
        elif command -v gnome-open &> /dev/null; then
            gnome-open "$1" 2>/dev/null
        else
            echo "Please open $1 in your browser"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        open "$1"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        start "$1"
    else
        echo "Please open $1 in your browser"
    fi
}

# Open the web UI in default browser
echo -e "\033[32mOpening ComfyUI Web UI in your browser...\033[0m"
open_url "http://localhost:8188"

echo
echo -e "\033[36m========================================\033[0m"
echo -e "\033[32mComfyUI is running!\033[0m"
echo -e "\033[36m========================================\033[0m"
echo
echo -e "\033[33mCommands:\033[0m"
echo "  View logs:  $COMPOSE_CMD logs -f mcp-comfyui"
echo "  Stop:       $COMPOSE_CMD --profile ai-services stop mcp-comfyui"
echo "  Restart:    $COMPOSE_CMD --profile ai-services restart mcp-comfyui"
echo
echo "Press Enter to view logs (Ctrl+C to exit logs)..."
read -r

# Show logs
$COMPOSE_CMD logs -f mcp-comfyui
