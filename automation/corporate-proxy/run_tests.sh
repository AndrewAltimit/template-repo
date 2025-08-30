#!/bin/bash
#
# Run corporate proxy tests in Docker container
# This follows the project's container-first philosophy
#

set -e

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo -e "${BLUE}Running corporate proxy tests in Docker container...${NC}"

# Change to project root
cd "$PROJECT_ROOT"

# Build the CI image if needed
echo -e "${BLUE}Building CI image...${NC}"
docker-compose build python-ci

# Run all tests in container
echo -e "${BLUE}Running tests...${NC}"
docker-compose run --rm python-ci python -m pytest \
    automation/corporate-proxy/tests/ \
    -v \
    --tb=short \
    --no-header

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi