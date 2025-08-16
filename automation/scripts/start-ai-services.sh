#!/bin/bash

# Start AI Toolkit and ComfyUI MCP servers on remote GPU machine
# This script is intended to run on the remote machine with NVIDIA GPU support

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MODE="${1:-docker}"  # docker or host
PROFILE="${2:-ai-services}"  # ai-services or gpu (includes all GPU services)

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}AI Services MCP Server Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get the repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Check for NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✓ NVIDIA GPU detected${NC}"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo ""
else
    echo -e "${YELLOW}⚠ Warning: No NVIDIA GPU detected${NC}"
    echo "The AI services require GPU support for optimal performance."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

cd "$REPO_ROOT"

case $MODE in
    docker)
        echo -e "${YELLOW}Starting AI services in Docker containers...${NC}"

        # Check if Docker is installed
        if ! command -v docker &> /dev/null; then
            echo -e "${RED}✗ Docker is not installed${NC}"
            exit 1
        fi

        # Check if docker-compose is installed
        if ! command -v docker-compose &> /dev/null; then
            echo -e "${RED}✗ docker-compose is not installed${NC}"
            exit 1
        fi

        # Check for nvidia-docker runtime
        if docker info 2>/dev/null | grep -q nvidia; then
            echo -e "${GREEN}✓ NVIDIA Docker runtime detected${NC}"
        else
            echo -e "${YELLOW}⚠ NVIDIA Docker runtime not detected${NC}"
            echo "Install nvidia-docker2 for GPU support in containers"
        fi

        echo ""
        echo "Building containers (this may take a while on first run)..."
        docker-compose build mcp-ai-toolkit mcp-comfyui

        echo ""
        echo "Starting services with profile: $PROFILE"
        docker-compose --profile "$PROFILE" up -d mcp-ai-toolkit mcp-comfyui

        # Wait for services to be healthy
        echo ""
        echo "Waiting for services to become healthy..."
        for _ in {1..30}; do
            if docker-compose ps | grep -q healthy; then
                echo -e "${GREEN}✓ Services are healthy${NC}"
                break
            fi
            echo -n "."
            sleep 2
        done
        echo ""

        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}AI services started successfully!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo "AI Toolkit:"
        echo -e "  ${BLUE}Web UI${NC}: http://0.0.0.0:8675"
        echo -e "  ${BLUE}MCP Server${NC}: http://0.0.0.0:8012"
        echo ""
        echo "ComfyUI:"
        echo -e "  ${BLUE}Web UI${NC}: http://0.0.0.0:8188"
        echo -e "  ${BLUE}MCP Server${NC}: http://0.0.0.0:8013"
        echo ""
        echo "Container status:"
        docker-compose ps mcp-ai-toolkit mcp-comfyui
        echo ""
        echo "Commands:"
        echo "  View logs:    docker-compose logs -f mcp-ai-toolkit mcp-comfyui"
        echo "  Stop:         docker-compose --profile $PROFILE down"
        echo "  Restart:      docker-compose --profile $PROFILE restart"
        echo "  Shell access: docker-compose exec mcp-ai-toolkit bash"
        ;;

    host)
        echo -e "${YELLOW}Starting AI services on host...${NC}"

        # Check Python installation
        if ! command -v python3 &> /dev/null; then
            echo -e "${RED}✗ Python 3 is not installed${NC}"
            exit 1
        fi

        # Install dependencies if needed
        if [ ! -d "$REPO_ROOT/venv" ]; then
            echo "Creating virtual environment..."
            python3 -m venv "$REPO_ROOT/venv"
        fi

        # Activate virtual environment
        # shellcheck disable=SC1091
        source "$REPO_ROOT/venv/bin/activate"

        echo "Installing dependencies..."
        pip install -q -r "$REPO_ROOT/docker/requirements/requirements-ai-toolkit.txt"
        pip install -q -r "$REPO_ROOT/docker/requirements/requirements-comfyui.txt"

        # Start AI Toolkit MCP Server
        echo "Starting AI Toolkit MCP Server..."
        nohup python3 -m tools.mcp.ai_toolkit.server --mode http --host 0.0.0.0 > /tmp/ai-toolkit-mcp.log 2>&1 &
        AI_TOOLKIT_PID=$!
        echo "AI Toolkit PID: $AI_TOOLKIT_PID"

        # Start ComfyUI MCP Server
        echo "Starting ComfyUI MCP Server..."
        nohup python3 -m tools.mcp.comfyui.server --mode http --host 0.0.0.0 > /tmp/comfyui-mcp.log 2>&1 &
        COMFYUI_PID=$!
        echo "ComfyUI PID: $COMFYUI_PID"

        # Save PIDs for later
        echo "$AI_TOOLKIT_PID" > /tmp/ai-toolkit-mcp.pid
        echo "$COMFYUI_PID" > /tmp/comfyui-mcp.pid

        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}AI services started successfully!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo "Services running:"
        echo -e "  ${BLUE}AI Toolkit MCP${NC}: http://0.0.0.0:8012 (PID: $AI_TOOLKIT_PID)"
        echo -e "  ${BLUE}ComfyUI MCP${NC}: http://0.0.0.0:8013 (PID: $COMFYUI_PID)"
        echo ""
        echo "Commands:"
        echo "  View AI Toolkit logs: tail -f /tmp/ai-toolkit-mcp.log"
        echo "  View ComfyUI logs:    tail -f /tmp/comfyui-mcp.log"
        echo "  Stop services:        kill $AI_TOOLKIT_PID $COMFYUI_PID"
        echo "  Stop using PID files: kill \$(cat /tmp/ai-toolkit-mcp.pid) \$(cat /tmp/comfyui-mcp.pid)"
        ;;

    *)
        echo -e "${RED}Invalid mode: $MODE${NC}"
        echo "Usage: $0 [docker|host] [profile]"
        echo ""
        echo "Modes:"
        echo "  docker - Run in Docker containers (recommended)"
        echo "  host   - Run directly on host"
        echo ""
        echo "Profiles (docker only):"
        echo "  ai-services - AI Toolkit and ComfyUI only"
        echo "  gpu        - All GPU-enabled services"
        exit 1
        ;;
esac
