#!/bin/bash
# Test script for Crush CLI functionality

set -e

echo "⚡ Testing Crush CLI Functionality"
echo "=================================="

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ OPENROUTER_API_KEY not set"
    exit 1
fi

# Set up Crush environment
export OPENAI_API_KEY="$OPENROUTER_API_KEY"
export OPENAI_API_BASE="https://openrouter.ai/api/v1"

echo "✅ API key configured"
echo ""

# Check if crush is installed
if ! command -v crush &> /dev/null; then
    echo "❌ crush CLI not found. Please install it first:"
    echo "   go install github.com/charmbracelet/crush@latest"
    echo "   or"
    echo "   brew install charmbracelet/tap/crush"
    exit 1
fi

# Test 1: Quick code generation
echo "Test 1: Quick Code Generation"
echo "-----------------------------"
crush run -q "Write a Python function to reverse a string" || echo "❌ Test 1 failed"
echo ""

# Test 2: Detailed generation
echo "Test 2: Detailed Generation"
echo "---------------------------"
crush run -q "Create a complete implementation of a linked list with all operations" || echo "❌ Test 2 failed"
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

CODE_CONTENT=$(cat "$TMP_EXPLAIN")
crush run -q "Explain this code:\n\n$CODE_CONTENT" || echo "❌ Test 3 failed"
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
crush run -q "Convert this Python code to JavaScript:\n\n$CONVERT_CONTENT" || echo "❌ Test 4 failed"
rm -f "$TMP_CONVERT"
echo ""

# Test 5: Concise vs Detailed style
echo "Test 5: Style Comparison"
echo "------------------------"
echo "Concise style:"
crush run -q "Binary search function" || echo "❌ Test 5a failed"
echo ""
echo "Detailed style:"
crush run -q "Create a detailed binary search function with error handling and comments" || echo "❌ Test 5b failed"
echo ""

echo "✅ All Crush CLI tests completed!"
echo ""
echo "Note: Review the output above to verify functionality"
