#!/bin/bash
# Build script for Crush and OpenCode corporate proxy containers

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================"
echo "Building Corporate Proxy Containers"
echo "======================================"
echo ""

# Function to build a container
build_container() {
    local name=$1
    local dockerfile=$2
    local context=$3
    local image_name=$4

    echo -e "${BLUE}Building $name...${NC}"

    if docker build --pull -f "$dockerfile" -t "$image_name" "$context"; then
        echo -e "${GREEN}✓ $name built successfully${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to build $name${NC}"
        return 1
    fi
}

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed${NC}"
    exit 1
fi

# Build Crush
echo "======================================"
echo "Building Crush Container"
echo "======================================"
if [ -f "$SCRIPT_DIR/crush/docker/Dockerfile" ]; then
    if build_container "Crush" \
        "$SCRIPT_DIR/crush/docker/Dockerfile" \
        "$SCRIPT_DIR" \
        "crush-corporate:latest"; then
        echo -e "${GREEN}✓ Crush container ready${NC}"
    else
        echo -e "${RED}✗ Crush build failed${NC}"
    fi
else
    echo -e "${YELLOW}Crush Dockerfile not found${NC}"
fi

echo ""

# Build OpenCode
echo "======================================"
echo "Building OpenCode Container"
echo "======================================"
if [ -f "$SCRIPT_DIR/opencode/docker/Dockerfile" ]; then
    if build_container "OpenCode" \
        "$SCRIPT_DIR/opencode/docker/Dockerfile" \
        "$SCRIPT_DIR" \
        "opencode-corporate:latest"; then
        echo -e "${GREEN}✓ OpenCode container ready${NC}"
    else
        echo -e "${RED}✗ OpenCode build failed${NC}"
    fi
else
    echo -e "${YELLOW}OpenCode Dockerfile not found${NC}"
fi

echo ""

# Build Gemini
echo "======================================"
echo "Building Gemini Container"
echo "======================================"
if [ -f "$SCRIPT_DIR/gemini/docker/Dockerfile" ]; then
    if build_container "Gemini" \
        "$SCRIPT_DIR/gemini/docker/Dockerfile" \
        "$SCRIPT_DIR" \
        "gemini-corporate:latest"; then
        echo -e "${GREEN}✓ Gemini container ready${NC}"
    else
        echo -e "${RED}✗ Gemini build failed${NC}"
    fi
else
    echo -e "${YELLOW}Gemini Dockerfile not found${NC}"
fi

echo ""
echo "======================================"
echo "Build Summary"
echo "======================================"

# Check what was built
echo "Available containers:"
if docker images -q crush-corporate:latest > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} crush-corporate:latest"
else
    echo -e "  ${RED}✗${NC} crush-corporate:latest"
fi

if docker images -q opencode-corporate:latest > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} opencode-corporate:latest"
else
    echo -e "  ${RED}✗${NC} opencode-corporate:latest"
fi

if docker images -q gemini-corporate:latest > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} gemini-corporate:latest"
else
    echo -e "  ${RED}✗${NC} gemini-corporate:latest"
fi

echo ""
echo "Next steps:"
echo "1. Test tool execution:"
echo "   ./test-container-tools.sh"
echo ""
echo "2. Test the complete flow:"
echo "   ./test-tool-flow.sh"
echo ""
echo "3. Run integration tests:"
echo "   python3 test-tool-integration.py"
