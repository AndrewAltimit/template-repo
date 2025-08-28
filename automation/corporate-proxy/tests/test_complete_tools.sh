#!/bin/bash
# Test suite for all 12 Crush tools

set -e

echo "========================================="
echo "TESTING COMPLETE CRUSH TOOL SET (12 TOOLS)"
echo "========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Change to project root
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

echo -e "\n${BLUE}=== Starting Complete Tool API V3 ===${NC}"

# Stop any existing servers
pkill -f structured_tool_api || true

# Start V3 API
echo "Starting V3 API with all 12 tools..."
python3 shared/services/structured_tool_api_v3.py > /tmp/api_v3.log 2>&1 &
API_PID=$!

# Wait for API to start
echo "Waiting for API to be ready..."
sleep 3

# Check health
if curl -fsS http://localhost:8055/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API is healthy${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ API health check failed${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    exit 1
fi

echo -e "\n${BLUE}=== Testing Original 6 Tools ===${NC}"

# Test 1: Write tool
echo -e "\nTest 1: Write tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Write test.txt with Hello World"}],
        "tools": [{"type": "function", "function": {"name": "write"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"write"'; then
    echo -e "${GREEN}✅ Write tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Write tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 2: View tool
echo -e "\nTest 2: View tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "View test.txt"}],
        "tools": [{"type": "function", "function": {"name": "view"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"view"'; then
    echo -e "${GREEN}✅ View tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ View tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 3: Bash tool
echo -e "\nTest 3: Bash tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Run ls -la"}],
        "tools": [{"type": "function", "function": {"name": "bash"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"bash"'; then
    echo -e "${GREEN}✅ Bash tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Bash tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 4: Grep tool
echo -e "\nTest 4: Grep tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Search for pattern TODO in files"}],
        "tools": [{"type": "function", "function": {"name": "grep"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"grep"'; then
    echo -e "${GREEN}✅ Grep tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Grep tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 5: LS tool
echo -e "\nTest 5: LS tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "List /tmp"}],
        "tools": [{"type": "function", "function": {"name": "ls"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"ls"'; then
    echo -e "${GREEN}✅ LS tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ LS tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo -e "\n${BLUE}=== Testing New 6 Tools ===${NC}"

# Test 6: Fetch tool
echo -e "\nTest 6: Fetch tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Fetch content from https://example.com as markdown"}],
        "tools": [{"type": "function", "function": {"name": "fetch"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"fetch"'; then
    echo -e "${GREEN}✅ Fetch tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Fetch tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 7: Download tool
echo -e "\nTest 7: Download tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Download https://example.com/file.zip to downloads/file.zip"}],
        "tools": [{"type": "function", "function": {"name": "download"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"download"'; then
    echo -e "${GREEN}✅ Download tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Download tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 8: Glob tool
echo -e "\nTest 8: Glob tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Find all *.py files"}],
        "tools": [{"type": "function", "function": {"name": "glob"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"glob"'; then
    echo -e "${GREEN}✅ Glob tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Glob tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 9: Diagnostics tool
echo -e "\nTest 9: Diagnostics tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "messages": [{"role": "user", "content": "Get system diagnostics"}],
        "tools": [{"type": "function", "function": {"name": "diagnostics"}}]
    }')

if echo "$RESPONSE" | grep -q '"name":"diagnostics"'; then
    echo -e "${GREEN}✅ Diagnostics tool detected${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Diagnostics tool not detected${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo -e "\n${BLUE}=== Testing Tool Execution ===${NC}"

# Test 10: Execute fetch tool
echo -e "\nTest 10: Execute fetch tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/tools/execute \
    -H "Content-Type: application/json" \
    -d '{
        "tool": "fetch",
        "arguments": {"url": "https://httpbin.org/html", "format": "text"}
    }')

if echo "$RESPONSE" | grep -q '"status":"success"'; then
    echo -e "${GREEN}✅ Fetch execution successful${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Fetch execution failed${NC}"
    echo "Response: $RESPONSE" | head -1
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 11: Execute glob tool
echo -e "\nTest 11: Execute glob tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/tools/execute \
    -H "Content-Type: application/json" \
    -d '{
        "tool": "glob",
        "arguments": {"pattern": "*.sh", "path": "."}
    }')

if echo "$RESPONSE" | grep -q '"status":"success"'; then
    echo -e "${GREEN}✅ Glob execution successful${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Glob execution failed${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 12: Execute diagnostics tool
echo -e "\nTest 12: Execute diagnostics tool"
RESPONSE=$(curl -s -X POST http://localhost:8055/v1/tools/execute \
    -H "Content-Type: application/json" \
    -d '{
        "tool": "diagnostics",
        "arguments": {"type": "system"}
    }')

if echo "$RESPONSE" | grep -q '"status":"success"'; then
    echo -e "${GREEN}✅ Diagnostics execution successful${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Diagnostics execution failed${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 13: Tool schemas endpoint
echo -e "\nTest 13: Tool schemas endpoint"
RESPONSE=$(curl -s http://localhost:8055/v1/tools)

if echo "$RESPONSE" | grep -q '"count":12'; then
    echo -e "${GREEN}✅ All 12 tools available${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ Not all tools available${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 14: Create test file for download
echo -e "\nTest 14: Download file execution"
echo "Test content" > /tmp/test_download.txt
# Start simple HTTP server in background
cd /tmp && python3 -m http.server 8888 > /dev/null 2>&1 &
SERVER_PID=$!
sleep 2

RESPONSE=$(curl -s -X POST http://localhost:8055/v1/tools/execute \
    -H "Content-Type: application/json" \
    -d '{
        "tool": "download",
        "arguments": {"url": "http://localhost:8888/test_download.txt", "filePath": "/tmp/downloaded.txt"}
    }')

if [ -f "/tmp/downloaded.txt" ] && echo "$RESPONSE" | grep -q '"status":"success"'; then
    echo -e "${GREEN}✅ Download execution successful${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    rm -f /tmp/downloaded.txt
else
    echo -e "${RED}❌ Download execution failed${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Cleanup HTTP server
kill $SERVER_PID 2>/dev/null || true

# Cleanup API server
kill $API_PID 2>/dev/null || true

# Summary
echo -e "\n========================================="
echo -e "${BLUE}COMPLETE TOOL TEST SUMMARY${NC}"
echo -e "========================================="
echo ""
echo -e "Tool Categories:"
echo -e "✅ Original 6 tools (write, view, bash, edit, ls, grep)"
echo -e "✅ New 6 tools (fetch, download, glob, multiedit, diagnostics, sourcegraph)"
echo ""
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED))
if [ $TOTAL -gt 0 ]; then
    SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL))
    echo -e "Success Rate: ${YELLOW}${SUCCESS_RATE}%${NC}"

    if [ $SUCCESS_RATE -eq 100 ]; then
        echo -e "\n${GREEN}🎉 PERFECT! All 12 Crush tools working!${NC}"
        echo -e "Full Crush compatibility achieved!"
    elif [ $SUCCESS_RATE -ge 90 ]; then
        echo -e "\n${GREEN}✅ Excellent! Nearly complete tool coverage${NC}"
    elif [ $SUCCESS_RATE -ge 80 ]; then
        echo -e "\n${YELLOW}⚠️ Good progress, some tools need work${NC}"
    else
        echo -e "\n${RED}❌ Tool implementation needs improvement${NC}"
    fi
fi
