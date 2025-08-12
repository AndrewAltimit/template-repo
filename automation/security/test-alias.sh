#!/bin/bash
# Test script to verify gh-wrapper alias is set up correctly

echo "🔍 Testing gh-wrapper alias setup..."
echo ""

# Test 1: Check if alias is set
echo "1️⃣ Checking if gh alias is configured..."
if alias gh 2>/dev/null | grep -q "gh-wrapper.sh"; then
    echo "   ✅ gh alias is correctly set to use gh-wrapper.sh"
else
    echo "   ❌ gh alias is NOT set. Run: source automation/security/setup-agent-hooks.sh"
    exit 1
fi

# Test 2: Check if Python 3 is available
echo ""
echo "2️⃣ Checking Python 3 availability..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version)
    echo "   ✅ Python 3 is available: $PYTHON_VERSION"
else
    echo "   ❌ Python 3 is not available"
    exit 1
fi

# Test 3: Check if wrapper is executable
echo ""
echo "3️⃣ Checking wrapper script permissions..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$SCRIPT_DIR/gh-wrapper.sh" ]; then
    echo "   ✅ gh-wrapper.sh is executable"
else
    echo "   ❌ gh-wrapper.sh is not executable. Run: chmod +x automation/security/*.sh"
    exit 1
fi

# Test 4: Check if validators exist
echo ""
echo "4️⃣ Checking validator scripts..."
if [ -f "$SCRIPT_DIR/github-secrets-masker.py" ] && [ -f "$SCRIPT_DIR/gh-comment-validator.py" ]; then
    echo "   ✅ Validator scripts found"
else
    echo "   ❌ Missing validator scripts"
    exit 1
fi

# Test 5: Test with a simple gh command (should work)
echo ""
echo "5️⃣ Testing gh command passthrough..."
if gh --version >/dev/null 2>&1; then
    echo "   ✅ gh commands are working through the wrapper"
else
    echo "   ❌ gh commands are failing"
    exit 1
fi

# Test 6: Test status function
echo ""
echo "6️⃣ Testing agent_hooks_status function..."
if command -v agent_hooks_status >/dev/null 2>&1; then
    echo "   ✅ agent_hooks_status function is available"
    echo ""
    echo "Running status check:"
    agent_hooks_status
else
    echo "   ❌ agent_hooks_status function not found"
    exit 1
fi

echo ""
echo "✨ All tests passed! Security hooks are properly configured."
echo ""
echo "Try these commands to verify validation:"
echo "  gh pr comment 1 --body 'Test with emoji ✅'"
echo "  (Should be blocked due to Unicode emoji)"
