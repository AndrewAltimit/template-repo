#!/bin/bash
# Test script for Crush CLI functionality in Docker container

set -e

echo "🐳 Testing Crush CLI in Container"
echo "=================================="

# Auto-load .env file if it exists and OPENROUTER_API_KEY is not set
if [ -z "$OPENROUTER_API_KEY" ] && [ -f ".env" ]; then
    echo "📄 Loading environment from .env file..."
    set -a
    source .env
    set +a
fi

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ OPENROUTER_API_KEY not set"
    exit 1
fi

echo "✅ API key configured"
echo ""

# Base Docker command
DOCKER_BASE="docker-compose run --rm -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY -e OPENAI_API_KEY=$OPENROUTER_API_KEY -e OPENAI_API_BASE=https://openrouter.ai/api/v1 openrouter-agents"

# Test 1: Quick code generation
echo "Test 1: Quick Code Generation"
echo "-----------------------------"
$DOCKER_BASE crush run -q "Write a Python function to reverse a string" || echo "❌ Test 1 failed"
echo ""

# Test 2: Detailed generation
echo "Test 2: Detailed Generation"
echo "---------------------------"
$DOCKER_BASE crush run -q "Create a complete implementation of a linked list with all operations" || echo "❌ Test 2 failed"
echo ""

# Test 3: Code explanation
echo "Test 3: Code Explanation"
echo "------------------------"
TMP_EXPLAIN=$(mktemp --suffix=.py)
trap 'rm -f "$TMP_EXPLAIN"' EXIT

cat > "$TMP_EXPLAIN" << EOF
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
EOF

# Read the file content directly since we don't need to mount it
CODE_CONTENT=$(cat "$TMP_EXPLAIN")
$DOCKER_BASE crush run -q "Explain this code:\n\n$CODE_CONTENT" || echo "❌ Test 3 failed"
echo ""

# Test 4: Code conversion (Python to JavaScript)
echo "Test 4: Code Conversion"
echo "-----------------------"
TMP_CONVERT=$(mktemp --suffix=.py)

cat > "$TMP_CONVERT" << EOF
def greet(name="World"):
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("User"))
EOF

CONVERT_CONTENT=$(cat "$TMP_CONVERT")
$DOCKER_BASE crush run -q "Convert this Python code to JavaScript:\n\n$CONVERT_CONTENT" || echo "❌ Test 4 failed"
rm -f "$TMP_CONVERT"
echo ""

# Test 5: Style Comparison
echo "Test 5: Style Comparison"
echo "------------------------"
echo "Concise style:"
$DOCKER_BASE crush run -q "Binary search function" || echo "❌ Test 5a failed"
echo ""
echo "Detailed style:"
$DOCKER_BASE crush run -q "Create a detailed binary search function with error handling and comments" || echo "❌ Test 5b failed"
echo ""

echo "✅ All Crush container tests completed!"
echo ""
echo "Note: Review the output above to verify functionality"
