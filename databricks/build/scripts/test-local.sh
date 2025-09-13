#!/bin/bash
# Test DBR environment setup locally

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../.."

# Default values
DBR_VERSION="dbr15"
TEST_ENV="venv_test"
SKIP_BUILD=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            DBR_VERSION="$2"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --help)
            echo "DBR Environment Local Test Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --version VERSION    DBR version to test (dbr15 or dbr16)"
            echo "  --skip-build        Skip building wheels"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}Testing DBR Environment Setup - $DBR_VERSION${NC}"
echo ""

# Build wheels if needed
if [ "$SKIP_BUILD" = false ]; then
    echo -e "${YELLOW}Building wheels...${NC}"
    "$PROJECT_ROOT/build/scripts/build-wheels.sh"
else
    echo -e "${YELLOW}Skipping wheel build${NC}"
fi

# Create test virtual environment
echo ""
echo -e "${YELLOW}Creating test virtual environment: $TEST_ENV${NC}"
rm -rf "$PROJECT_ROOT/$TEST_ENV"

# Select Python version based on DBR version
if [ "$DBR_VERSION" = "dbr15" ]; then
    PYTHON_VERSION="python3.11"
else
    PYTHON_VERSION="python3.12"
fi

# Check if specific Python version is available
if ! command -v "$PYTHON_VERSION" &> /dev/null; then
    echo -e "${YELLOW}Warning: $PYTHON_VERSION not found, using python3${NC}"
    PYTHON_VERSION="python3"
fi

# Create virtual environment
"$PYTHON_VERSION" -m venv "$PROJECT_ROOT/$TEST_ENV"

# Activate virtual environment
source "$PROJECT_ROOT/$TEST_ENV/bin/activate"

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --quiet --upgrade pip

# Install wheels
echo ""
echo -e "${YELLOW}Installing DBR environment wheels...${NC}"

# Install in correct order (dependencies first)
pip install "$PROJECT_ROOT"/dist/dbr_env_core-*.whl
pip install "$PROJECT_ROOT"/dist/dbr_env_ml-*.whl
pip install "$PROJECT_ROOT"/dist/dbr_env_cloud-*.whl
pip install "$PROJECT_ROOT"/dist/dbr_env_all-*.whl

# Install the extras for the specific DBR version
echo ""
echo -e "${YELLOW}Installing $DBR_VERSION dependencies...${NC}"
pip install "dbr-env-all[$DBR_VERSION]"

# Test imports
echo ""
echo -e "${YELLOW}Testing Python imports...${NC}"

python -c "
import sys
print(f'Python version: {sys.version}')

# Test core imports
try:
    from dbr_env_core import get_dbr_info
    info = get_dbr_info('$DBR_VERSION')
    print(f'✓ dbr_env_core imported successfully')
    print(f'  DBR info: {info}')
except ImportError as e:
    print(f'✗ Failed to import dbr_env_core: {e}')
    sys.exit(1)

# Test ML imports
try:
    from dbr_env_ml import get_ml_info
    info = get_ml_info('$DBR_VERSION')
    print(f'✓ dbr_env_ml imported successfully')
    print(f'  ML packages: {list(info.keys())}')
except ImportError as e:
    print(f'✗ Failed to import dbr_env_ml: {e}')
    sys.exit(1)

# Test cloud imports
try:
    from dbr_env_cloud import get_cloud_info
    info = get_cloud_info('$DBR_VERSION')
    print(f'✓ dbr_env_cloud imported successfully')
    print(f'  Cloud providers: {list(info.keys())}')
except ImportError as e:
    print(f'✗ Failed to import dbr_env_cloud: {e}')
    sys.exit(1)

# Test all imports
try:
    from dbr_env_all import get_all_info
    info = get_all_info('$DBR_VERSION')
    print(f'✓ dbr_env_all imported successfully')
    print(f'  Components: {list(info.keys())}')
except ImportError as e:
    print(f'✗ Failed to import dbr_env_all: {e}')
    sys.exit(1)

print('')
print('✓ All imports successful!')
"

# Test validation script
echo ""
echo -e "${YELLOW}Testing validation module...${NC}"

python -c "
from dbr_env_all.validate import validate_dbr_environment
result = validate_dbr_environment('$DBR_VERSION', json_output=False)
print(result)
"

# Test command-line validation
echo ""
echo -e "${YELLOW}Testing command-line validation...${NC}"

if command -v dbr-validate &> /dev/null; then
    echo -e "${GREEN}✓ dbr-validate command found${NC}"
    dbr-validate --version "$DBR_VERSION" || true
else
    echo -e "${YELLOW}⚠ dbr-validate command not found (expected before post-install)${NC}"
fi

# Deactivate virtual environment
deactivate

# Summary
echo ""
echo -e "${GREEN}✓ Local testing complete!${NC}"
echo ""
echo "Test environment preserved in: $PROJECT_ROOT/$TEST_ENV"
echo "To remove test environment: rm -rf $PROJECT_ROOT/$TEST_ENV"
