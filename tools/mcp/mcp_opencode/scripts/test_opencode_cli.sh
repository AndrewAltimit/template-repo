#!/bin/bash
# Test script for OpenCode CLI functionality

set -e

echo "🧪 Testing OpenCode CLI Functionality"
echo "======================================"

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ OPENROUTER_API_KEY not set"
    exit 1
fi

echo "✅ API key configured"
echo ""

# Test 1: Simple code generation
echo "Test 1: Simple Code Generation"
echo "------------------------------"
opencode run -q "Write a Python function to calculate factorial" || echo "❌ Test 1 failed"
echo ""

# Test 2: Code with context
echo "Test 2: Code with Context"
echo "-------------------------"
TMP_CONTEXT=$(mktemp --suffix=.py)
trap 'rm -f "$TMP_CONTEXT"' EXIT

cat > "$TMP_CONTEXT" << EOF
def process_data(data):
    # TODO: Implement data processing
    pass
EOF

opencode run -q "Complete the process_data function to filter and transform data" -c "$TMP_CONTEXT" || echo "❌ Test 2 failed"
echo ""

# Test 3: Code refactoring
echo "Test 3: Code Refactoring"
echo "------------------------"
TMP_REFACTOR=$(mktemp --suffix=.py)

cat > "$TMP_REFACTOR" << EOF
def calc(x,y,op):
    if op=='+':return x+y
    if op=='-':return x-y
    if op=='*':return x*y
    if op=='/':return x/y
EOF

opencode refactor -f "$TMP_REFACTOR" -i "Improve code style and add error handling" || echo "❌ Test 3 failed"
rm -f "$TMP_REFACTOR"
echo ""

# Test 4: Code review
echo "Test 4: Code Review"
echo "-------------------"
TMP_REVIEW=$(mktemp --suffix=.py)

cat > "$TMP_REVIEW" << EOF
def authenticate(username, password):
    users = {"admin": "password123", "user": "test"}
    return users.get(username) == password
EOF

opencode review -f "$TMP_REVIEW" --focus security || echo "❌ Test 4 failed"
rm -f "$TMP_REVIEW"
echo ""

# Test 5: Status check
echo "Test 5: Status Check"
echo "--------------------"
opencode status || echo "❌ Test 5 failed"
echo ""

echo "✅ All OpenCode CLI tests completed!"
echo ""
echo "Note: Review the output above to verify functionality"
