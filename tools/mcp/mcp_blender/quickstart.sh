#!/bin/bash

# Blender MCP Server Quick Start Script

set -eu

echo "🎬 Blender MCP Server Quick Start"
echo "================================="
echo

# Export USER_ID and GROUP_ID for Docker volume permissions
export USER_ID="${USER_ID:-$(id -u)}"
export GROUP_ID="${GROUP_ID:-$(id -g)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

# Function to check if server is running
check_server() {
    curl -s http://localhost:8017/health > /dev/null 2>&1
    return $?
}

# Parse command line arguments
COMMAND=${1:-help}

case $COMMAND in
    start)
        # Check for GPU flag
        GPU_FLAG=""
        if [[ "$2" == "--gpu" ]]; then
            GPU_FLAG="--profile gpu"
            echo "🚀 Starting Blender MCP Server with GPU support..."
        else
            echo "🚀 Starting Blender MCP Server..."
        fi

        # Ensure host directories exist with correct permissions
        echo -e "${YELLOW}Creating host directories...${NC}"
        # Get the script's directory and repository root
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
        mkdir -p "${REPO_ROOT}/outputs/blender/projects"
        mkdir -p "${REPO_ROOT}/outputs/blender/assets"
        mkdir -p "${REPO_ROOT}/outputs/blender/renders"
        mkdir -p "${REPO_ROOT}/outputs/blender/templates"

        # Build the container
        echo -e "${YELLOW}Building container...${NC}"
        docker-compose build mcp-blender

        # Start the server
        echo -e "${YELLOW}Starting server...${NC}"
        if [ -n "$GPU_FLAG" ]; then
            docker-compose --profile gpu up -d mcp-blender
        else
            docker-compose up -d mcp-blender
        fi

        # Wait for server to be ready
        echo -n "Waiting for server to be ready"
        for _ in {1..30}; do
            if check_server; then
                echo
                echo -e "${GREEN}✅ Server is running at http://localhost:8017${NC}"
                echo
                echo "You can now:"
                echo "  • Test the server: ./quickstart.sh test"
                echo "  • Run a demo: ./quickstart.sh demo"
                echo "  • Check logs: ./quickstart.sh logs"
                echo "  • Stop server: ./quickstart.sh stop"
                exit 0
            fi
            echo -n "."
            sleep 1
        done

        echo
        echo -e "${RED}❌ Server failed to start${NC}"
        echo "Check logs with: docker-compose logs mcp-blender"
        exit 1
        ;;

    stop)
        echo "🛑 Stopping Blender MCP Server..."
        docker-compose stop mcp-blender
        echo -e "${GREEN}✅ Server stopped${NC}"
        ;;

    restart)
        echo "🔄 Restarting Blender MCP Server..."
        docker-compose restart mcp-blender
        echo -e "${GREEN}✅ Server restarted${NC}"
        ;;

    status)
        if check_server; then
            echo -e "${GREEN}✅ Server is running${NC}"
            echo
            echo "Server details:"
            curl -s http://localhost:8017/health | python3 -m json.tool
        else
            echo -e "${RED}❌ Server is not running${NC}"
            echo "Start it with: ./quickstart.sh start"
        fi
        ;;

    logs)
        echo "📜 Showing server logs (Ctrl+C to exit)..."
        docker-compose logs -f mcp-blender
        ;;

    test)
        echo "🧪 Testing Blender MCP Server..."

        if ! check_server; then
            echo -e "${RED}❌ Server is not running${NC}"
            echo "Start it first with: ./quickstart.sh start"
            exit 1
        fi

        # Run test script
        python3 tools/mcp/blender/scripts/test_server.py
        ;;

    demo)
        echo "🎨 Running Blender MCP Demo..."

        if ! check_server; then
            echo -e "${RED}❌ Server is not running${NC}"
            echo "Start it first with: ./quickstart.sh start"
            exit 1
        fi

        # Show demo options
        echo
        echo "Select a demo:"
        echo "  1) Quick Render - Create and render a simple scene"
        echo "  2) Physics - Falling objects simulation"
        echo "  3) Animation - Keyframe animation"
        echo "  4) Geometry Nodes - Procedural generation"
        echo "  5) All demos"
        echo
        read -r -p "Enter choice (1-5): " choice

        case $choice in
            1) python3 tools/mcp/blender/scripts/test_server.py --demo render ;;
            2) python3 tools/mcp/blender/scripts/test_server.py --demo physics ;;
            3) python3 tools/mcp/blender/scripts/test_server.py --demo animation ;;
            4) python3 tools/mcp/blender/scripts/test_server.py --demo geometry ;;
            5) python3 tools/mcp/blender/scripts/test_server.py --demo all ;;
            *) echo "Invalid choice" ;;
        esac
        ;;

    interactive)
        echo "💻 Starting Interactive Mode..."

        if ! check_server; then
            echo -e "${RED}❌ Server is not running${NC}"
            echo "Start it first with: ./quickstart.sh start"
            exit 1
        fi

        python3 tools/mcp/blender/scripts/test_server.py --interactive
        ;;

    gpu-info)
        echo "🎮 GPU Information:"
        echo

        # Check for NVIDIA GPU
        if command -v nvidia-smi &> /dev/null; then
            echo "NVIDIA GPU detected:"
            nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
            echo

            # Check if NVIDIA Container Toolkit is installed
            if docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi > /dev/null 2>&1; then
                echo -e "${GREEN}✅ NVIDIA Container Toolkit is installed${NC}"
                echo "GPU acceleration is available for rendering!"
            else
                echo -e "${YELLOW}⚠️  NVIDIA Container Toolkit not installed${NC}"
                echo "Install it for GPU acceleration:"
                echo "https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
            fi
        else
            echo -e "${YELLOW}⚠️  No NVIDIA GPU detected${NC}"
            echo "Blender will use CPU for rendering"
        fi
        ;;

    clean)
        echo "🧹 Cleaning up..."

        # Stop and remove container
        docker-compose down mcp-blender

        # Clean up output files
        read -p "Remove output files? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf outputs/blender/renders/*
            rm -rf outputs/blender/projects/*
            echo -e "${GREEN}✅ Output files removed${NC}"
        fi

        echo -e "${GREEN}✅ Cleanup complete${NC}"
        ;;

    help|*)
        cat << EOF
🎬 Blender MCP Server Quick Start

Usage: ./quickstart.sh [COMMAND]

Commands:
  start       - Build and start the Blender MCP server
  start --gpu - Start with GPU support (NVIDIA)
  stop        - Stop the server
  restart     - Restart the server
  status      - Check server status
  logs        - Show server logs
  test        - Run basic tests
  demo        - Run interactive demos
  interactive - Start interactive testing mode
  gpu-info    - Check GPU availability
  clean       - Stop server and clean up files
  help        - Show this help message

Examples:
  ./quickstart.sh start       # Start the server
  ./quickstart.sh start --gpu # Start with GPU support
  ./quickstart.sh demo        # Run demos
  ./quickstart.sh logs        # View logs

Documentation:
  tools/mcp/blender/docs/README.md

Requirements:
  - Docker and Docker Compose
  - Python 3.8+
  - (Optional) NVIDIA GPU for accelerated rendering

EOF
        ;;
esac
