#!/bin/bash
set -e
# Start AI Toolkit Full Application (Web UI + MCP Server) in Docker
# Automatically opens the web UI in your default browser

echo -e "\033[36m========================================\033[0m"
echo -e "\033[32mAI Toolkit Full Application Launcher\033[0m"
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

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "\033[31mERROR: docker-compose not found\033[0m"
    echo "Please install docker-compose:"
    echo "  https://docs.docker.com/compose/install/"
    exit 1
fi

# Get script directory and navigate to repository root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$SCRIPT_DIR/../../.."
cd "$REPO_ROOT" || exit 1

echo -e "\033[33mBuilding AI Toolkit container...\033[0m"
echo "This may take a while on first run or after updates"
docker-compose build mcp-ai-toolkit

echo
echo -e "\033[33mStarting AI Toolkit container...\033[0m"
docker-compose --profile ai-services up -d mcp-ai-toolkit

# Check if the container started successfully
if ! docker ps --format "table {{.Names}}" | grep -q "ai-toolkit"; then
    echo -e "\033[31mERROR: Failed to start AI Toolkit container\033[0m"
    echo "Check Docker and try again"
    docker-compose logs mcp-ai-toolkit
    exit 1
fi

echo
echo -e "\033[36m========================================\033[0m"
echo -e "\033[32mAI Toolkit is starting up...\033[0m"
echo -e "\033[36m========================================\033[0m"
echo
echo -e "\033[33mServices:\033[0m"
echo -e "  \033[36mWeb UI:\033[0m     http://localhost:8675"
echo -e "  \033[36mMCP Server:\033[0m http://localhost:8012"
echo

# Wait for services to initialize with healthcheck polling
echo -e "\033[33mWaiting for AI Toolkit to initialize...\033[0m"
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -f http://localhost:8675/ >/dev/null 2>&1; then
        echo -e "\033[32mAI Toolkit is ready!\033[0m"
        break
    fi
    echo -n "."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done
if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo -e "\n\033[33mWarning: AI Toolkit may still be starting up\033[0m"
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
echo -e "\033[32mOpening AI Toolkit Web UI in your browser...\033[0m"
open_url "http://localhost:8675"

echo
echo -e "\033[36m========================================\033[0m"
echo -e "\033[32mAI Toolkit is running!\033[0m"
echo -e "\033[36m========================================\033[0m"
echo
echo -e "\033[33mCommands:\033[0m"
echo "  View logs:  docker-compose logs -f mcp-ai-toolkit"
echo "  Stop:       docker-compose --profile ai-services stop mcp-ai-toolkit"
echo "  Restart:    docker-compose --profile ai-services restart mcp-ai-toolkit"
echo
echo "Press Enter to view logs (Ctrl+C to exit logs)..."
read -r

# Show logs
docker-compose logs -f mcp-ai-toolkit
