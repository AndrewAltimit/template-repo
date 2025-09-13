#!/bin/bash
# Build all DBR environment wheels

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."

echo -e "${GREEN}Building DBR Environment Wheels${NC}"
echo ""

# Check if build tool is installed
if ! python3 -m pip show build &> /dev/null; then
    echo -e "${YELLOW}Installing build tool...${NC}"
    python3 -m pip install --quiet build twine
fi

# Clean previous builds
echo -e "${YELLOW}Cleaning previous builds...${NC}"
rm -rf "$PROJECT_ROOT"/wheels/*/dist
rm -rf "$PROJECT_ROOT"/wheels/*/build
rm -rf "$PROJECT_ROOT"/wheels/*/*.egg-info
rm -rf "$PROJECT_ROOT"/wheels/*/src/*.egg-info

# Build each wheel
PACKAGES=("dbr-env-core" "dbr-env-ml" "dbr-env-cloud" "dbr-env-all")

for package in "${PACKAGES[@]}"; do
    echo ""
    echo -e "${YELLOW}Building $package...${NC}"

    cd "$PROJECT_ROOT/wheels/$package"

    # Build wheel
    python3 -m build --wheel

    # Check if build succeeded
    if [ -f dist/*.whl ]; then
        echo -e "${GREEN}✓ $package built successfully${NC}"
        ls -lh dist/*.whl
    else
        echo -e "${RED}✗ Failed to build $package${NC}"
        exit 1
    fi
done

# Create a dist directory for all wheels
echo ""
echo -e "${YELLOW}Collecting all wheels...${NC}"
mkdir -p "$PROJECT_ROOT/dist"
cp "$PROJECT_ROOT"/wheels/*/dist/*.whl "$PROJECT_ROOT/dist/"

echo ""
echo -e "${GREEN}✓ All wheels built successfully!${NC}"
echo ""
echo "Wheels available in: $PROJECT_ROOT/dist/"
ls -lh "$PROJECT_ROOT/dist/"

# Validate wheels with twine
echo ""
echo -e "${YELLOW}Validating wheels with twine...${NC}"
python3 -m twine check "$PROJECT_ROOT"/dist/*.whl

echo ""
echo -e "${GREEN}✓ Build complete!${NC}"
