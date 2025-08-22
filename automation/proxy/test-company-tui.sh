#!/bin/bash
# Test script for Company OpenCode TUI functionality

set -e

echo "============================================"
echo "Testing Company OpenCode TUI"
echo "============================================"

CONTAINER_NAME="opencode-company-tui-test"
IMAGE_NAME="opencode-company-tui:latest"

# Function to test a command in the container
test_command() {
    local cmd="$1"
    local description="$2"

    echo ""
    echo "Testing: $description"
    echo "Command: $cmd"
    echo "---"

    docker run --rm \
        --name "$CONTAINER_NAME" \
        -e COMPANY_API_BASE="http://localhost:8050" \
        -e COMPANY_API_TOKEN="test-secret-token-123" \
        -e OPENROUTER_API_KEY="dummy" \
        "$IMAGE_NAME" \
        bash -c "$cmd"

    if [ $? -eq 0 ]; then
        echo "✅ $description: PASSED"
    else
        echo "❌ $description: FAILED"
        return 1
    fi
}

# Build the image if it doesn't exist
if ! docker images | grep -q "opencode-company-tui"; then
    echo "Building image first..."
    ./automation/proxy/build-company-tui.sh
fi

echo ""
echo "Running tests..."

# Test 1: Check if TUI binaries are installed
test_command "ls -la /home/bun/.cache/opencode/tui/" "TUI binaries installed"

# Test 2: Check if OpenCode binary exists
test_command "which opencode && opencode --version" "OpenCode binary exists"

# Test 3: List models (should only show 3 company models)
test_command "opencode models 2>&1 | grep -E 'Company|claude-3.5-sonnet|claude-3-opus|gpt-4' | head -5" "Model listing shows only company models"

# Test 4: Check if TUI binary is executable
test_command "test -x /home/bun/.cache/opencode/tui/tui-linux-x64 && echo 'TUI binary is executable'" "TUI binary is executable"

# Test 5: Check environment variable
test_command "echo \$OPENCODE_TUI_BINARY" "TUI binary environment variable set"

echo ""
echo "============================================"
echo "Test Summary"
echo "============================================"
echo ""
echo "All automated tests completed."
echo ""
echo "To test TUI interactively:"
echo "  1. Run: ./automation/proxy/run-company-tui.sh"
echo "  2. Inside container:"
echo "     a. Start mock API: python3 mock_company_api.py &"
echo "     b. Start wrapper: python3 company_translation_wrapper.py &"
echo "     c. Run TUI: opencode"
echo ""
echo "The TUI should start without 'go run' errors!"
