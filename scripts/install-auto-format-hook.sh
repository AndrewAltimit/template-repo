#!/bin/bash
# Install a git pre-commit hook that auto-stages formatted files

cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Git pre-commit hook with auto-staging for formatted files

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Store the initial state
INITIAL_STASH=$(git stash create)

# Run pre-commit hooks
echo -e "${YELLOW}Running pre-commit hooks...${NC}"
pre-commit run

# Check the exit status
RESULT=$?

if [ $RESULT -ne 0 ]; then
    # Check if files were modified (formatted)
    if ! git diff --quiet; then
        echo -e "\n${YELLOW}Files were reformatted. Auto-staging changes...${NC}"

        # Stage all modified tracked files
        git add -u

        # Show what was staged
        echo -e "${GREEN}Auto-staged files:${NC}"
        git diff --cached --name-only

        # Run pre-commit again on the staged files
        echo -e "\n${YELLOW}Running pre-commit hooks again...${NC}"
        pre-commit run
        RESULT=$?

        if [ $RESULT -eq 0 ]; then
            echo -e "\n${GREEN}✅ All checks passed! Commit will proceed.${NC}"
        fi
    fi
fi

exit $RESULT
EOF

# Make the hook executable
chmod +x .git/hooks/pre-commit

echo "✅ Auto-format git hook installed successfully!"
echo ""
echo "The hook will:"
echo "  1. Run formatters (black, isort, etc.)"
echo "  2. Auto-stage any formatting changes"
echo "  3. Re-run validation"
echo "  4. Allow the commit if all checks pass"
echo ""
echo "To uninstall: rm .git/hooks/pre-commit"
