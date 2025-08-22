#!/bin/bash
# Run OpenCode with proxy in a container
# Usage: ./run_opencode_container.sh [mock|real] [interactive|query "Your question"]

set -e

# Configuration
MODE=${1:-mock}
INTERACTION=${2:-interactive}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${MAGENTA}🎭 OpenCode Container Launcher${NC}"
echo "================================"
echo ""

# Build the container if it doesn't exist
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^opencode-with-proxy:latest$"; then
    echo -e "${YELLOW}Building container...${NC}"
    docker build -f docker/opencode-with-proxy.Dockerfile -t opencode-with-proxy:latest . || {
        echo -e "${RED}Failed to build container${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Container built${NC}"
else
    echo -e "${GREEN}✓ Container image exists${NC}"
fi

# Set environment based on mode
if [ "$MODE" = "real" ]; then
    echo -e "${CYAN}Using REAL company API${NC}"

    # Check for required environment variables
    if [ -z "$COMPANY_API_BASE" ] || [ -z "$COMPANY_API_TOKEN" ]; then
        echo -e "${RED}Error: For real mode, set COMPANY_API_BASE and COMPANY_API_TOKEN${NC}"
        echo "Example:"
        echo "  export COMPANY_API_BASE=https://your-api.com"
        echo "  export COMPANY_API_TOKEN=your-token"
        echo "  $0 real"
        exit 1
    fi

    ENV_OPTS="-e PROXY_MOCK_MODE=false -e COMPANY_API_BASE=$COMPANY_API_BASE -e COMPANY_API_TOKEN=$COMPANY_API_TOKEN"
else
    echo -e "${YELLOW}Using MOCK mode (all responses = 'Hatsune Miku')${NC}"
    ENV_OPTS="-e PROXY_MOCK_MODE=true"
fi

echo ""

# Run based on interaction type
if [ "$INTERACTION" = "interactive" ]; then
    echo -e "${BLUE}Starting OpenCode interactive session...${NC}"
    echo ""
    echo -e "${CYAN}Available Models through Company Proxy:${NC}"
    echo "  • Claude 3.5 Sonnet (default)"
    echo "  • Claude 3 Opus"
    echo "  • GPT-4"
    echo ""
    echo -e "${YELLOW}Note: OpenCode may show other models in its list, but only${NC}"
    echo -e "${YELLOW}      the above 3 models work through the company proxy.${NC}"
    echo ""

    docker run --rm -it \
        $ENV_OPTS \
        -v "$(pwd):/workspace" \
        opencode-with-proxy:latest

elif [ "$INTERACTION" = "query" ]; then
    QUERY="${3:-What is your name?}"
    echo -e "${BLUE}Running query: '$QUERY'${NC}"
    echo ""

    docker run --rm \
        $ENV_OPTS \
        -v "$(pwd):/workspace" \
        opencode-with-proxy:latest \
        bash -c "echo '$QUERY' | opencode run 2>/dev/null | grep -v '^\[' | grep -v '^$'"

else
    echo -e "${RED}Invalid usage${NC}"
    echo ""
    echo "Usage:"
    echo "  $0 [mock|real] [interactive|query \"Your question\"]"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Mock mode, interactive"
    echo "  $0 mock interactive                   # Same as above"
    echo "  $0 mock query \"What is 2+2?\"          # Single query, mock mode"
    echo "  $0 real interactive                   # Real API, interactive"
    echo "  $0 real query \"Write hello world\"     # Single query, real API"
    exit 1
fi
