#!/bin/bash
#
# Start script for Gemini MCP Server
# This server MUST run on the host system (not in a container)
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in container
if [ -f /.dockerenv ] || [ -n "$CONTAINER_ENV" ]; then
    echo -e "${RED}ERROR: Gemini MCP Server cannot run inside a container!${NC}"
    echo -e "${RED}The Gemini CLI requires Docker access and must run on the host system.${NC}"
    echo -e "${YELLOW}Please run this script directly on the host.${NC}"
    exit 1
fi

# Default values
MODE="stdio"
PROJECT_ROOT="$(pwd)"
LOG_LEVEL="INFO"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --project-root)
            PROJECT_ROOT="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --mode MODE           Server mode: stdio (default) or http"
            echo "  --project-root PATH   Project root directory (default: current directory)"
            echo "  --log-level LEVEL     Log level: DEBUG, INFO (default), WARNING, ERROR"
            echo "  --help, -h            Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set environment variables
export MCP_GEMINI_LOG_LEVEL="$LOG_LEVEL"

echo -e "${GREEN}Starting Gemini MCP Server${NC}"
echo "Mode: $MODE"
echo "Project root: $PROJECT_ROOT"
echo "Log level: $LOG_LEVEL"
echo ""

# Change to script directory and then to the repository root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/../../../.." || exit 1

# Check if Gemini CLI is available
if ! command -v gemini &> /dev/null; then
    echo -e "${YELLOW}WARNING: Gemini CLI not found in PATH${NC}"
    echo "The Gemini MCP Server requires the Gemini CLI to be installed."
    echo "Please install it and ensure it's in your PATH."
    echo ""
fi

# Run the server
if [ "$MODE" = "stdio" ]; then
    echo "Starting in stdio mode (for Claude Desktop)..."
    echo "Press Ctrl+C to stop the server."
    python3 -m tools.mcp.gemini.server --mode stdio --project-root "$PROJECT_ROOT"
elif [ "$MODE" = "http" ]; then
    echo "Starting in HTTP mode on port 8006..."
    echo "Press Ctrl+C to stop the server."
    python3 -m tools.mcp.gemini.server --mode http --project-root "$PROJECT_ROOT"
else
    echo -e "${RED}Invalid mode: $MODE${NC}"
    echo "Mode must be 'stdio' or 'http'"
    exit 1
fi
