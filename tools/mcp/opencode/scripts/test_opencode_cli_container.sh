#!/bin/bash
# Test script for OpenCode CLI functionality in Docker container

set -e

echo "🐳 Testing OpenCode CLI in Container"
echo "======================================"

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
DOCKER_BASE="docker-compose run --rm -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY openrouter-agents"

# Test 1: Simple code generation
echo "Test 1: Simple Code Generation"
echo "------------------------------"
$DOCKER_BASE opencode run -q "Write a Python function to calculate factorial" || echo "❌ Test 1 failed"
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

# Mount the temp file and run in container
CONTEXT_DIR=$(dirname "$TMP_CONTEXT")
CONTEXT_FILE=$(basename "$TMP_CONTEXT")
docker-compose run --rm \
    -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
    -v "$CONTEXT_DIR:/workspace" \
    openrouter-agents \
    opencode run -q "Complete the process_data function to filter and transform data" -c "/workspace/$CONTEXT_FILE" || echo "❌ Test 2 failed"
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

REFACTOR_DIR=$(dirname "$TMP_REFACTOR")
REFACTOR_FILE=$(basename "$TMP_REFACTOR")
docker-compose run --rm \
    -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
    -v "$REFACTOR_DIR:/workspace" \
    openrouter-agents \
    opencode refactor -f "/workspace/$REFACTOR_FILE" -i "Improve code style and add error handling" || echo "❌ Test 3 failed"
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

REVIEW_DIR=$(dirname "$TMP_REVIEW")
REVIEW_FILE=$(basename "$TMP_REVIEW")
docker-compose run --rm \
    -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
    -v "$REVIEW_DIR:/workspace" \
    openrouter-agents \
    opencode review -f "/workspace/$REVIEW_FILE" --focus security || echo "❌ Test 4 failed"
rm -f "$TMP_REVIEW"
echo ""

# Test 5: Status check
echo "Test 5: Status Check"
echo "--------------------"
$DOCKER_BASE opencode status || echo "❌ Test 5 failed"
echo ""

echo "✅ All OpenCode container tests completed!"
echo ""
echo "Note: Review the output above to verify functionality"
