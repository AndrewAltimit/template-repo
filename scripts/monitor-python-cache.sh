#!/bin/bash
# Script to monitor for Python cache files that might cause permission issues

echo "🔍 Monitoring for Python Cache Files"
echo "===================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Find all Python cache directories and files
echo ""
echo "Searching for Python cache files..."

FOUND_ISSUES=0

# Check for __pycache__ directories
PYCACHE_DIRS=$(find . -type d -name "__pycache__" -not -path "./.git/*" 2>/dev/null)
if [[ -n "$PYCACHE_DIRS" ]]; then
    echo -e "${RED}❌ Found __pycache__ directories:${NC}"
    echo "$PYCACHE_DIRS" | while read -r dir; do
        echo "   $dir"
        # Check permissions
        if [[ ! -w "$dir" ]]; then
            echo -e "      ${YELLOW}⚠️  Permission issue detected${NC}"
            ((FOUND_ISSUES++))
        fi
    done
else
    echo -e "${GREEN}✅ No __pycache__ directories found${NC}"
fi

# Check for .pyc files
PYC_FILES=$(find . -type f -name "*.pyc" -not -path "./.git/*" 2>/dev/null)
if [[ -n "$PYC_FILES" ]]; then
    echo -e "${RED}❌ Found .pyc files:${NC}"
    echo "$PYC_FILES" | head -10
    PYC_COUNT=$(echo "$PYC_FILES" | wc -l)
    if [[ $PYC_COUNT -gt 10 ]]; then
        echo "   ... and $((PYC_COUNT - 10)) more"
    fi
    ((FOUND_ISSUES++))
else
    echo -e "${GREEN}✅ No .pyc files found${NC}"
fi

# Check for pytest cache
if [[ -d ".pytest_cache" ]]; then
    echo -e "${YELLOW}⚠️  Found .pytest_cache directory${NC}"
    ((FOUND_ISSUES++))
else
    echo -e "${GREEN}✅ No .pytest_cache found${NC}"
fi

# Check for mypy cache
if [[ -d ".mypy_cache" ]]; then
    echo -e "${YELLOW}⚠️  Found .mypy_cache directory${NC}"
    ((FOUND_ISSUES++))
else
    echo -e "${GREEN}✅ No .mypy_cache found${NC}"
fi

# Summary and recommendations
echo ""
echo "===================================="
if [[ $FOUND_ISSUES -eq 0 ]]; then
    echo -e "${GREEN}✅ No Python cache files found! The prevention measures are working.${NC}"
else
    echo -e "${RED}❌ Found $FOUND_ISSUES cache-related items${NC}"
    echo ""
    echo "To clean these files, run:"
    echo "  ./scripts/cleanup-workspace.sh"
    echo ""
    echo "To prevent future occurrences, ensure:"
    echo "  1. All Python containers have PYTHONDONTWRITEBYTECODE=1"
    echo "  2. pytest is run with -p no:cacheprovider"
    echo "  3. Docker containers run with correct user permissions"
fi