#!/bin/bash

# Quick launcher for AI services on remote GPU machine
# Run this on the machine at 192.168.0.152

set -e

# Get the repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

# Simple command based on first argument
case "${1:-start}" in
    start)
        echo "Starting AI MCP services..."
        docker-compose --profile ai-services up -d mcp-ai-toolkit mcp-comfyui
        echo "Services started on:"
        echo "  - AI Toolkit: http://$(hostname -I | awk '{print $1}'):8012"
        echo "  - ComfyUI: http://$(hostname -I | awk '{print $1}'):8013"
        ;;

    stop)
        echo "Stopping AI MCP services..."
        docker-compose --profile ai-services down
        ;;

    restart)
        echo "Restarting AI MCP services..."
        docker-compose --profile ai-services restart mcp-ai-toolkit mcp-comfyui
        ;;

    logs)
        docker-compose logs -f mcp-ai-toolkit mcp-comfyui
        ;;

    status)
        docker-compose ps mcp-ai-toolkit mcp-comfyui
        ;;

    build)
        echo "Building AI MCP service containers..."
        docker-compose build mcp-ai-toolkit mcp-comfyui
        ;;

    pull)
        echo "Pulling latest code..."
        git pull origin refine
        ;;

    update)
        echo "Updating and restarting services..."
        git pull origin refine
        docker-compose build mcp-ai-toolkit mcp-comfyui
        docker-compose --profile ai-services up -d mcp-ai-toolkit mcp-comfyui
        ;;

    *)
        echo "Usage: $0 {start|stop|restart|logs|status|build|pull|update}"
        echo ""
        echo "Commands:"
        echo "  start   - Start AI services"
        echo "  stop    - Stop AI services"
        echo "  restart - Restart AI services"
        echo "  logs    - View service logs"
        echo "  status  - Check service status"
        echo "  build   - Build containers"
        echo "  pull    - Pull latest code from git"
        echo "  update  - Pull code, rebuild, and restart"
        exit 1
        ;;
esac
