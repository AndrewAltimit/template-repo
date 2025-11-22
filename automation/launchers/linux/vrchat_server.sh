#!/bin/bash
# Start Virtual Character MCP Server
# For local development or Linux/Mac systems

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Default configuration
PORT="${1:-8020}"
HOST="${2:-0.0.0.0}"
MODE="${3:-http}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Virtual Character MCP Server${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 is not installed${NC}"
    exit 1
fi

echo -e "${YELLOW}Configuration:${NC}"
echo "  Port: $PORT"
echo "  Host: $HOST"
echo "  Mode: $MODE"
echo ""

# Navigate to repo root
cd "$REPO_ROOT" || exit 1

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"

check_and_install() {
    local module=$1
    local package=$2

    if ! python3 -c "import $module" 2>/dev/null; then
        echo "  Installing $package..."
        pip3 install --user "$package"
    else
        echo -e "  ${GREEN}✓${NC} $module installed"
    fi
}

check_and_install "pythonosc" "python-osc"
check_and_install "fastapi" "fastapi uvicorn[standard]"
check_and_install "aiohttp" "aiohttp"

echo ""
echo -e "${GREEN}Starting Virtual Character MCP Server...${NC}"
echo -e "Server will be available at ${GREEN}http://$HOST:$PORT${NC}"
echo ""
echo -e "${YELLOW}Available endpoints:${NC}"
echo "  POST /set_backend      - Connect to backend"
echo "  POST /send_animation   - Send animation data"
echo "  POST /execute_behavior - Execute behaviors"
echo "  GET  /receive_state    - Get current state"
echo "  GET  /list_backends    - List available backends"
echo "  GET  /get_backend_status - Get backend status"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Start the server
exec python3 -m mcp_virtual_character.server \
    --port "$PORT" \
    --host "$HOST" \
    --mode "$MODE"
