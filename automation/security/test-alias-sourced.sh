#!/bin/bash
# Test script to verify gh-wrapper alias is set up correctly
# This script should be sourced, not executed: . automation/security/test-alias-sourced.sh

echo "🔍 Testing gh-wrapper alias setup..."
echo ""

# Test 1: Check if alias is set in current shell
echo "1️⃣ Checking if gh alias is configured..."
if type gh 2>/dev/null | grep -q "aliased to.*gh-wrapper.sh"; then
    echo "   ✅ gh alias is correctly set to use gh-wrapper.sh"
    ALIAS_SET=true
else
    # Try checking with alias command
    if alias gh 2>/dev/null | grep -q "gh-wrapper.sh"; then
        echo "   ✅ gh alias is correctly set to use gh-wrapper.sh"
        ALIAS_SET=true
    else
        echo "   ⚠️  gh alias not detected, attempting to set it up..."
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        # shellcheck source=/dev/null
        source "$SCRIPT_DIR/setup-agent-hooks.sh"

        # Check again
        if alias gh 2>/dev/null | grep -q "gh-wrapper.sh"; then
            echo "   ✅ gh alias is now set"
            ALIAS_SET=true
        else
            echo "   ❌ Failed to set gh alias"
            ALIAS_SET=false
        fi
    fi
fi

if [ "$ALIAS_SET" = true ]; then
    # Test 2: Check if Python 3 is available
    echo ""
    echo "2️⃣ Checking Python 3 availability..."
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 --version)
        echo "   ✅ Python 3 is available: $PYTHON_VERSION"
    else
        echo "   ❌ Python 3 is not available"
    fi

    # Test 3: Check if wrapper is executable
    echo ""
    echo "3️⃣ Checking wrapper script permissions..."
    WRAPPER_PATH=$(alias gh 2>/dev/null | sed "s/.*='\(.*\)'/\1/" | sed "s/.*=\"\(.*\)\"/\1/")
    if [ -x "$WRAPPER_PATH" ]; then
        echo "   ✅ gh-wrapper.sh is executable"
    else
        echo "   ❌ gh-wrapper.sh is not executable at: $WRAPPER_PATH"
    fi

    # Test 4: Test with a simple gh command
    echo ""
    echo "4️⃣ Testing gh command passthrough..."
    if gh --version >/dev/null 2>&1; then
        echo "   ✅ gh commands are working through the wrapper"
    else
        echo "   ❌ gh commands are failing"
    fi

    # Test 5: Test status function
    echo ""
    echo "5️⃣ Testing agent_hooks_status function..."
    if command -v agent_hooks_status >/dev/null 2>&1; then
        echo "   ✅ agent_hooks_status function is available"
    else
        echo "   ❌ agent_hooks_status function not found"
    fi

    echo ""
    echo "✨ Security hooks are configured!"
    echo ""
    echo "To verify validation works, try:"
    echo "  gh pr comment 1 --body 'Test with emoji ✅'"
    echo "  (Should be blocked due to Unicode emoji)"
fi
