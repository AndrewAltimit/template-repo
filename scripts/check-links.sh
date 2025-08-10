#!/bin/bash
# Check markdown links locally before pushing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Markdown Link Checker ===${NC}"
echo ""

# Check if markdown-link-check is installed
if ! command -v markdown-link-check &> /dev/null; then
    echo -e "${YELLOW}markdown-link-check is not installed.${NC}"
    echo "Installing markdown-link-check..."

    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}npm is not installed. Please install Node.js and npm first.${NC}"
        echo "Alternatively, you can run this in Docker:"
        echo "  docker run --rm -v \$(pwd):/workspace ghcr.io/tcort/markdown-link-check:stable /workspace/**/*.md"
        exit 1
    fi

    npm install -g markdown-link-check@3.12.2
fi

# Parse arguments
CHECK_EXTERNAL=true
FILES_PATTERN="."

while [[ $# -gt 0 ]]; do
    case $1 in
        --internal-only)
            CHECK_EXTERNAL=false
            shift
            ;;
        --file)
            FILES_PATTERN="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --internal-only    Only check internal links (skip external URLs)"
            echo "  --file PATH        Check specific file or directory (default: entire repo)"
            echo "  --help            Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                          # Check all links in all markdown files"
            echo "  $0 --internal-only          # Check only internal links"
            echo "  $0 --file docs/             # Check only files in docs directory"
            echo "  $0 --file README.md         # Check single file"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Create config for internal-only if needed
CONFIG_FILE=".markdown-link-check.json"
if [ "$CHECK_EXTERNAL" = false ]; then
    echo -e "${YELLOW}Checking internal links only...${NC}"

    # Create temporary config that ignores external links
    if [ -f "$CONFIG_FILE" ]; then
        jq '. + {"ignorePatterns": (.ignorePatterns + [{"pattern": "^https?://"}])}' \
            "$CONFIG_FILE" > .markdown-link-check-internal.json
        CONFIG_FILE=".markdown-link-check-internal.json"
    fi
fi

# Find markdown files
echo "Finding markdown files..."
if [ -f "$FILES_PATTERN" ]; then
    # Single file
    MD_FILES="$FILES_PATTERN"
elif [ -d "$FILES_PATTERN" ]; then
    # Directory
    MD_FILES=$(find "$FILES_PATTERN" -name "*.md" \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" \
        -not -path "*/vendor/*" \
        -not -path "*/.venv/*" \
        -not -path "*/venv/*" \
        2>/dev/null)
else
    # Pattern or entire repo
    MD_FILES=$(find . -name "*.md" \
        -not -path "./node_modules/*" \
        -not -path "./.git/*" \
        -not -path "./vendor/*" \
        -not -path "./.venv/*" \
        -not -path "./venv/*" \
        2>/dev/null)
fi

# Count files
FILE_COUNT=$(echo "$MD_FILES" | grep -c "^" || echo 0)

if [ "$FILE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No markdown files found.${NC}"
    exit 0
fi

echo "Found $FILE_COUNT markdown file(s) to check"
echo ""

# Check each file
FAILED_FILES=0
TOTAL_ERRORS=0

for file in $MD_FILES; do
    echo -n "Checking: $file ... "

    # Run link check
    if output=$(markdown-link-check --config "$CONFIG_FILE" "$file" 2>&1); then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        FAILED_FILES=$((FAILED_FILES + 1))

        # Show errors
        echo "$output" | grep -E "✖|→" | sed 's/^/  /'

        # Count errors
        FILE_ERRORS=$(echo "$output" | grep -c "✖" || echo 0)
        TOTAL_ERRORS=$((TOTAL_ERRORS + FILE_ERRORS))
    fi
done

# Clean up temporary config
if [ "$CHECK_EXTERNAL" = false ] && [ -f ".markdown-link-check-internal.json" ]; then
    rm -f .markdown-link-check-internal.json
fi

# Summary
echo ""
echo "========================="
echo "Summary:"
echo "  Files checked: $FILE_COUNT"
echo "  Files with errors: $FAILED_FILES"
echo "  Total broken links: $TOTAL_ERRORS"

if [ $FAILED_FILES -eq 0 ]; then
    echo -e "${GREEN}✓ All links are valid!${NC}"
    exit 0
else
    echo -e "${RED}✗ Found broken links in $FAILED_FILES file(s)${NC}"
    echo ""
    echo "To fix broken links:"
    echo "  1. Update the URLs in the affected files"
    echo "  2. Or add patterns to .markdown-link-check.json to ignore false positives"
    exit 1
fi
