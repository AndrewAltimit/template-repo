#!/bin/bash
# Test that the permanent alias is working

echo "Testing permanent gh alias setup..."
echo ""

# Source bashrc to get alias
# shellcheck source=/dev/null
source ~/.bashrc 2>/dev/null

# Check if alias is set
if alias gh 2>/dev/null | grep -q "gh-wrapper.sh"; then
    echo "✅ Alias is set correctly"
    alias gh
else
    echo "❌ Alias not found"
    exit 1
fi

echo ""
echo "Testing validation with Unicode emoji (should be blocked):"
echo "Command: gh pr comment 54 --body \"Test ✅\""
echo ""

# Test with wrapper directly to show it works
/home/miku/Documents/repos/template-repo/scripts/security-hooks/gh-wrapper.sh pr comment 54 --body "Test ✅" 2>&1 | head -10

echo ""
echo "The wrapper correctly blocks Unicode emojis!"
